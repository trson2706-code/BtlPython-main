# Story 5.2: Panel Camera + Session

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a giảng viên (teacher),
I want a real-time camera preview panel with face detection bounding box and a session control panel with state transitions, confirmation buttons, and countdown timer,
so that I can see my face being scanned, confirm my identity to start an attendance session, monitor the countdown, and end the session — all with clear Vietnamese-language feedback.

## Acceptance Criteria

1. **Camera Panel** (`src/gui/camera_panel.py`): Hiển thị camera preview real-time ~30fps trong `CTkLabel` sử dụng `CTkImage` + PIL. Frame được lấy qua `get_frame_callback` (callable, trả về RGB numpy array hoặc None). Vẽ bounding box xanh lá (nhận diện thành công) hoặc đỏ (đang quét) lên frame trước khi hiển thị.
2. **Session Panel** (`src/gui/session_panel.py`): Hiển thị trạng thái phiên theo 3 state: `CHỜ GIẢNG VIÊN` → `ĐANG ĐIỂM DANH` → `ĐÃ KẾT THÚC`. Hiển thị tên GV/SV khi nhận diện được. Nút `[✅ Xác nhận]` chỉ hiển thị/enable khi GV đã được nhận diện. Nút `[⏹ Kết thúc]` chỉ hiển thị/enable trong trạng thái `ĐANG ĐIỂM DANH`.
3. **Đếm ngược**: Timer đếm ngược từ `60:00` → `00:00` hiển thị dạng `MM:SS`, tự động gọi kết thúc session khi hết giờ. Giá trị phút nhận qua constructor parameter `scan_time_minutes` (mặc định 60).
4. **Tích hợp Event System**: Tất cả giao tiếp giữa panel và core logic đều thông qua `EventManager` (`src.core.events`). Camera panel và session panel KHÔNG import từ `src.core.database`, `src.core.recognition`, `src.core.camera`, `src.core.worker`, hay `src.core.config`. Chỉ được import `src.core.events` (EventManager + EventType). Data nhận qua event callbacks hoặc constructor parameters.
5. **Tích hợp vào App**: Thay thế placeholder frames trong `src/gui/app.py` (`camera_frame`, `session_frame`) bằng instance của `CameraPanel` và `SessionPanel`. Các panel nhận parent frame làm master.
6. **Hiển thị nhận diện**: Presenter sẽ enrich event data trước khi forward tới panels. Khi nhận enriched `TEACHER_DETECTED` → session panel hiển thị tên GV + thông tin lớp/môn. Khi nhận enriched `STUDENT_DETECTED` → hiển thị tên SV + MSSV + trạng thái "✅ Có mặt". Camera panel nhận `coordinates` để vẽ bounding box.
7. **Ngôn ngữ**: Mọi text hiển thị phải bằng Tiếng Việt.
8. **Shutdown Handling**: Camera panel phải dừng preview (`stop_preview()`) khi app đóng. Presenter sẽ gọi `camera_panel.stop_preview()` trước khi destroy.

## Tasks / Subtasks

