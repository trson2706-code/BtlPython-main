"""Presenter layer — điểm vào duy nhất của ứng dụng điểm danh sinh viên.

Ghép nối tất cả core modules (Model) và GUI panels (View) theo MVP pattern.
Quản lý state machine: Mode 1 (chờ GV) → Mode 2 (điểm danh SV) → idle → reset.
Thread safety: mọi GUI update qua app.after(0, ...).

Chạy bằng:
    python -m src.main
    python src/main.py
"""

import logging
import os
import subprocess
import sys
from datetime import datetime

from src.core.config import Config
from src.core.database import DatabaseManager
from src.core.class_manager import ClassManager
from src.core.student_manager import StudentManager
from src.core.attendance_session import AttendanceSession
from src.core.camera import CameraManager
from src.core.worker import RecognitionWorker
from src.core.excel_export import ExcelExporter
from src.core.events import events, EventType
from src.gui.app import App
from src.gui.admin_window import AdminWindow

logger = logging.getLogger(__name__)


class Presenter:
    """Orchestrator chính — kết nối Model ↔ View qua event system."""

    def __init__(self):
        # 1. Data layer
        self.db = DatabaseManager()
        self.class_mgr = ClassManager(self.db)
        self.student_mgr = StudentManager(self.db)

        # 2. Business logic
        self.session = AttendanceSession(self.class_mgr)
        self.exporter = ExcelExporter()

        # 3. Camera + Worker
        self.camera = CameraManager()
        self.worker = RecognitionWorker(self.camera)

        # 4. GUI (MUST be last — triggers Tk initialization)
        self.app = App()

        # 4b. Inject config vào SessionPanel (App tạo default 60)
        config = Config()
        self.app.session_panel._scan_time_minutes = config.get(
            'session', 'student_scan_time', default=60
        )

        # 5. State tracking
        self._current_mode = None          # 1=teacher, 2=student, None=idle
        self._current_class_id = None
        self._pending_class_id = None      # Lưu class_id chờ xác nhận
        self._current_teacher_id = None
        self._last_session_result = None   # [F4-fix] Lưu result để xuất Excel thủ công
        self._admin_window = None           # E8-S2: AdminWindow lifecycle
        self._post_session_popup = None     # E9-S3: Post-session notification popup

        # 6. Wire camera → GUI
        self.app.camera_panel._get_frame_callback = self.camera.get_frame

        # 7. Setup events
        self._setup_events()

    # ──────────────────────────────────────────────────────────
    # EVENT WIRING
    # ──────────────────────────────────────────────────────────

    def _setup_events(self):
        """Subscribe tất cả events (bao gồm CAMERA_STOPPED)."""
        events.subscribe(EventType.TEACHER_DETECTED, self._on_teacher_detected)
        events.subscribe(EventType.SESSION_CONFIRMED, self._on_session_confirmed)
        events.subscribe(EventType.STUDENT_DETECTED, self._on_student_detected)
        events.subscribe(EventType.SESSION_END_REQUESTED, self._on_session_end_requested)
        events.subscribe(EventType.EXCEL_EXPORT_REQUESTED, self._on_excel_export_requested)
        events.subscribe(EventType.MANUAL_MARK_REQUESTED, self._on_manual_mark_requested)
        events.subscribe(EventType.SHUTDOWN_REQUESTED, self._on_shutdown)
        events.subscribe(EventType.ERROR_OCCURRED, self._on_error)
        events.subscribe(EventType.CAMERA_STOPPED, self._on_camera_stopped)
        events.subscribe(EventType.ADMIN_REQUESTED, self._on_admin_requested)
        events.subscribe(EventType.FACE_UNRECOGNIZED, self._on_face_unrecognized)
        events.subscribe(EventType.SPOOF_DETECTED, self._on_spoof_detected)

    # ──────────────────────────────────────────────────────────
    # MODE 1: CHỜ GIẢNG VIÊN
    # ──────────────────────────────────────────────────────────

    def _on_teacher_detected(self, data):
        """Handler cho TEACHER_DETECTED — Mode 1 flow (AC#4) + [F3-fix] mode guard."""
        # [F3-fix] Mode guard: bỏ qua stale events từ mode cũ
        if self._current_mode != 1:
            return

        person_id = data['person_id']

        # Guard None: kiểm tra teacher tồn tại trong DB
        teacher_info = self.db.get_teacher(person_id)
        if not teacher_info:
            logger.warning(f"Không tìm thấy giảng viên ID {person_id} trong DB.")
            return

        # Tra TKB — ValueError nếu không có lịch
        try:
            class_id = self.session.check_timetable(person_id)
        except ValueError as e:
            logger.warning(f"Giảng viên {person_id} không có TKB phù hợp: {e}")
            return

        # Guard None: kiểm tra class tồn tại
        class_info = self.db.get_class(class_id)
        if not class_info:
            logger.warning(f"Không tìm thấy lớp ID {class_id} trong DB.")
            return

        # Lưu state chờ xác nhận
        self._pending_class_id = class_id
        self._current_teacher_id = person_id

        # Enrich data cho GUI
        enriched = {
            'person_id': person_id,
            'name': teacher_info['name'],
            'teacher_code': teacher_info['teacher_code'],
            'class_info': f"{class_info['subject']} - {class_info['class_code']}",
            'confidence': data['confidence'],
            'coordinates': data['coordinates'],
        }

        # Thread-safe GUI update
        self.app.after(0, self.app.session_panel.on_teacher_detected, enriched)
        self.app.after(0, self.app.camera_panel.set_bounding_box, data['coordinates'], 'green')

    # ──────────────────────────────────────────────────────────
    # SESSION CONFIRMED: CHUYỂN SANG MODE 2
    # ──────────────────────────────────────────────────────────

    def _on_session_confirmed(self, data):
        """Handler cho SESSION_CONFIRMED — xác nhận GV, chuyển Mode 2 (AC#5).

        [CR-1] Mode guard: chỉ xử lý khi đang ở Mode 1.
        [CR-3] Guard _pending_class_id is None.
        """
        # [CR-1] Mode guard: bỏ qua nếu không đang ở Mode 1 (chờ GV)
        if self._current_mode != 1:
            return

        # [CR-3] Guard: _pending_class_id phải có giá trị
        if self._pending_class_id is None:
            logger.warning("SESSION_CONFIRMED nhưng _pending_class_id is None.")
            return

        self.worker.pause_scanning()

        class_id = self._pending_class_id
        self._current_class_id = class_id

        # Start session — session tự emit SESSION_STARTED, Presenter chủ động update GUI
        self.session.start_session(class_id)

        # Load student encodings cho lớp hiện tại
        self._load_student_encodings(class_id)

        # Chuyển sang quét SV
        self.worker.start_scanning(mode=2)

        # [CR-6] Defensive or [] cho DB returns
        # Chuẩn bị students list cho GUI
        students_in_class = self.db.get_students_in_class(class_id) or []
        students_list = [
            {
                'student_id': s['id'],
                'name': s['name'],
                'student_code': s['student_code'],
            }
            for s in students_in_class
        ]

        # Thread-safe GUI updates
        self.app.after(0, self.app.session_panel.on_session_started, {
            'class_id': class_id,
            'start_time': datetime.now(),
        })
        self.app.after(0, self.app.attendance_panel.on_session_started, {
            'class_id': class_id,
            'students': students_list,
        })
        self.app.after(0, self.app.student_panel.on_students_loaded, students_list)

        self._current_mode = 2

    # ──────────────────────────────────────────────────────────
    # MODE 2: ĐIỂM DANH SINH VIÊN
    # ──────────────────────────────────────────────────────────

    def _on_student_detected(self, data):
        """Handler cho STUDENT_DETECTED — điểm danh SV (AC#6) + [F3-fix] mode guard."""
        # Guard nguồn event: bỏ qua event từ AttendanceSession.mark_present() (không có coordinates)
        if 'coordinates' not in data:
            return

        # [F3-fix] Mode guard: bỏ qua stale events
        if self._current_mode != 2:
            return

        student_id = data['person_id']  # ⚠️ worker dùng 'person_id', map thành student_id
        raw_confidence = data['confidence']  # Giá trị 0-100 từ calculate_confidence()

        # ⚠️ CRITICAL: chuyển về 0.0-1.0 cho session (ExcelExporter nhân 100 lại)
        session_confidence = raw_confidence / 100.0

        snapshot_path = data.get('snapshot_path')

        # Mark present — session sẽ emit STUDENT_DETECTED nội bộ, bị bỏ qua ở guard nguồn event
        success = self.session.mark_present(student_id, session_confidence, snapshot_path)
        if not success:
            return  # SV đã điểm danh hoặc không thuộc lớp

        # Query student info để enrich data cho GUI
        student = self.db.get_student(student_id)
        if not student:
            return  # Guard None

        mark_time_str = datetime.now().strftime('%H:%M:%S')
        enriched = {
            'student_id': student_id,
            'name': student['name'],
            'student_code': student['student_code'],
            'confidence': raw_confidence,
            'mark_time': mark_time_str,
        }

        # Thread-safe GUI updates
        self.app.after(0, self.app.attendance_panel.add_record, enriched)
        self.app.after(0, self.app.student_panel.on_student_marked, enriched)
        self.app.after(0, self.app.session_panel.on_student_detected, enriched)
        self.app.after(0, self.app.camera_panel.set_bounding_box, data['coordinates'], 'green')

        # Bounding box tự clear sau 2 giây
        self.app.after(2000, self.app.camera_panel.clear_bounding_box)

    # ──────────────────────────────────────────────────────────
    # KẾT THÚC SESSION
    # ──────────────────────────────────────────────────────────

    def _on_session_end_requested(self, data):
        """Handler cho SESSION_END_REQUESTED — kết thúc session (AC#7).

        [F7-fix]: try-except ValueError tránh crash khi end_session() gọi 2 lần.
        [F4-fix]: Lưu result cho xuất Excel thủ công.
        [F8-fix]: Wrap export trong try-except.
        [PM-4]: pause_scanning() ngoài try block — đảm bảo luôn chạy.
        [PM-1/PM-5]: Reset _pending_class_id khi chuyển idle.
        """
        # [PM-4] pause_scanning NGOÀI try block — nếu throw thì session vẫn end được
        self.worker.pause_scanning()

        try:
            result = self.session.end_session()
        except ValueError as e:
            # [F7-fix] Duplicate guard: session đã kết thúc (countdown + nút bấm gần cùng lúc)
            logger.warning(f"end_session() duplicate call: {e}")
            return

        # [F4-fix] Lưu result cho xuất Excel thủ công (AC#9)
        self._last_session_result = result
        self._current_mode = None  # Chuyển sang idle
        # [PM-1/PM-5] Reset stale pending state — tránh leak vào auto-reset
        self._pending_class_id = None

        # [E9-S1] Lưu lịch sử vào DB — best-effort (không block Excel export)
        try:
            self.db.save_session(result, self._current_teacher_id)
        except Exception as e:
            # Broad Exception: save_session có thể raise sqlite3.Error,
            # TypeError (datetime conversion), KeyError, etc.
            logger.error(f"Lỗi lưu lịch sử điểm danh: {e}")

        # Query class/teacher info cho export
        class_info = self.db.get_class(self._current_class_id)
        teacher_info = self.db.get_teacher(self._current_teacher_id)

        # [F8-fix] Wrap export trong try-except
        try:
            filepath = self.exporter.export_session(result, class_info, teacher_info)
            logger.info(f"Đã xuất Excel: {filepath}")
            # [E9-S3] Thông báo chi tiết: Có mặt X/Y (Z%) — Excel đã xuất
            present_count, total, pct = self._compute_attendance_summary(result)
            summary_msg = f"✅ Có mặt {present_count}/{total} ({pct:.1f}%) — Excel đã xuất"
            self.app.after(0, self.app.student_panel.on_error, summary_msg, "green")
            # [E9-S3] Popup thông báo
            self.app.after(0, self._show_post_session_popup, filepath, result)
        except (ValueError, OSError) as e:
            logger.error(f"Lỗi xuất Excel: {e}")
            self.app.after(0, self.app.student_panel.on_error, str(e))

        # Update GUI
        self.app.after(0, self.app.session_panel.on_session_ended, result)
        self.app.after(0, self.app.attendance_panel.on_session_ended, result)

        # Sau 5 giây delay: quay về Flow Chờ GV (AC#8)
        # [F5-fix]: dùng self._reset_to_teacher_mode (có self. prefix)
        self.app.after(5000, self._reset_to_teacher_mode)

    def _reset_to_teacher_mode(self):
        """Auto-reset sau khi kết thúc — quay về Mode 1 (AC#8).

        [F12-fix]: Kiểm tra winfo_exists() tránh crash khi app đóng trong 5 giây delay.
        [E9-S3]: Cleanup post-session popup + skip reset if AdminWindow is open.
        """
        # [F12-fix] Guard: app có thể đã đóng trong 5 giây delay
        if not self.app.winfo_exists():
            return

        # [E9-S3] Cleanup post-session popup nếu còn mở
        self._close_post_session_popup()

        # [E9-S3] Skip reset nếu AdminWindow đang mở
        # (user click "Xem lịch sử" từ popup → mở admin → auto-reset timer vẫn pending
        #  → nếu không guard thì reset sẽ corrupt state: start_scanning + mode=1 khi admin open)
        if self._admin_window is not None:
            return

        # Reset tất cả panels
        self.app.session_panel.reset()
        self.app.attendance_panel.reset()
        self.app.student_panel.reset()
        self.app.camera_panel.clear_bounding_box()

        # Load lại teacher encodings + bắt đầu quét GV
        self._load_teacher_encodings()
        self.worker.start_scanning(mode=1)
        self._current_mode = 1

    # ──────────────────────────────────────────────────────────
    # XUẤT EXCEL THỦ CÔNG
    # ──────────────────────────────────────────────────────────

    def _on_excel_export_requested(self, data):
        """Handler cho EXCEL_EXPORT_REQUESTED — xuất Excel thủ công (AC#9)."""
        if self._last_session_result is None:
            logger.warning("Không có kết quả session để xuất Excel.")
            self.app.after(
                0, self.app.student_panel.on_error,
                "Chưa có kết quả điểm danh để xuất."
            )
            return

        class_info = self.db.get_class(self._current_class_id)
        teacher_info = self.db.get_teacher(self._current_teacher_id)

        try:
            filepath = self.exporter.export_session(
                self._last_session_result, class_info, teacher_info
            )
            logger.info(f"Đã xuất Excel thủ công: {filepath}")
        except (ValueError, OSError) as e:
            logger.error(f"Lỗi xuất Excel thủ công: {e}")
            self.app.after(0, self.app.student_panel.on_error, str(e))

    # ──────────────────────────────────────────────────────────
    # ĐIỂM DANH THỦ CÔNG
    # ──────────────────────────────────────────────────────────

    def _on_manual_mark_requested(self, data):
        """Handler cho MANUAL_MARK_REQUESTED — điểm danh thủ công khi hệ thống lỗi.

        GV bấm nút điểm danh cho SV mà camera không nhận diện được.
        Gọi session.mark_present() với confidence=1.0 (thủ công) rồi cập nhật GUI.
        """
        if self._current_mode != 2:
            return

        student_id = data.get('student_id')
        if student_id is None:
            return

        # Mark present với confidence 1.0 (manual) — session sẽ emit STUDENT_DETECTED nội bộ
        success = self.session.mark_present(student_id, 1.0)
        if not success:
            self.app.after(
                0, self.app.student_panel.on_error,
                "SV đã được điểm danh hoặc không thuộc lớp."
            )
            return

        # Query student info
        student = self.db.get_student(student_id)
        if not student:
            return

        mark_time_str = datetime.now().strftime('%H:%M:%S')
        enriched = {
            'student_id': student_id,
            'name': student['name'],
            'student_code': student['student_code'],
            'confidence': 100.0,
            'mark_time': mark_time_str,
        }

        # Cập nhật cả 2 panel
        self.app.after(0, self.app.attendance_panel.add_record, enriched)
        self.app.after(0, self.app.student_panel.on_student_marked, enriched)
        self.app.after(
            0, self.app.student_panel.on_error,
            f"✅ Đã điểm danh thủ công: {student['name']}", "green"
        )
        logger.info(f"Điểm danh thủ công SV {student_id}: {student['name']}")

    # ──────────────────────────────────────────────────────────
    # SHUTDOWN + ERROR + CAMERA_STOPPED
    # ──────────────────────────────────────────────────────────

    def _on_shutdown(self, data):
        """Handler cho SHUTDOWN_REQUESTED — graceful shutdown (AC#12).

        [PM-2]: Set _current_mode = None first so all mode-guarded event
        handlers become no-ops before we tear down resources.
        """
        logger.info("Shutdown requested — dọn dẹp resources...")
        # [PM-2] Neutralize mode guards trước khi dọn dẹp
        self._current_mode = None
        self.worker.stop_scanning()
        self.camera.stop()
        self.app.camera_panel.stop_preview()
        self.app.after(0, self.app.destroy)

    def _on_face_unrecognized(self, data):
        """Handler cho FACE_UNRECOGNIZED — khuôn mặt phát hiện nhưng không khớp DB."""
        if self._current_mode is None:
            return
        coords = data.get('coordinates')
        if coords:
            self.app.after(0, self.app.camera_panel.set_bounding_box, coords, 'red')
            self.app.after(2000, self.app.camera_panel.clear_bounding_box)
        self.app.after(
            0, lambda: self.app.session_panel.info_label.configure(
                text="❌ Không nhận diện được"
            )
        )

    def _on_spoof_detected(self, data):
        """Handler cho SPOOF_DETECTED — hiển thị cảnh báo spoof trên GUI."""
        # Mode guard: bỏ qua nếu idle (không đang nhận diện)
        if self._current_mode is None:
            return
        coords = data.get('coordinates')
        score = data.get('liveness_score', 0.0)
        logger.warning("Phát hiện ảnh giả (score=%.2f): %s", score, data.get('details'))
        if coords:
            self.app.after(0, self.app.camera_panel.set_bounding_box, coords, 'red')
            self.app.after(2000, self.app.camera_panel.clear_bounding_box)
        self.app.after(
            0, lambda: self.app.session_panel.info_label.configure(
                text="⚠️ Phát hiện ảnh giả — Vui lòng dùng khuôn mặt thật"
            )
        )

    def _on_error(self, data):
        """Handler cho ERROR_OCCURRED — log lỗi (AC#13)."""
        logger.error(f"Lỗi hệ thống: {data}")

    def _on_camera_stopped(self, data):
        """Handler cho CAMERA_STOPPED — camera disconnect (AC#14) [F13-fix].

        [CR-2] Hiển thị thông báo trên info_label thay vì gọi on_session_ended()
        — tránh chuyển session panel sang state SESSION_ENDED không đúng ngữ cảnh.
        """
        logger.warning("Camera đã ngắt kết nối.")
        if self._current_mode is not None:
            self.app.after(
                0, lambda: self.app.session_panel.info_label.configure(
                    text="⚠️ Camera ngắt kết nối"
                )
            )
        self._current_mode = None

    # ──────────────────────────────────────────────────────────
    # ENCODING LOADING
    # ──────────────────────────────────────────────────────────

    def _load_teacher_encodings(self):
        """Load tất cả teacher encodings vào worker cho Mode 1."""
        raw_encodings = self.db.get_encodings_by_type('teacher') or []  # [CR-8]
        encodings = [r['encoding'] for r in raw_encodings]
        metadata = [
            {'person_id': r['person_id'], 'person_type': 'teacher'}
            for r in raw_encodings
        ]
        self.worker.load_encodings(encodings, metadata)

    def _load_student_encodings(self, class_id: int):
        """Load student encodings CHỈ cho lớp hiện tại vào worker cho Mode 2."""
        students = self.db.get_students_in_class(class_id) or []  # [CR-7]
        student_ids = {s['id'] for s in students}

        all_student_encodings = self.db.get_encodings_by_type('student') or []  # [CR-7]
        encodings = []
        metadata = []
        for r in all_student_encodings:
            if r['person_id'] in student_ids:
                encodings.append(r['encoding'])
                metadata.append({'person_id': r['person_id'], 'person_type': 'student'})

        self.worker.load_encodings(encodings, metadata)
        # ⚠️ [F2-note] O(N) filter — chấp nhận cho MVP. Tech debt cho future optimization.

    # ──────────────────────────────────────────────────────────
    # ADMIN WINDOW (E8-S2)
    # ──────────────────────────────────────────────────────────

    def _on_admin_requested(self, data):
        """Handler cho ADMIN_REQUESTED — mở AdminWindow (AC#3-#6)."""
        # Mode guard: chỉ mở admin khi đang chờ GV (Mode 1)
        if self._current_mode != 1:
            return
        # Double-open guard: ngăn tạo window thứ 2 nếu click nhanh
        if self._admin_window is not None:
            return
        # Pause worker trước khi tạo AdminWindow
        self.worker.pause_scanning()
        # [CR2-F4] Neutralize mode immediately — prevent stale TEACHER_DETECTED
        # events (already queued by worker thread) from being processed
        self._current_mode = None
        # [CR-F3] Disable admin button for visual consistency while modal is open
        self.app.session_panel.admin_button.configure(state="disabled")
        # [E9-S3] Forward initial_tab nếu có trong event data
        initial_tab = data.get('initial_tab') if data else None
        # Tạo AdminWindow — modal (grab_set + transient trong constructor)
        self._admin_window = AdminWindow(
            self.app, self.class_mgr, self.student_mgr, self.db,
            initial_tab=initial_tab
        )
        # Override protocol để Presenter kiểm soát lifecycle
        self._admin_window.protocol("WM_DELETE_WINDOW", self._on_admin_closed)

    def _on_admin_closed(self):
        """Handler khi AdminWindow đóng — reload + resume (AC#6).

        [F7/F9-fix]: Set _current_mode = 1 sau khi resume.
        [F10-fix]: Clear _pending_class_id để tránh stale state.
        [A2-fix]: Check camera alive trước khi resume scanning.
        [CR-F1]: Clear _current_teacher_id — teacher may have been deleted in admin.
        [CR-F3]: Re-enable admin button.
        [CR-F4]: Guard winfo_exists() — app may have been destroyed while admin open.
        [CR2-F1]: Reset session panel on camera-dead path.
        [CR2-F5]: Only re-enable admin button when camera alive.
        [CR2-F8]: Move _load_teacher_encodings inside camera-alive branch.
        """
        if self._admin_window:
            try:
                self._admin_window.grab_release()
            except Exception:
                pass
            self._admin_window.destroy()
            self._admin_window = None
        # [F10-fix] Clear stale pending state
        self._pending_class_id = None
        # [CR-F1] Clear stale teacher state — teacher may have been deleted in admin
        self._current_teacher_id = None
        # [CR-F4] Guard: app may have been destroyed while admin was open
        if not self.app.winfo_exists():
            self._current_mode = None
            return
        # [A2-fix] Only resume if camera still alive
        if self.camera.is_opened():
            # [CR-F3] Re-enable admin button
            self.app.session_panel.admin_button.configure(state="normal")
            # [CR2-F8] Reload teacher encodings only when camera alive (avoid wasted DB call)
            self._load_teacher_encodings()
            self.worker.start_scanning(mode=1)
            # [F7/F9-fix] Restore mode — without this, mode guards reject all events
            self._current_mode = 1
        else:
            # [CR2-F1] Reset session panel — clear stale teacher info/buttons
            self.app.session_panel.reset()
            # [CR-F2] Camera died while admin was open — go idle with notification
            logger.warning("Camera ngắt kết nối khi admin đang mở — chuyển idle.")
            self.app.after(
                0, lambda: self.app.session_panel.info_label.configure(
                    text="⚠️ Camera ngắt kết nối"
                )
            )
            self._current_mode = None

    # ──────────────────────────────────────────────────────────
    # POST-SESSION NOTIFICATION (E9-S3)
    # ──────────────────────────────────────────────────────────

    @staticmethod
    def _compute_attendance_summary(result):
        """Tính present_count, total, pct từ result dict — DRY helper."""
        present = result.get('present', []) or []
        absent = result.get('absent', []) or []
        present_count = len(present)
        total = present_count + len(absent)
        pct = (present_count / total * 100) if total > 0 else 0
        return present_count, total, pct

    # ──────────────────────────────────────────────────────────
    # ──────────────────────────────────────────────────────────

    def _show_post_session_popup(self, filepath, result):
        """Hiển thị popup thông báo sau session — NON-BLOCKING.

        Tạo CTkToplevel với summary + filepath + 3 nút action.
        Popup dùng transient() nhưng KHÔNG grab_set() — non-blocking.
        """
        import customtkinter as ctk  # Lazy import — main.py không import ctk ở top-level

        # Guard: app phải còn sống
        if not self.app.winfo_exists():
            return
        # Guard: tránh duplicate popup
        if self._post_session_popup is not None:
            return

        # Tính summary
        present_count, total, pct = self._compute_attendance_summary(result)

        popup = ctk.CTkToplevel(self.app)
        popup.title("✅ Kết thúc phiên điểm danh")
        popup.geometry("480x250")
        popup.transient(self.app)
        # ⚠️ KHÔNG grab_set() — non-blocking popup

        # Summary
        ctk.CTkLabel(popup, text=f"Có mặt {present_count}/{total} ({pct:.1f}%)",
                     font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(15, 5))

        # Filepath
        ctk.CTkLabel(popup, text=f"📄 {filepath}", wraplength=440,
                     text_color="gray", font=ctk.CTkFont(size=12)).pack(pady=5, padx=20)

        # Buttons frame
        bf = ctk.CTkFrame(popup, fg_color="transparent")
        bf.pack(pady=15)

        ctk.CTkButton(bf, text="📂 Mở file", width=120,
                      command=lambda: self._open_file(filepath)).pack(side="left", padx=8)
        ctk.CTkButton(bf, text="📋 Xem lịch sử", width=120,
                      command=lambda: self._on_view_history_from_popup()).pack(side="left", padx=8)
        ctk.CTkButton(bf, text="Đóng", width=80,
                      command=lambda: self._close_post_session_popup()).pack(side="left", padx=8)

        self._post_session_popup = popup

    def _open_file(self, filepath):
        """Mở file bằng ứng dụng mặc định — cross-platform.

        [CR-F1] Hiển thị error trên popup hoặc student_panel nếu fail (AC2).
        [CR-F6] AttributeError guard cho os.startfile trên non-Windows.
        """
        try:
            if sys.platform == 'darwin':
                subprocess.Popen(['open', filepath])
            elif sys.platform == 'win32':
                os.startfile(filepath)
            else:
                subprocess.Popen(['xdg-open', filepath])
        except (OSError, FileNotFoundError, AttributeError) as e:
            logger.error(f"Không thể mở file: {e}")
            # [CR-F1] Hiển thị error cho user — AC2 yêu cầu feedback trên popup
            error_msg = f"❌ Không thể mở file: {e}"
            if (self._post_session_popup is not None
                    and self._post_session_popup.winfo_exists()):
                try:
                    import customtkinter as ctk
                    ctk.CTkLabel(
                        self._post_session_popup, text=error_msg,
                        text_color="red", font=ctk.CTkFont(size=12)
                    ).pack(pady=2)
                except Exception:
                    pass
            else:
                self.app.after(
                    0, self.app.student_panel.on_error, error_msg
                )

    def _close_post_session_popup(self):
        """Destroy popup nếu còn mở — winfo_exists() guard."""
        if self._post_session_popup is not None:
            try:
                if self._post_session_popup.winfo_exists():
                    self._post_session_popup.destroy()
            except Exception:
                pass
            self._post_session_popup = None

    def _on_view_history_from_popup(self):
        """Callback: đóng popup + mở Admin tab Lịch sử."""
        self._close_post_session_popup()
        self._open_admin_history()

    def _open_admin_history(self):
        """Mở AdminWindow trực tiếp ở tab Lịch sử — bypass mode guard.

        Khác _on_admin_requested(): không check mode, không disable admin_button
        (vì admin_button đã disabled ở SESSION_ENDED state).
        """
        if not self.app.winfo_exists():
            return
        if self._admin_window is not None:
            return
        # pause_scanning() là idempotent — an toàn gọi kể cả khi worker đã paused
        # (session vừa end → worker đã paused; nhưng nếu _reset_to_teacher_mode đã chạy
        # → worker đang scanning mode=1 → cần pause lại)
        self.worker.pause_scanning()
        # [CR-F4] Neutralize mode — prevent stale TEACHER_DETECTED events
        # from being processed while AdminWindow is open (mirrors _on_admin_requested)
        self._current_mode = None
        self._admin_window = AdminWindow(
            self.app, self.class_mgr, self.student_mgr, self.db,
            initial_tab="📋 Lịch sử"
        )
        self._admin_window.protocol("WM_DELETE_WINDOW", self._on_admin_closed)

    # ──────────────────────────────────────────────────────────
    # RUN
    # ──────────────────────────────────────────────────────────

    def run(self):
        """[F1-fix] Start worker thread, camera, và GUI mainloop.

        worker.start() PHẢI gọi trước start_scanning() để thread chạy loop.
        """
        self.worker.start()           # Thread.start() — PHẢI gọi trước start_scanning()
        self.camera.start()
        self._load_teacher_encodings()
        self.worker.start_scanning(mode=1)
        self._current_mode = 1
        self.app.camera_panel.start_preview()
        self.app.mainloop()


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    )
    presenter = Presenter()
    presenter.run()
