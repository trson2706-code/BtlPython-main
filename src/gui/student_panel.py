"""Student Panel — Hiển thị danh sách điểm danh + điểm danh thủ công.

View layer thuần túy (MVP pattern):
- KHÔNG import từ src.core ngoại trừ src.core.events
- Emit events (MANUAL_MARK_REQUESTED, EXCEL_EXPORT_REQUESTED)
- Nhận data qua public methods (gọi bởi Presenter)
- Hiển thị danh sách SV: Có mặt / Vắng + nút điểm danh thủ công
"""

import logging
import customtkinter as ctk
from src.core.events import events, EventType

logger = logging.getLogger(__name__)


class StudentPanel(ctk.CTkFrame):
    """Panel hiển thị trạng thái điểm danh sinh viên + hỗ trợ điểm danh thủ công.

    Khi session active: hiển thị danh sách SV với trạng thái Có mặt / Vắng.
    SV vắng có nút "Điểm danh" để GV bấm điểm danh thủ công (backup khi hệ thống lỗi).

    Args:
        master: Parent widget (CTk hoặc CTkFrame)
    """

    def __init__(self, master):
        super().__init__(master)
        self._student_widgets = {}  # dict[int, dict] — student_id → row widget refs
        self._students_data = {}    # dict[int, dict] — student_id → student info
        self._has_session_data = False

        # ── Header label ──
        self.header_label = ctk.CTkLabel(
            self,
            text="👨‍🎓 DANH SÁCH SINH VIÊN",
            font=ctk.CTkFont(size=18, weight="bold"),
        )
        self.header_label.pack(pady=(10, 5))

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

        # ── Button frame ──
        self._button_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._button_frame.pack(fill="x", padx=5, pady=5)

        # Nút Điểm danh thủ công (hiển thị dialog danh sách)
        self.manual_button = ctk.CTkButton(
            self._button_frame,
            text="📋 Điểm danh",
            font=ctk.CTkFont(size=14),
            state="disabled",
            command=self._show_attendance_dialog,
        )
        self.manual_button.pack(side="left", padx=5)

        # Nút Xuất Excel (disabled mặc định)
        self.export_button = ctk.CTkButton(
            self._button_frame,
            text="📊 Xuất Excel",
            font=ctk.CTkFont(size=14),
            state="disabled",
            command=self._on_export_click,
        )
        self.export_button.pack(side="right", padx=5)

        # ── Info label cho thông báo ──
        self.info_label = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(size=12),
            text_color="orange",
        )
        self.info_label.pack(pady=(0, 5))

    # ── Public API (gọi bởi Presenter từ main thread) ──

    def on_students_loaded(self, students: list):
        """Nhận danh sách SV từ Presenter và render.

        Args:
            students: [{'student_id': int, 'name': str, 'student_code': str}, ...]
        """
        if not self.winfo_exists():
            return

        self._clear_list()

        if not students:
            self._placeholder_label.pack(expand=True, pady=20)
            logger.info("on_students_loaded() — empty list, placeholder shown")
            return

        # Ẩn placeholder
        self._placeholder_label.pack_forget()

        for student in students:
            student_id = student.get('student_id')
            if student_id is None:
                continue
            self._students_data[student_id] = student
            self._create_student_row(self._scroll_frame, student)

        self._has_session_data = True
        self.export_button.configure(state="normal")
        self.manual_button.configure(state="normal")
        logger.info("Students loaded — %d sinh viên", len(students))

    def on_student_marked(self, data: dict):
        """Cập nhật trạng thái SV từ ❌ → ✅ khi điểm danh thành công.

        Args:
            data: {'student_id': int, 'name': str, 'mark_time': str}
        """
        if not self.winfo_exists():
            return

        student_id = data.get('student_id')
        if student_id is None or student_id not in self._student_widgets:
            return

        record = self._student_widgets[student_id]
        if record.get('is_present'):
            return  # Đã điểm danh rồi

        mark_time = data.get('mark_time', '')
        try:
            record['status_label'].configure(text="✅ Có mặt", text_color="#28A745")
            record['time_label'].configure(text=mark_time)
            # Ẩn nút điểm danh thủ công
            if record.get('mark_button'):
                record['mark_button'].pack_forget()
        except Exception:
            return

        record['is_present'] = True

    def on_error(self, message: str, color: str = "orange"):
        """Hiển thị thông báo tạm thời (tự xóa sau 5 giây)."""
        if not self.winfo_exists():
            return

        self.info_label.configure(text=message, text_color=color)
        logger.warning("Student panel error: %s", message)

        def _clear_error():
            if self.winfo_exists():
                self.info_label.configure(text="")

        self.after(5000, _clear_error)

    def reset(self):
        """Reset toàn bộ panel — clear list, disable buttons, hiển thị placeholder."""
        self._clear_list()
        self._has_session_data = False
        self._students_data.clear()
        if self.winfo_exists():
            self.export_button.configure(state="disabled")
            self.manual_button.configure(state="disabled")
            self._placeholder_label.pack(expand=True, pady=20)
            self.info_label.configure(text="")

    # ── Private methods ──

    def _create_student_row(self, parent, student_data):
        """Tạo row cho 1 SV: tên, MSSV, giờ, trạng thái, nút điểm danh thủ công."""
        student_id = student_data.get('student_id')
        name = student_data.get('name', '')
        student_code = student_data.get('student_code', '')

        row = ctk.CTkFrame(parent)
        row.pack(fill="x", padx=2, pady=1)

        ctk.CTkLabel(row, text=name, width=120, anchor="w").pack(side="left", padx=5)
        ctk.CTkLabel(row, text=student_code, width=80).pack(side="left", padx=5)

        time_label = ctk.CTkLabel(row, text="", width=60)
        time_label.pack(side="left", padx=5)

        status_label = ctk.CTkLabel(row, text="❌ Vắng", width=80, text_color="#DC3545")
        status_label.pack(side="left", padx=5)

        # Nút điểm danh thủ công (inline)
        mark_btn = ctk.CTkButton(
            row,
            text="✋",
            width=30,
            height=28,
            fg_color="#FFC107",
            hover_color="#E0A800",
            text_color="black",
            command=lambda sid=student_id: self._on_manual_mark(sid),
        )
        mark_btn.pack(side="right", padx=5)

        self._student_widgets[student_id] = {
            'status_label': status_label,
            'time_label': time_label,
            'row_frame': row,
            'mark_button': mark_btn,
            'is_present': False,
        }

    def _clear_list(self):
        """Destroy tất cả row widgets."""
        for student_id, record in self._student_widgets.items():
            try:
                record['row_frame'].destroy()
            except Exception:
                pass
        self._student_widgets.clear()

    def _on_export_click(self):
        """Emit EXCEL_EXPORT_REQUESTED."""
        events.emit(EventType.EXCEL_EXPORT_REQUESTED, {})

    def _on_manual_mark(self, student_id: int):
        """Emit MANUAL_MARK_REQUESTED khi GV bấm điểm danh thủ công."""
        events.emit(EventType.MANUAL_MARK_REQUESTED, {'student_id': student_id})

    def _show_attendance_dialog(self):
        """Hiển thị dialog danh sách SV: Có mặt / Vắng, cho phép điểm danh thủ công."""
        if not self.winfo_exists():
            return

        dialog = ctk.CTkToplevel(self)
        dialog.title("📋 Danh sách điểm danh")
        dialog.geometry("500x500")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        dialog.protocol("WM_DELETE_WINDOW", lambda: self._safe_close(dialog))

        # ── Thống kê ──
        present_count = sum(1 for r in self._student_widgets.values() if r['is_present'])
        total = len(self._student_widgets)
        absent_count = total - present_count

        stats_frame = ctk.CTkFrame(dialog)
        stats_frame.pack(fill="x", padx=10, pady=(10, 5))

        ctk.CTkLabel(
            stats_frame,
            text=f"✅ Có mặt: {present_count}  |  ❌ Vắng: {absent_count}  |  Tổng: {total}",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(pady=8)

        # ── Tab: Vắng / Có mặt ──
        tabview = ctk.CTkTabview(dialog)
        tabview.pack(expand=True, fill="both", padx=10, pady=5)
        tabview.add("❌ Chưa điểm danh")
        tabview.add("✅ Đã điểm danh")

        # ── Tab Vắng: SV chưa điểm danh + nút điểm danh thủ công ──
        absent_scroll = ctk.CTkScrollableFrame(tabview.tab("❌ Chưa điểm danh"))
        absent_scroll.pack(expand=True, fill="both", padx=2, pady=2)

        absent_found = False
        for sid, record in self._student_widgets.items():
            if not record['is_present']:
                absent_found = True
                info = self._students_data.get(sid, {})
                row = ctk.CTkFrame(absent_scroll)
                row.pack(fill="x", padx=2, pady=1)
                ctk.CTkLabel(row, text=info.get('name', ''), width=150, anchor="w").pack(side="left", padx=5)
                ctk.CTkLabel(row, text=info.get('student_code', ''), width=100).pack(side="left", padx=5)
                ctk.CTkButton(
                    row,
                    text="✋ Điểm danh",
                    width=100,
                    height=28,
                    fg_color="#FFC107",
                    hover_color="#E0A800",
                    text_color="black",
                    command=lambda s=sid, d=dialog: self._manual_mark_from_dialog(s, d),
                ).pack(side="right", padx=5)

        if not absent_found:
            ctk.CTkLabel(
                absent_scroll,
                text="🎉 Tất cả sinh viên đã điểm danh!",
                text_color="gray",
                font=ctk.CTkFont(size=14),
            ).pack(pady=20)

        # ── Tab Có mặt: SV đã điểm danh ──
        present_scroll = ctk.CTkScrollableFrame(tabview.tab("✅ Đã điểm danh"))
        present_scroll.pack(expand=True, fill="both", padx=2, pady=2)

        present_found = False
        for sid, record in self._student_widgets.items():
            if record['is_present']:
                present_found = True
                info = self._students_data.get(sid, {})
                row = ctk.CTkFrame(present_scroll)
                row.pack(fill="x", padx=2, pady=1)
                ctk.CTkLabel(row, text=info.get('name', ''), width=150, anchor="w").pack(side="left", padx=5)
                ctk.CTkLabel(row, text=info.get('student_code', ''), width=100).pack(side="left", padx=5)
                time_text = ""
                try:
                    time_text = record['time_label'].cget("text")
                except Exception:
                    pass
                ctk.CTkLabel(row, text=f"⏰ {time_text}", width=80, text_color="gray").pack(side="right", padx=5)

        if not present_found:
            ctk.CTkLabel(
                present_scroll,
                text="Chưa có sinh viên nào điểm danh.",
                text_color="gray",
                font=ctk.CTkFont(size=14),
            ).pack(pady=20)

        # Nút đóng
        ctk.CTkButton(
            dialog,
            text="Đóng",
            command=lambda: self._safe_close(dialog),
        ).pack(pady=10)

    def _manual_mark_from_dialog(self, student_id: int, dialog):
        """Điểm danh thủ công từ dialog và đóng dialog để refresh."""
        events.emit(EventType.MANUAL_MARK_REQUESTED, {'student_id': student_id})
        # Đóng dialog — user mở lại sẽ thấy cập nhật
        self._safe_close(dialog)

    def _safe_close(self, dialog):
        """Defensive close dialog."""
        try:
            dialog.grab_release()
        except Exception:
            pass
        dialog.destroy()