- [x] Tạo `src/gui/camera_panel.py` (AC: #1, #8)
  - [x] Class `CameraPanel(CTkFrame)` với constructor: `__init__(self, master, get_frame_callback: callable = None)`
  - [x] `CTkLabel` trung tâm để hiển thị video frame, fallback text "📷 Camera đang tắt"
  - [x] Method `start_preview()` — set `_running = True`, gọi `after(33, self._update_frame)` (~30fps)
  - [x] Method `stop_preview()` — set `_running = False`, cancel pending `after` via `after_cancel()`, xóa ảnh trên label
  - [x] Method `_update_frame()` — lấy frame qua `get_frame_callback`, `.copy()` frame trước khi vẽ bbox, convert sang `CTkImage` (wrap trong try-except), cập nhật label, gọi `_schedule_next()`
  - [x] Method `set_bounding_box(coords: dict, color: str)` — lưu coords `{'top','right','bottom','left'}` + color `"green"/"red"` để vẽ trên frame tiếp theo. **CHÚ Ý**: Presenter PHẢI gọi method này từ main thread (dùng `app.after(0, ...)`) để tránh race condition với `_update_frame()`
  - [x] Method `clear_bounding_box()` — xóa bounding box
  - [x] Giữ reference `self._current_image = ctk_image` sau mỗi lần configure để tránh garbage collection
  - [x] Guard: `_running` flag pattern (tương tự `_closing` trong app.py) để tránh update sau khi stop
  - [x] Guard: `winfo_exists()` check trong `_schedule_next()` và `_update_frame()` — tránh `TclError` khi widget bị destroy giữa chừng

- [x] Tạo `src/gui/session_panel.py` (AC: #2, #3, #6)
  - [x] Class `SessionPanel(CTkFrame)` với constructor: `__init__(self, master, scan_time_minutes: int = 60)`
  - [x] Constants cho 3 state: `WAITING_TEACHER = "waiting"`, `ATTENDANCE_ACTIVE = "active"`, `SESSION_ENDED = "ended"`
  - [x] Label trạng thái lớn (font 18-20): "⏳ CHỜ GIẢNG VIÊN" / "📋 ĐANG ĐIỂM DANH" / "✅ ĐÃ KẾT THÚC"
  - [x] Label thông tin nhận diện: hiển thị tên GV/SV + class info (nhận enriched data từ Presenter)
  - [x] Label đếm ngược `MM:SS` (font 24-28, bold) — chỉ hiện khi `ATTENDANCE_ACTIVE`
  - [x] Nút `[✅ Xác nhận]` — disabled mặc định, enabled khi GV detected. Click → emit `SESSION_CONFIRMED`
  - [x] Nút `[⏹ Kết thúc]` — hidden mặc định, visible + enabled khi `ATTENDANCE_ACTIVE`. Click → emit `SESSION_END_REQUESTED`
  - [x] Method `on_teacher_detected(data: dict)` — nhận enriched data `{'name', 'teacher_code', 'class_info', 'confidence'}`, cập nhật UI, enable nút Xác nhận
  - [x] Method `on_student_detected(data: dict)` — nhận enriched data `{'name', 'student_code', 'confidence'}`, hiển thị tên SV mới nhất
  - [x] Method `on_session_started(data: dict)` — nhận `{'class_id', 'start_time'}`, chuyển state sang `ATTENDANCE_ACTIVE`, bắt đầu timer
  - [x] Method `on_session_ended(data: dict)` — chuyển state sang `SESSION_ENDED`, gọi `_stop_timer()` dừng timer
  - [x] Method `_tick_countdown()` — giảm 1 giây, cập nhật label, nếu hết giờ → emit `SESSION_END_REQUESTED`. Thêm `winfo_exists()` guard
  - [x] Method `_stop_timer()` — cancel pending `after` timer via `after_cancel()`
  - [x] Method `reset()` — gọi `_stop_timer()` cancel timer cũ, quay về state `WAITING_TEACHER`, xóa thông tin, reset `_remaining_seconds`

- [x] Thêm EventType constants mới trong `src/core/events.py` (AC: #4)
  - [x] `SESSION_CONFIRMED = "session_confirmed"` — GV bấm Xác nhận
  - [x] `SESSION_END_REQUESTED = "session_end_requested"` — GV bấm Kết thúc hoặc hết giờ

- [x] Cập nhật `src/gui/app.py` (AC: #5)
  - [x] Import `CameraPanel` từ `src.gui.camera_panel`
  - [x] Import `SessionPanel` từ `src.gui.session_panel`
  - [x] Thay `camera_frame = CTkFrame(self)` + placeholder label bằng `self.camera_panel = CameraPanel(self)` rồi `.grid(row=0, column=0, ...)`
  - [x] Thay `session_frame = CTkFrame(self)` + placeholder label bằng `self.session_panel = SessionPanel(self)` rồi `.grid(row=0, column=1, ...)`
  - [x] Giữ nguyên `attendance_frame` và `student_frame` (chưa thay đổi, thuộc story 5-3)
  - [x] Giữ nguyên grid layout + weights + graceful shutdown

- [x] Cập nhật `src/gui/__init__.py` (AC: #5)
  - [x] Thêm exports: `from .camera_panel import CameraPanel` và `from .session_panel import SessionPanel`

- [x] Cập nhật `tests/test_gui_app.py` (AC: #5 — tránh regression)
  - [x] Sửa test `test_app_initialization`: thay `isinstance(app.camera_frame, ctk.CTkFrame)` → kiểm tra `hasattr(app, 'camera_panel')` và `isinstance(app.camera_panel, CameraPanel)`
  - [x] Tương tự cho `session_frame` → `session_panel`
  - [x] Giữ nguyên tests cho `attendance_frame` và `student_frame`

- [x] Viết tests `tests/test_camera_panel.py`
  - [x] Test khởi tạo CameraPanel với mock parent + mock callback
  - [x] Test `start_preview()` sets `_running = True`
  - [x] Test `stop_preview()` sets `_running = False` và gọi `after_cancel()`
  - [x] Test `set_bounding_box()` lưu coords + color đúng
  - [x] Test `clear_bounding_box()` xóa coords
  - [x] Test `_update_frame()` với mock get_frame callback trả None → không crash
  - [x] Test `_update_frame()` với mock callback trả frame → gọi label.configure
  - [x] Test `_update_frame()` với callback ném exception → graceful handle, không crash
  - [x] Test `_schedule_next()` không gọi `after()` khi `winfo_exists()` trả False
  - [x] Test `_update_frame()` PIL conversion failure (malformed frame) → graceful handle

- [x] Viết tests `tests/test_session_panel.py`
  - [x] Test khởi tạo SessionPanel default state = WAITING_TEACHER
  - [x] Test state transitions: WAITING → ACTIVE → ENDED
  - [x] Test nút Xác nhận disabled khi chưa detect GV
  - [x] Test nút Xác nhận enabled sau on_teacher_detected(enriched_data)
  - [x] Test on_session_started chuyển state + bắt đầu timer
  - [x] Test countdown timer logic (mock after())
  - [x] Test countdown hết giờ emit SESSION_END_REQUESTED
  - [x] Test reset() quay về WAITING_TEACHER + xóa thông tin
  - [x] Test reset() giữa lúc timer đang chạy → timer cũ bị cancel
  - [x] Test on_session_ended() khi timer đang active → timer bị cancel
  - [x] Test scan_time_minutes = 0 → emit SESSION_END_REQUESTED lập tức
  - [x] Test `_tick_countdown()` không crash khi `winfo_exists()` trả False


## Dev Notes

### Architecture Constraints (CRITICAL)

- **MVP Pattern**: View layer (`src/gui`) phải "ngu" — KHÔNG import từ `src.core` **ngoại trừ** `src.core.events` (EventManager + EventType). `src.core.events` là kênh giao tiếp duy nhất được phép.
- **Camera Panel KHÔNG sở hữu CameraManager**: Nhận `get_frame_callback` qua constructor. Presenter sẽ truyền `camera_manager.get_frame`.
- **Session Panel KHÔNG gọi AttendanceSession, KHÔNG import Config**: Nhận `scan_time_minutes` qua constructor (Presenter đọc config và truyền giá trị). Chỉ emit events, Presenter điều phối.
- **Thread Safety**: GUI updates PHẢI chạy trên main thread. Sử dụng `self.after()` cho periodic updates — KHÔNG dùng `after_idle()`.
- **Thread Contract cho Panel Methods**: Presenter PHẢI gọi tất cả panel methods (`set_bounding_box()`, `on_teacher_detected()`, `on_student_detected()`, v.v.) từ main thread — dùng `app.after(0, lambda: panel.method(data))`. Panels KHÔNG tự synchronize — trách nhiệm thuộc Presenter.
- **Widget Lifecycle Guard**: Mọi `self.after()` call PHẢI kiểm tra `self.winfo_exists()` trước — tránh `TclError` khi widget đã bị destroy.

### Presenter ↔ Panel Orchestration Flow (CRITICAL)

Các panel là "ngu" — Presenter (src/main.py, story 6-2) sẽ điều phối toàn bộ flow. Story này chỉ tạo panels, **Presenter wiring thuộc story 6-2**. Nhưng panels PHẢI expose đúng API:

```
[Khởi tạo] Presenter tạo panels:
  camera_panel = CameraPanel(app, get_frame_callback=camera_manager.get_frame)
  session_panel = SessionPanel(app, scan_time_minutes=Config().get('session','student_scan_time',default=60))

[GV quét mặt] Worker emit TEACHER_DETECTED(raw_data) →
  Presenter subscribe, enrich data (lookup teacher name, check timetable, get class info) →
  Presenter gọi (qua app.after): session_panel.on_teacher_detected(enriched_data)
  Presenter gọi (qua app.after): camera_panel.set_bounding_box(raw_data['coordinates'], "green")

[GV bấm Xác nhận] Session panel emit SESSION_CONFIRMED →
  Presenter subscribe → start AttendanceSession → load student encodings → start worker mode 2

[SV quét mặt] Worker emit STUDENT_DETECTED(raw_data) →
  Presenter subscribe, enrich data (lookup student name, student_code) →
  Presenter gọi (qua app.after): session_panel.on_student_detected(enriched_data)
  Presenter gọi (qua app.after): camera_panel.set_bounding_box(raw_data['coordinates'], "green")

[Hết giờ / GV bấm Kết thúc] Session panel emit SESSION_END_REQUESTED →
  Presenter subscribe → end AttendanceSession → export Excel → session_panel.reset()

[Shutdown] app.py emit SHUTDOWN_REQUESTED →
  Presenter: camera_panel.stop_preview() → worker.stop_scanning() → camera.stop() → app.destroy()
```

### Enriched Data Contracts (CRITICAL)

Panels nhận enriched data từ Presenter — KHÔNG phải raw data từ Worker.

```python
# Enriched TEACHER_DETECTED (Presenter → SessionPanel.on_teacher_detected)
{
    'person_id': int,           # teacher.id
    'name': str,                # "Nguyễn Văn A" (từ DB lookup)
    'teacher_code': str,        # "GV001" (từ DB lookup)
    'class_info': str,          # "CNTT01 - Lập trình Python" (từ timetable check)
    'confidence': float,        # 0-100%
    'coordinates': dict,        # {'top','right','bottom','left'} — cho bounding box
}

# Enriched STUDENT_DETECTED (Presenter → SessionPanel.on_student_detected)
{
    'person_id': int,           # student.id
    'name': str,                # "Trần Văn B" (từ DB lookup)
    'student_code': str,        # "2024001" (từ DB lookup)
    'confidence': float,        # 0-100%
    'coordinates': dict,        # {'top','right','bottom','left'} — cho bounding box
}

# Raw Worker event format (tham khảo — panels KHÔNG nhận trực tiếp):
# {'person_id': int, 'confidence': float, 'coordinates': FaceDetectionResult, 'snapshot_path': str}
```

### Constructor Signatures (Exact)

```python
# camera_panel.py
class CameraPanel(ctk.CTkFrame):
    def __init__(self, master, get_frame_callback: callable = None):
        super().__init__(master)
        self._get_frame_callback = get_frame_callback
        self._running = False
        self._after_id = None
        self._bbox_coords = None   # dict {'top','right','bottom','left'} hoặc None
        self._bbox_color = "red"   # "green" hoặc "red"
        self._current_image = None # giữ reference CTkImage
        # ... setup video_label ...

# session_panel.py
class SessionPanel(ctk.CTkFrame):
    def __init__(self, master, scan_time_minutes: int = 60):
        super().__init__(master)
        self._scan_time_minutes = scan_time_minutes
        self._state = self.WAITING_TEACHER
        self._remaining_seconds = 0
        self._timer_id = None
        # ... setup labels + buttons ...
```

### Camera Preview Update Pattern (CRITICAL)

```python
from PIL import Image
import customtkinter as ctk
import cv2

def _update_frame(self):
    if not self._running or not self.winfo_exists():
        return

    if not self._get_frame_callback:
        self._schedule_next()
        return

    try:
        frame = self._get_frame_callback()
    except Exception:
        self._schedule_next()
        return

    if frame is None:
        self._schedule_next()
        return

    # QUAN TRỌNG: copy() trước khi vẽ bbox để không modify CameraManager's cached frame
    display_frame = frame.copy()

    # Vẽ bounding box nếu có (trên copy, dùng cv2)
    if self._bbox_coords:
        t, r, b, l = self._bbox_coords['top'], self._bbox_coords['right'], self._bbox_coords['bottom'], self._bbox_coords['left']
        color_rgb = (0, 255, 0) if self._bbox_color == "green" else (255, 0, 0)
        cv2.rectangle(display_frame, (l, t), (r, b), color_rgb, 2)

    # Scale frame theo panel size
    panel_w = self.winfo_width()
    panel_h = self.winfo_height()
    display_size = (panel_w, panel_h) if panel_w > 1 and panel_h > 1 else (640, 480)

    try:
        pil_image = Image.fromarray(display_frame)
        ctk_image = ctk.CTkImage(light_image=pil_image, dark_image=pil_image, size=display_size)
        self.video_label.configure(image=ctk_image)
        self._current_image = ctk_image  # Giữ reference tránh GC
    except Exception:
        pass  # Skip frame nếu PIL/CTkImage conversion fail

    self._schedule_next()

def _schedule_next(self):
    if self._running and self.winfo_exists():
        self._after_id = self.after(33, self._update_frame)  # ~30fps
```

### Countdown Timer Pattern

```python
# scan_time_minutes nhận qua constructor — KHÔNG import Config
# Timer dùng self.after() — KHÔNG dùng threading.Timer

def _start_countdown(self):
    self._remaining_seconds = self._scan_time_minutes * 60
    self._tick_countdown()

def _tick_countdown(self):
    if not self.winfo_exists():
        return
    if self._remaining_seconds <= 0:
        self.countdown_label.configure(text="00:00")
        events.emit(EventType.SESSION_END_REQUESTED)
        return
    mins, secs = divmod(self._remaining_seconds, 60)
    self.countdown_label.configure(text=f"{mins:02d}:{secs:02d}")
    self._remaining_seconds -= 1
    self._timer_id = self.after(1000, self._tick_countdown)

def _stop_timer(self):
    if self._timer_id:
        self.after_cancel(self._timer_id)
        self._timer_id = None
```

### EventType Constants

Đã có trong `src/core/events.py`:
- `TEACHER_DETECTED`, `STUDENT_DETECTED`, `SESSION_STARTED`, `SESSION_ENDED`
- `CAMERA_STOPPED`, `ERROR_OCCURRED`, `SHUTDOWN_REQUESTED`

**Cần thêm:**
- `SESSION_CONFIRMED = "session_confirmed"` — session panel emit khi GV bấm Xác nhận
- `SESSION_END_REQUESTED = "session_end_requested"` — session panel emit khi GV bấm Kết thúc hoặc hết giờ

### Project Structure Notes

- **Files tạo mới**: `src/gui/camera_panel.py`, `src/gui/session_panel.py`, `tests/test_camera_panel.py`, `tests/test_session_panel.py`
- **Files sửa đổi**: `src/gui/app.py` (thay placeholder), `src/core/events.py` (thêm 2 constants), `src/gui/__init__.py` (thêm exports), `tests/test_gui_app.py` (update kiểu check)
- `src/gui/__init__.py` đã tồn tại — không cần tạo

### Anti-Pattern Prevention

| ❌ SAI | ✅ ĐÚNG |
|--------|---------|
| `from src.core.config import Config` trong panel | Nhận `scan_time_minutes` qua constructor |
| `from src.core.camera import CameraManager` trong panel | Nhận `get_frame_callback` qua constructor |
| Gọi `AttendanceSession.start_session()` trong panel | Emit `SESSION_CONFIRMED`, Presenter xử lý |
| Panel nhận raw worker data rồi tự query DB | Presenter enrich data rồi gọi panel methods |
| `cv2.rectangle(frame, ...)` trên original frame | `display_frame = frame.copy()` trước khi vẽ |
| Dùng `threading.Timer` cho countdown | Dùng `self.after(1000, ...)` trên main thread |
| Tạo `CTkLabel` mới mỗi frame | Dùng `label.configure(image=...)` |
| Dùng `ImageTk.PhotoImage` | Dùng `CTkImage` (HiDPI support) |
| Dùng `after_idle()` cho camera loop | Dùng `after(33, ...)` cho consistent framerate |
| Không giữ image reference | `self._current_image = ctk_image` |
| Gọi `self.after()` không check `winfo_exists()` | `if self._running and self.winfo_exists(): self.after(...)` |
| Presenter gọi panel method từ worker thread | Presenter dùng `app.after(0, lambda: panel.method(data))` |
| `Image.fromarray()` không wrap try-except | Wrap trong `try-except` để skip malformed frames |

### References

- [Source: src/gui/app.py](file:///Users/huynguyen/work/projects/BtlPython/src/gui/app.py) — Main window layout, placeholder frames, guard flag pattern
- [Source: src/core/events.py](file:///Users/huynguyen/work/projects/BtlPython/src/core/events.py) — EventManager + EventType constants
- [Source: src/core/camera.py](file:///Users/huynguyen/work/projects/BtlPython/src/core/camera.py) — CameraManager.get_frame() returns RGB copy
- [Source: src/core/worker.py#L130-148](file:///Users/huynguyen/work/projects/BtlPython/src/core/worker.py) — Raw event data format: `{person_id, confidence, coordinates, snapshot_path}`
- [Source: src/core/attendance_session.py#L80-104](file:///Users/huynguyen/work/projects/BtlPython/src/core/attendance_session.py) — SESSION_STARTED data format
- [Source: src/core/class_manager.py](file:///Users/huynguyen/work/projects/BtlPython/src/core/class_manager.py) — get_teacher(), get_classes_by_teacher() for enrichment
- [Source: config.yaml](file:///Users/huynguyen/work/projects/BtlPython/config.yaml) — session.student_scan_time=60, camera.fps=30
- [Source: tests/test_gui_app.py](file:///Users/huynguyen/work/projects/BtlPython/tests/test_gui_app.py) — Existing GUI test patterns (pytest fixture, Mock, event cleanup)
- [Source: docs/lich-su-thao-luan.md#13](file:///Users/huynguyen/work/projects/BtlPython/docs/lich-su-thao-luan.md) — Flow chính thức (Bước 1-3)

### Previous Story Intelligence (5-1-main-window-layout)

**Learnings áp dụng:**
- Guard flag `_closing` pattern → áp dụng `_running` flag cho CameraPanel
- Placeholder labels Tiếng Việt → tất cả text phải Tiếng Việt
- `EventManager` thread-safe lock + snapshot copy → an toàn emit từ worker thread
- Tests dùng pytest fixtures + Mock + cleanup event subscriptions
- Package `__init__.py` đã tồn tại
- Theme config đã xử lý module-level trong app.py

**Code Review Patterns:**
- H1: Package init ✓ — H2: Tiếng Việt ✓ — H3: Theme config ✓ — M2: Guard flag ✓ — M3: Cross-platform ✓

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (Thinking)

### Debug Log References

- Timer tick test: `_remaining_seconds` is `scan_time_minutes * 60 - 1` after `on_session_started()` because `_tick_countdown()` decrements immediately on first call before scheduling next tick.

### Completion Notes List

- ✅ Created `CameraPanel` with ~30fps preview loop, bounding box drawing (cv2), PIL→CTkImage conversion, `_running` guard flag, `winfo_exists()` lifecycle guards
- ✅ Created `SessionPanel` with 3-state machine (WAITING→ACTIVE→ENDED), enriched data display, countdown timer using `self.after(1000, ...)`, SESSION_CONFIRMED/SESSION_END_REQUESTED event emission
- ✅ Added 2 new EventType constants: `SESSION_CONFIRMED`, `SESSION_END_REQUESTED`
- ✅ Integrated panels into `app.py` replacing placeholder frames
- ✅ Updated `__init__.py` with exports (CameraPanel, SessionPanel, App)
- ✅ Updated `test_gui_app.py` for regression prevention (CameraPanel/SessionPanel type checks)
- ✅ 27 camera panel tests + 42 session panel tests = 69 new tests (after code review additions)
- ✅ Full regression suite: 133/133 tests passed, zero regressions
- ✅ MVP pattern strictly enforced: panels only import `src.core.events`, no other core modules
- ✅ All Vietnamese language labels maintained

### Change Log

- 2026-04-28: Story 5-2 implemented — CameraPanel + SessionPanel + EventType constants + app integration + 52 tests
- 2026-04-28: Code review fixes — 11 findings (4H/4M/3L) all resolved, +17 new tests, total 133/133 passed
- 2026-04-28: Party mode review fixes — 9 findings (3M/4L/2I) all resolved, +5 new tests, idempotency guards + forward-compatible event emission

### Senior Developer Review (AI)

**Reviewer:** Binh — 2026-04-28
**Outcome:** ✅ Approved (all findings fixed)

**Findings Fixed (11 total: 4 High, 4 Medium, 3 Low):**

| ID | Severity | Finding | Fix |
|----|----------|---------|-----|
| H1 | HIGH | No test for confirm button SESSION_CONFIRMED emission | Added `TestConfirmButtonEmission` class |
| H2 | HIGH | No test for end button SESSION_END_REQUESTED via click | Added `TestEndButtonEmission` class |
| H3 | HIGH | Tests don't verify student_code, "✅ Có mặt", teacher_code, class_info display | Added `TestEnrichedDataDisplay` class (6 tests) |
| H4 | HIGH | `__init__.py` missing App export | Added `from .app import App` |
| M1 | MEDIUM | Story claims 116 total tests, actual is 133 after fixes | Corrected in completion notes |
| M2 | MEDIUM | No test for _update_frame with active bbox + cv2.rectangle | Added `TestUpdateFrameWithBoundingBox` class (3 tests) |
| M3 | MEDIUM | Silent bare `pass` in PIL conversion exception | Replaced with `logger.debug()` |
| M4 | MEDIUM | _tick_countdown has no state guard (TOCTOU race) | Added `self._state != ATTENDANCE_ACTIVE` guard |
| L1 | LOW | camera_panel.py docstring says "ngoại trừ src.core.events" but doesn't import it | Fixed docstring |
| L2 | LOW | No validation for negative scan_time_minutes | Added `max(0, scan_time_minutes)` clamp + 3 tests |
| L3 | LOW | stop_preview() missing winfo_exists() guard | Added guard + `TestStopPreviewGuard` test |

### Party Mode Review (AI)

**Reviewers:** Winston (Architect) + Amelia (Dev) + Quinn (QA) — 2026-04-28
**Outcome:** ✅ Approved (all 9 findings fixed)

**Findings Fixed (9 total: 3 Medium, 4 Low, 2 Info):**

| ID | Severity | Finding | Fix |
|----|----------|---------|-----|
| D3 | MEDIUM | `_on_confirm_click()` and `_on_end_click()` emit None (not forward-compatible) | Emit `{}` instead of None across all 3 emission points |
| Q1 | MEDIUM | No test for `_update_frame` with widget destroyed mid-frame | Added `TestUpdateFrameWidgetDestroyed` class |
| Q3 | MEDIUM | No guard for double `on_session_started()` — orphaned timer | Added idempotency guard + `TestDoubleSessionStarted` class (2 tests) |
| D1 | LOW | Variable `l` shadowing confusion with `1` in bbox drawing | Renamed to `top`, `right`, `bottom`, `left_coord` |
| D2 | LOW | Countdown UX: first tick displays then immediately decrements | Display initial time in `_start_countdown()` before scheduling tick |
| Q2 | LOW | No guard for double `start_preview()` — orphaned after | Added idempotency guard + `TestDoubleStartPreview` class |
| Q4 | LOW | No test for stop→start restart cycle | Added `TestRestartPreview` class |
| D4 | INFO | CameraPanel/SessionPanel in app.py created without callbacks | Documented — Presenter wiring is story 6-2 |
| Q5 | INFO | No integration test for panels co-existing in App | Covered by `test_gui_app.py` type checks |

### File List

- [NEW] src/gui/camera_panel.py
- [NEW] src/gui/session_panel.py
- [NEW] tests/test_camera_panel.py
- [NEW] tests/test_session_panel.py
- [MODIFIED] src/core/events.py
- [MODIFIED] src/gui/app.py
- [MODIFIED] src/gui/__init__.py
- [MODIFIED] tests/test_gui_app.py
