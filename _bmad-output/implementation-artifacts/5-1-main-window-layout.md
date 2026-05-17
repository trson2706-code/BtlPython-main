# Story 5.1: main-window-layout

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user (teacher/admin),
I want a unified main application window mapped out in 4 panels using CustomTkinter with Dark Mode,
so that I can seamlessly view the camera, manage the current attendance session, track the attendance list, and manage students all from one organized interface using the Vietnamese language.

## Acceptance Criteria

1. **Main Application Module**: `src/gui/app.py` is created with a main application class extending `customtkinter.CTk`.
2. **Framework & Theme**: Must use `CustomTkinter` configured with a Dark theme by default and display in Vietnamese.
3. **Window Properties**: The window has a clear title `📚 HỆ THỐNG ĐIỂM DANH SINH VIÊN` and a reasonable minimum size (e.g., 1200x800) to fit all panels comfortably.
4. **4-Panel Layout Strategy**: The main window uses a well-structured layout (e.g., Grid) split into 4 distinct quadrants:
   - Top-Left: Camera Panel placeholder
   - Top-Right: Session Panel placeholder
   - Bottom-Left: Attendance Panel placeholder
   - Bottom-Right: Student Panel placeholder
5. **Responsive Design**: The panels must dynamically resize correctly when the main window is maximized or resized via explicit structural ratios (e.g. Left column 60% and Right column 40%) using grid `weight` configurations.
6. **Graceful Shutdown**: Clicking the window's close (X) button or using keyboard shortcuts (`Command+Q` on macOS) triggers a non-destructive shutdown event (`AppEvent.SHUTDOWN_REQUESTED`). The UI will block and wait for the overarching Presenter controller to clean up threads and issue a final exit/destroy command.

## Tasks / Subtasks

- [x] Tạo module `src/gui/app.py`.
  - [x] Khai báo class `App(customtkinter.CTk)`.
  - [x] Set title: "📚 HỆ THỐNG ĐIỂM DANH SINH VIÊN".
  - [x] Cấu hình chiều dài x chiều rộng khởi tạo (ví dụ: 1280x720) và `minsize`.
- [x] Cấu hình CustomTkinter Theme.
  - [x] Gọi `customtkinter.set_appearance_mode("dark")`.
  - [x] Gọi `customtkinter.set_default_color_theme("blue")` hoặc màu phù hợp.
- [x] Thiết kế Layout 4 Panels.
  - [x] Sử dụng `grid` layout chia màn hình thành 2 hàng, 2 cột tương ứng với 4 quadrants (2x2).
  - [x] Đặt `grid_columnconfigure(0, weight=6)` và `grid_columnconfigure(1, weight=4)` (tỷ lệ 60-40), cũng như cấu hình row weight để chiều dọc co giãn phù hợp.
  - [x] Khởi tạo 4 frame (`CTkFrame`) rỗng (placeholder) đại diện cho: `camera_frame`, `session_frame`, `attendance_frame`, và `student_frame`.
- [x] Tích hợp graceful shutdown trong UI.
  - [x] Bắt sự kiện `protocol("WM_DELETE_WINDOW", self.on_closing)`.
  - [x] Thêm fallback phím tắt: `self.bind("<Command-q>", lambda e: self.on_closing())`.
  - [x] Hàm `on_closing` gửi `AppEvent.SHUTDOWN_REQUESTED` (sử dụng `src.core.events.emit`) và **không** gọi ngay `self.destroy()`. Main Presenter sẽ lo việc dọn dẹp camera/worker thread rồi gọi callback tắt app.

## Dev Notes & Architecture Constraints

- **MVP Pattern Constraint**: The View layer (`src/gui`) must be "dumb". It should not import directly from `src.core.database` or `src.core.recognition`. All complex logic triggers MUST go through the central Event system (`src.core.events`). This story focuses purely on the container UI.
- **CustomTkinter Grid**: Use `grid` heavily for dividing the window into exactly 4 areas. Left side column index 0 (camera/attendance) takes `weight=6`, right side column index 1 takes `weight=4`. Ensure it's responsive.
- **Placeholders**: For this story, just create the structural frames (e.g., `CTkFrame` with a test label like "Camera Panel") so the subsequent stories (5-2, 5-3) can just pass these frames to their own specific UI panel classes.
- **Language**: All text, titles, placeholders must be strictly in Vietnamese.
- **Graceful Shutdown (Deferred Destroy)**: Emitting `AppEvent.SHUTDOWN_REQUESTED` ensures Presenter (`src/main.py`) can stop the background loops and threads safely before destroying the tkinter main loop. Do not call `destroy()` in `app.py` prematurely.

### Project Structure Notes

- **File thêm**: `src/gui/app.py`
- Tuân thủ cấu trúc của package `src/gui`. Giữ file gọn gàng, chứa code của cửa sổ gốc chứa các thành phần.

### References

- [Docs: Lịch sử thảo luận](file:///Users/huynguyen/work/projects/BtlPython/docs/lich-su-thao-luan.md)
  (Section 11: GUI Design)

## Dev Agent Record

### Agent Model Used
Gemini 3.1 Pro (High)

### Debug Log References

### Completion Notes List
- Completed App class in `src/gui/app.py` with customtkinter Dark theme and layout setup.
- Added 4 placeholder panels (`camera_frame`, `session_frame`, `attendance_frame`, `student_frame`) mapped to grid with weights 60-40 correctly.
- Added `EventType.SHUTDOWN_REQUESTED` to `src/core/events.py`.
- Integrated graceful shutdown flow capturing WM_DELETE_WINDOW and `Command-Q` properly emitting shutdown signal without calling `destroy()`.
- Wrote pytest tests in `tests/test_gui_app.py` that passed successfully and regression tests show no errors.

#### Code Review Fixes (2026-04-22)
- [H1] Tạo `src/gui/__init__.py` — thiếu package init file.
- [H2] Đổi placeholder labels sang Tiếng Việt ("Bảng Camera", "Bảng Phiên Điểm Danh", v.v.).
- [H3] Di chuyển `set_appearance_mode`/`set_default_color_theme` ra module-level (trước `super().__init__()`).
- [M1] Sửa `geometry("1280x800")` cho khớp với `minsize(1200, 800)`.
- [M2] Thêm `_closing` guard flag chống duplicate shutdown events.
- [M3] Refactor tests dùng pytest fixture để đảm bảo cleanup.
- [M4] Đổi `assert_called_once()` thành `assert_called_once_with(None)` cho precision.
- Thêm test `test_shutdown_event_only_fires_once` verify M2 guard.

#### Party Mode Review Fixes (2026-04-28)
- [H-PM1] `EventManager` thread-safety — thêm `threading.Lock`, emit dùng snapshot copy listener list.
- [M-PM2] `__main__` block trong View — thêm warning log + tự subscribe destroy handler để tránh treo app.
- [M-PM3] Cross-platform shortcut — thêm `<Control-q>` binding bên cạnh `<Command-q>`.
- [M-PM4] Test gaps — thêm 4 tests: `test_grid_row_weights`, `test_wm_delete_window_protocol_bound`, `test_keyboard_shortcuts_bound`, `test_event_manager_thread_safety`.
- [L-PM5] Sprint status YAML summary — cập nhật `completed: 9`, `progress_percent: 60`.

### File List
- `src/gui/__init__.py`
- `src/gui/app.py`
- `src/core/events.py`
- `tests/test_gui_app.py`

