"""Session Control Panel — Quản lý trạng thái phiên điểm danh.

View layer thuần túy (MVP pattern):
- KHÔNG import từ src.core ngoại trừ src.core.events
- Nhận scan_time_minutes qua constructor (Presenter đọc config)
- Chỉ emit events (SESSION_CONFIRMED, SESSION_END_REQUESTED)
- Presenter điều phối toàn bộ flow
"""

import customtkinter as ctk
from src.core.events import events, EventType


class SessionPanel(ctk.CTkFrame):
    """Panel quản lý trạng thái phiên điểm danh.
    
    3 states: WAITING_TEACHER → ATTENDANCE_ACTIVE → SESSION_ENDED
    
    Args:
        master: Parent widget (CTk hoặc CTkFrame)
        scan_time_minutes: Thời gian điểm danh tính bằng phút (mặc định 60).
            Presenter đọc từ config và truyền giá trị.
    """

    # State constants
    WAITING_TEACHER = "waiting"
    ATTENDANCE_ACTIVE = "active"
    SESSION_ENDED = "ended"

    # Vietnamese labels cho mỗi state
    _STATE_LABELS = {
        WAITING_TEACHER: "⏳ CHỜ GIẢNG VIÊN",
        ATTENDANCE_ACTIVE: "📋 ĐANG ĐIỂM DANH",
        SESSION_ENDED: "✅ ĐÃ KẾT THÚC",
    }

    def __init__(self, master, scan_time_minutes: int = 60):
        super().__init__(master)
        self._scan_time_minutes = max(0, scan_time_minutes)  # L2: clamp negative
        self._state = self.WAITING_TEACHER
        self._remaining_seconds = 0
        self._timer_id = None

        # ── Status label (trạng thái phiên) ──
        self.status_label = ctk.CTkLabel(
            self,
            text=self._STATE_LABELS[self.WAITING_TEACHER],
            font=ctk.CTkFont(size=20, weight="bold"),
        )
        self.status_label.pack(pady=(20, 10))

        # ── Info label (tên GV/SV + class info) ──
        self.info_label = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(size=14),
            wraplength=350,
        )
        self.info_label.pack(pady=5)

        # ── Countdown label (MM:SS) ──
        self.countdown_label = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(size=28, weight="bold"),
        )
        self.countdown_label.pack(pady=10)

        # ── Nút Xác nhận ──
        self.confirm_button = ctk.CTkButton(
            self,
            text="✅ Xác nhận",
            font=ctk.CTkFont(size=14),
            state="disabled",
            command=self._on_confirm_click,
        )
        self.confirm_button.pack(pady=5)

        # ── Nút Kết thúc ──
        self.end_button = ctk.CTkButton(
            self,
            text="⏹ Kết thúc",
            font=ctk.CTkFont(size=14),
            state="disabled",
            fg_color="#DC3545",
            hover_color="#C82333",
            command=self._on_end_click,
        )
        self.end_button.pack(pady=5)

        # ── Nút Quản lý (Admin) ──
        self.admin_button = ctk.CTkButton(
            self,
            text="⚙️ Quản lý",
            font=ctk.CTkFont(size=14),
            state="normal",
            command=self._on_admin_click,
        )
        self.admin_button.pack(pady=5)

    # ── Public API (gọi bởi Presenter từ main thread) ──

    def on_teacher_detected(self, data: dict):
        """Nhận enriched TEACHER_DETECTED data từ Presenter.
        
        Args:
            data: {'person_id', 'name', 'teacher_code', 'class_info', 'confidence', 'coordinates'}
        """
        name = data.get('name', '')
        teacher_code = data.get('teacher_code', '')
        class_info = data.get('class_info', '')
        confidence = data.get('confidence', 0)

        info_text = (
            f"{name} ({teacher_code})\n"
            f"{class_info}\n"
            f"Độ chính xác: {confidence:.1f}%"
        )
        self.info_label.configure(text=info_text)
        self.confirm_button.configure(state="normal")

    def on_student_detected(self, data: dict):
        """Nhận enriched STUDENT_DETECTED data từ Presenter.
        
        Args:
            data: {'person_id', 'name', 'student_code', 'confidence', 'coordinates'}
        """
        name = data.get('name', '')
        student_code = data.get('student_code', '')
        confidence = data.get('confidence', 0)

        info_text = (
            f"👨‍🎓 {name} ({student_code})\n"
            f"✅ Có mặt — {confidence:.1f}%"
        )
        self.info_label.configure(text=info_text)

    def on_session_started(self, data: dict):
        """Chuyển sang state ATTENDANCE_ACTIVE + bắt đầu countdown.
        
        Args:
            data: {'class_id', 'start_time'}
        """
        # Q3: Guard chống duplicate call — tránh orphaned timer
        if self._state == self.ATTENDANCE_ACTIVE:
            return
        self._state = self.ATTENDANCE_ACTIVE
        self.status_label.configure(text=self._STATE_LABELS[self.ATTENDANCE_ACTIVE])
        self.confirm_button.configure(state="disabled")
        self.end_button.configure(state="normal")
        self.admin_button.configure(state="disabled")
        self._start_countdown()

    def on_session_ended(self, data: dict):
        """Chuyển sang state SESSION_ENDED + dừng timer.
        
        Args:
            data: dict (optional fields)
        """
        self._state = self.SESSION_ENDED
        self.status_label.configure(text=self._STATE_LABELS[self.SESSION_ENDED])
        self.confirm_button.configure(state="disabled")
        self.end_button.configure(state="disabled")
        self.admin_button.configure(state="disabled")
        self._stop_timer()

    def reset(self):
        """Reset về state WAITING_TEACHER — xóa thông tin, reset timer."""
        self._stop_timer()
        self._state = self.WAITING_TEACHER
        self._remaining_seconds = 0
        self.status_label.configure(text=self._STATE_LABELS[self.WAITING_TEACHER])
        self.info_label.configure(text="")
        self.countdown_label.configure(text="")
        self.confirm_button.configure(state="disabled")
        self.end_button.configure(state="disabled")
        self.admin_button.configure(state="normal")

    # ── Private methods ──

    def _on_confirm_click(self):
        """Emit SESSION_CONFIRMED khi GV bấm Xác nhận."""
        # D3: Emit empty dict thay vì None cho forward compatibility
        events.emit(EventType.SESSION_CONFIRMED, {})

    def _on_end_click(self):
        """Emit SESSION_END_REQUESTED khi GV bấm Kết thúc."""
        # D3: Emit empty dict thay vì None cho forward compatibility
        events.emit(EventType.SESSION_END_REQUESTED, {})

    def _on_admin_click(self):
        """Emit ADMIN_REQUESTED khi user bấm Quản lý."""
        events.emit(EventType.ADMIN_REQUESTED, {})

    def _start_countdown(self):
        """Bắt đầu đếm ngược từ scan_time_minutes."""
        self._remaining_seconds = self._scan_time_minutes * 60
        # D2: Hiển thị thời gian ban đầu trước khi schedule tick đầu tiên
        if self._remaining_seconds > 0:
            mins, secs = divmod(self._remaining_seconds, 60)
            self.countdown_label.configure(text=f"{mins:02d}:{secs:02d}")
            self._remaining_seconds -= 1
            self._timer_id = self.after(1000, self._tick_countdown)
        else:
            # scan_time_minutes = 0 → emit kết thúc lập tức
            self._tick_countdown()

    def _tick_countdown(self):
        """Giảm 1 giây, cập nhật label. Hết giờ → emit SESSION_END_REQUESTED."""
        if not self.winfo_exists():
            return

        # M4: State guard — không tick nếu session đã kết thúc
        if self._state != self.ATTENDANCE_ACTIVE:
            return

        if self._remaining_seconds <= 0:
            self.countdown_label.configure(text="00:00")
            events.emit(EventType.SESSION_END_REQUESTED, {})
            return

        mins, secs = divmod(self._remaining_seconds, 60)
        self.countdown_label.configure(text=f"{mins:02d}:{secs:02d}")
        self._remaining_seconds -= 1
        self._timer_id = self.after(1000, self._tick_countdown)

    def _stop_timer(self):
        """Cancel pending after timer."""
        if self._timer_id is not None:
            try:
                self.after_cancel(self._timer_id)
            except Exception:
                pass
            self._timer_id = None
