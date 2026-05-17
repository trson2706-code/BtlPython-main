import customtkinter as ctk
from src.core.events import events, EventType
from src.gui.camera_panel import CameraPanel
from src.gui.session_panel import SessionPanel
from src.gui.attendance_panel import AttendancePanel
from src.gui.student_panel import StudentPanel

# H3 Fix: Cấu hình theme TRƯỚC khi tạo bất kỳ widget nào
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class App(ctk.CTk):
    """Cửa sổ chính của ứng dụng điểm danh sinh viên.
    
    Thiết lập layout 4 panel (2x2 grid) với tỷ lệ cột 60/40,
    sử dụng CustomTkinter Dark theme và ngôn ngữ Tiếng Việt.
    """

    def __init__(self):
        super().__init__()
        
        # M2 Fix: Guard flag chống gọi on_closing nhiều lần
        self._closing = False
        
        # Configure Window
        self.title("📚 HỆ THỐNG ĐIỂM DANH SINH VIÊN")
        # M1 Fix: geometry khởi tạo phải >= minsize (1200x800)
        self.geometry("1280x800")
        self.minsize(1200, 800)
        
        # Configure Grid Layout (4 Panels, 2x2 grid)
        # column 0 has weight 6, column 1 has weight 4
        self.grid_columnconfigure(0, weight=6)
        self.grid_columnconfigure(1, weight=4)
        
        # row weights for proportional vertical layout
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # Panel Camera (story 5-2)
        self.camera_panel = CameraPanel(self)
        self.camera_panel.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        
        # Panel Session (story 5-2)
        self.session_panel = SessionPanel(self)
        self.session_panel.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        
        # Panel Attendance (story 5-3)
        self.attendance_panel = AttendancePanel(self)
        self.attendance_panel.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
        
        # Panel Student (story 5-3)
        self.student_panel = StudentPanel(self)
        self.student_panel.grid(row=1, column=1, padx=10, pady=10, sticky="nsew")
        
        # Graceful Shutdown integration
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.bind("<Command-q>", lambda e: self.on_closing())
        self.bind("<Control-q>", lambda e: self.on_closing())

    def on_closing(self):
        """Xử lý sự kiện đóng cửa sổ.
        
        Gửi event SHUTDOWN_REQUESTED để Presenter dọn dẹp resources.
        Không gọi self.destroy() — Presenter sẽ xử lý việc tắt app.
        """
        # M2 Fix: Guard chống duplicate shutdown events
        if self._closing:
            return
        self._closing = True
        events.emit(EventType.SHUTDOWN_REQUESTED)


if __name__ == "__main__":
    # ⚠️ DEBUG ONLY — Chạy trực tiếp không có Presenter.
    # Shutdown event sẽ không được xử lý → tự destroy để tránh treo app.
    import logging
    logging.basicConfig(level=logging.WARNING)
    logging.warning(
        "Chạy app.py trực tiếp (không có Presenter). "
        "Shutdown event sẽ tự gọi destroy() thay vì chờ Presenter."
    )
    app = App()
    events.subscribe(
        EventType.SHUTDOWN_REQUESTED,
        lambda _: app.after(0, app.destroy)
    )
    app.mainloop()
