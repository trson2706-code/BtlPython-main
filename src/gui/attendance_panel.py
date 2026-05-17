"""Attendance Panel — Bảng điểm danh sinh viên real-time.

View layer thuần túy (MVP pattern):
- KHÔNG import từ src.core ngoại trừ src.core.events
- Nhận data qua public methods (gọi bởi Presenter)
- Hiển thị danh sách điểm danh scrollable + thống kê
- Session lifecycle: on_session_started → add_record → on_session_ended
"""

import logging
import customtkinter as ctk

logger = logging.getLogger(__name__)


class AttendancePanel(ctk.CTkFrame):
    """Panel hiển thị danh sách điểm danh sinh viên real-time.

    Hiển thị scrollable list với mỗi dòng: tên SV, MSSV, giờ điểm danh,
    trạng thái (✅ Có mặt / ❌ Vắng). Thống kê tổng cập nhật real-time.

    Args:
        master: Parent widget (CTk hoặc CTkFrame)
    """

    def __init__(self, master):
        super().__init__(master)
        self._records = {}          # dict[int, dict] — student_id → row widget refs
        #   key: student_id (int)
        #   value: {'status_label': CTkLabel, 'time_label': CTkLabel,
        #           'row_frame': CTkFrame, 'is_present': bool}
        self._total_students = 0
        self._present_count = 0
        self._session_active = False

        # ── Header label ──
        self.header_label = ctk.CTkLabel(
            self,
            text="📋 BẢNG ĐIỂM DANH",
            font=ctk.CTkFont(size=18, weight="bold"),
        )
        self.header_label.pack(pady=(10, 5))

        # ── Stats label ──
        self.stats_label = ctk.CTkLabel(
            self,
            text="Có mặt 0/0 (0%)",
            font=ctk.CTkFont(size=14),
        )
        self.stats_label.pack(pady=(0, 5))

        # ── Scrollable frame cho danh sách SV ──
        self._scroll_frame = ctk.CTkScrollableFrame(self)
        self._scroll_frame.pack(expand=True, fill="both", padx=5, pady=5)

        # ── Placeholder label ──
        self._placeholder_label = ctk.CTkLabel(
            self._scroll_frame,
            text="Chưa có phiên điểm danh",
            font=ctk.CTkFont(size=14),
            text_color="gray",
        )
        self._placeholder_label.pack(expand=True, pady=20)

    # ── Public API (gọi bởi Presenter từ main thread) ──

    def on_session_started(self, data: dict):
        """Nhận enriched session data từ Presenter, render danh sách SV ban đầu.

        Gọi reset() trước để xóa session cũ. Render tất cả SV với ❌ Vắng.

        Args:
            data: {'class_id': int, 'students': [{'student_id', 'name', 'student_code'}, ...]}
        """
        if not self.winfo_exists():
            return

        self.reset()
        self._session_active = True

        # Ẩn placeholder
        self._placeholder_label.pack_forget()

        students = data.get('students', [])

        for student in students:
            student_id = student.get('student_id')
            if student_id is None:
                continue
            self._create_attendance_row(self._scroll_frame, student)

        # Architect-1 FIX: đếm chỉ students hợp lệ (có student_id) — tránh semantic mismatch
        self._total_students = len(self._records)

        self._update_stats()
        logger.info("Session started — %d sinh viên loaded", self._total_students)

    def add_record(self, data: dict):
        """Cập nhật dòng SV từ ❌ → ✅ khi điểm danh thành công.

        Guards: skip nếu student_id đã ✅, session inactive, hoặc student_id
        không có trong _records.

        Args:
            data: {'student_id': int, 'name': str, 'student_code': str,
                   'confidence': float, 'mark_time': str}
        """
        if not self._session_active:
            logger.debug("add_record() skipped — session inactive")
            return

        student_id = data.get('student_id')
        if student_id is None:
            return

        if student_id not in self._records:
            logger.debug("add_record() skipped — student_id %s not in records", student_id)
            return

        record = self._records[student_id]

        # Idempotency guard: skip nếu đã ✅
        if record['is_present']:
            logger.debug("add_record() skipped — student_id %s already present", student_id)
            return

        # Widget lifecycle guard
        if not self.winfo_exists():
            return

        # Cập nhật trạng thái
        mark_time = data.get('mark_time', '')
        try:
            record['status_label'].configure(text="✅ Có mặt")
            record['time_label'].configure(text=mark_time)
        except Exception:
            # Widget đã bị destroy
            logger.debug("add_record() — widget destroyed for student_id %s", student_id)
            return

        record['is_present'] = True
        self._present_count += 1
        self._update_stats()

    def on_session_ended(self, data: dict):
        """Freeze danh sách khi session kết thúc.

        Chỉ set _session_active = False. KHÔNG cần re-render hay format datetime.
        Data đã hiển thị real-time qua add_record().

        Args:
            data: {'class_id', 'start_time', 'end_time', 'present', 'absent'}
        """
        if not self.winfo_exists():
            return

        self._session_active = False
        # Cập nhật stats label thành "KẾT THÚC" — dùng _calc_percentage() tránh DRY
        pct = self._calc_percentage()
        self.stats_label.configure(
            text=f"KẾT THÚC — Có mặt {self._present_count}/{self._total_students} ({pct}%)"
        )
        logger.info("Session ended — %d/%d present", self._present_count, self._total_students)

    def reset(self):
        """Reset toàn bộ panel — destroy widgets, xóa records, hiển thị placeholder."""
        # Destroy tất cả row widgets (tránh memory leak)
        for student_id, record in self._records.items():
            try:
                record['row_frame'].destroy()
            except Exception:
                pass

        self._records.clear()
        self._total_students = 0
        self._present_count = 0
        self._session_active = False

        # Hiển thị lại placeholder + reset stats (guard widget lifecycle)
        if self.winfo_exists():
            self._placeholder_label.pack(expand=True, pady=20)
            self._update_stats()

    # ── Private methods ──

    def _create_attendance_row(self, parent, student_data):
        """Tạo row frame cho 1 sinh viên trong danh sách điểm danh.

        Args:
            parent: CTkScrollableFrame parent
            student_data: {'student_id': int, 'name': str, 'student_code': str}

        Returns:
            CTkFrame: Row frame đã tạo
        """
        student_id = student_data.get('student_id')
        name = student_data.get('name', '')
        student_code = student_data.get('student_code', '')

        row = ctk.CTkFrame(parent)
        row.pack(fill="x", padx=2, pady=1)

        # Tên SV
        ctk.CTkLabel(row, text=name, width=120, anchor="w").pack(side="left", padx=5)

        # MSSV
        ctk.CTkLabel(row, text=student_code, width=80).pack(side="left", padx=5)

        # Giờ điểm danh (trống mặc định)
        time_label = ctk.CTkLabel(row, text="", width=60)
        time_label.pack(side="left", padx=5)

        # Trạng thái (mặc định ❌ Vắng)
        status_label = ctk.CTkLabel(row, text="❌ Vắng", width=80)
        status_label.pack(side="left", padx=5)

        # Lưu refs vào _records
        self._records[student_id] = {
            'status_label': status_label,
            'time_label': time_label,
            'row_frame': row,
            'is_present': False,
        }

    def _calc_percentage(self) -> int:
        """Tính phần trăm có mặt, tránh ZeroDivisionError."""
        if self._total_students == 0:
            return 0
        return int(self._present_count / self._total_students * 100)

    def _update_stats(self):
        """Cập nhật stats label với thống kê Có mặt X/Y (Z%)."""
        pct = self._calc_percentage()
        self.stats_label.configure(
            text=f"Có mặt {self._present_count}/{self._total_students} ({pct}%)"
        )
