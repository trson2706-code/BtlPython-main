# Story 5.3: Panel Điểm danh + Sinh viên

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a giảng viên (teacher),
I want an attendance tracking panel showing real-time student check-in status with statistics, and a student management panel with add/remove functionality and Excel export button,
so that I can monitor attendance progress during a session, manage the class roster, and export results — all with clear Vietnamese-language feedback.

## Acceptance Criteria

1. **Attendance Panel** (`src/gui/attendance_panel.py`): Hiển thị danh sách điểm danh scrollable trong `CTkScrollableFrame`. Mỗi dòng hiển thị: tên SV, MSSV, giờ điểm danh, trạng thái (✅ Có mặt / ❌ Vắng). Thống kê tổng: "Có mặt X/Y (Z%)" cập nhật real-time.
2. **Student Panel** (`src/gui/student_panel.py`): Hiển thị danh sách sinh viên trong lớp hiện tại (scrollable). Hỗ trợ thêm sinh viên qua dialog (tên, MSSV, chọn ảnh — ảnh optional). Hỗ trợ xóa sinh viên đã chọn (có dialog xác nhận trước khi xóa). Nút `[📊 Xuất Excel]` emit event để Presenter xử lý (disabled mặc định, enabled sau khi load danh sách SV).
3. **Tích hợp Event System**: Tất cả giao tiếp thông qua `EventManager` (`src.core.events`). Panels KHÔNG import từ `src.core.database`, `src.core.student_manager`, `src.core.config`, hay bất kỳ module core nào khác. Chỉ import `src.core.events` (EventManager + EventType). Data nhận qua event callbacks hoặc public methods (gọi bởi Presenter).
4. **Tích hợp vào App**: Thay thế placeholder frames trong `src/gui/app.py` (`attendance_frame`, `student_frame`) bằng instance của `AttendancePanel` và `StudentPanel`. Các panel nhận parent frame làm master.
5. **Cập nhật điểm danh real-time**: Khi Presenter nhận enriched `STUDENT_DETECTED` → gọi `attendance_panel.add_record(data)` để thêm dòng mới vào danh sách + cập nhật thống kê. Data contract: `{'student_id', 'name', 'student_code', 'confidence', 'mark_time'}`.
6. **Session lifecycle**: Khi session bắt đầu → `attendance_panel.on_session_started(data)` load danh sách SV ban đầu (tất cả ❌ Vắng). Khi session kết thúc → `attendance_panel.on_session_ended(data)` chỉ freeze danh sách (`_session_active = False`) — KHÔNG cần re-render hay format datetime (data đã hiển thị real-time qua `add_record`). Reset khi bắt đầu session mới.
7. **Student management**: `student_panel.on_students_loaded(students_list)` nhận danh sách SV từ Presenter + set `_has_session_data = True` + enable Excel button. Nút thêm SV emit `STUDENT_ADD_REQUESTED` với data `{'name', 'student_code', 'image_path'}` (`image_path` optional — `''` nếu không chọn ảnh). Nút xóa SV hiển thị **dialog xác nhận** trước khi emit `STUDENT_REMOVE_REQUESTED` với data `{'student_id'}`. Presenter xử lý logic CRUD.
8. **Excel export**: Nút `[📊 Xuất Excel]` emit `EXCEL_EXPORT_REQUESTED`. **Disabled mặc định** — enabled khi `on_students_loaded()` được gọi. Presenter subscribe → gọi `excel_export.export_session()` → thông báo kết quả.
9. **Ngôn ngữ**: Mọi text hiển thị phải bằng Tiếng Việt.
10. **Widget Lifecycle**: Mọi `self.after()` call PHẢI kiểm tra `self.winfo_exists()` trước. Guard pattern giống CameraPanel/SessionPanel.
11. **Empty State UX**: Khi chưa có phiên điểm danh, AttendancePanel hiển thị placeholder "Chưa có phiên điểm danh". Khi StudentPanel chưa có SV, hiển thị "Chưa có sinh viên. Nhấn ➕ để thêm."

## Tasks / Subtasks

- [x] Thêm EventType constants mới trong `src/core/events.py` (AC: #3, #7, #8)
  - [x] `STUDENT_ADD_REQUESTED = "student_add_requested"`
  - [x] `STUDENT_REMOVE_REQUESTED = "student_remove_requested"`
  - [x] `EXCEL_EXPORT_REQUESTED = "excel_export_requested"`

- [x] Tạo `src/gui/attendance_panel.py` (AC: #1, #5, #6, #10)
  - [x] `import logging` + `logger = logging.getLogger(__name__)` — pattern từ camera_panel.py
  - [x] Class `AttendancePanel(CTkFrame)` với constructor: `__init__(self, master)`
  - [x] Header label: "📋 BẢNG ĐIỂM DANH" (font 18, bold)
  - [x] Stats label: "Có mặt 0/0 (0%)" (font 14) — cập nhật real-time
  - [x] `CTkScrollableFrame` bên trong cho danh sách SV
  - [x] Placeholder label: "Chưa có phiên điểm danh" — hiển thị khi `_session_active == False`, ẩn khi session started (AC#11)
  - [x] Helper method `_create_attendance_row(parent, student_data) -> CTkFrame` — tạo row frame với labels (tên, MSSV, giờ, trạng thái icon). Return row frame + lưu label refs
  - [x] Mỗi record row: `CTkFrame` chứa labels (tên, MSSV, giờ, trạng thái icon). Lưu label refs vào `_records` dict để cập nhật status/time sau
  - [x] Method `on_session_started(data: dict)` — nhận **enriched** data `{'class_id', 'students': [{'student_id', 'name', 'student_code'}]}` (Presenter enrich, không phải raw SESSION_STARTED event). Gọi `reset()` trước để xóa session cũ. Ẩn placeholder, render tất cả SV với ❌ Vắng, reset stats
  - [x] Method `add_record(data: dict)` — nhận `{'student_id', 'name', 'student_code', 'confidence', 'mark_time'}`, cập nhật dòng SV từ ❌ → ✅ bằng cách configure label refs (KHÔNG tạo row mới). Cập nhật stats. **Guard**: skip nếu `student_id` đã ✅ hoặc session inactive hoặc `student_id` không có trong `_records` (no KeyError)
  - [x] Method `on_session_ended(data: dict)` — nhận `{'class_id', 'start_time', 'end_time', 'present': [...], 'absent': [...]}` (từ `AttendanceSession.end_session()`). Set `_session_active = False` freeze danh sách. **NOTE**: Chỉ freeze — KHÔNG cần format datetime. Data đã hiển thị real-time qua `add_record()` (mark_time format sẵn bởi Presenter). Có thể update stats thành "KẾT THÚC — Có mặt X/Y (Z%)"
  - [x] Method `reset()` — gọi `widget.destroy()` cho mỗi row frame trong `_records` (tránh memory leak), xóa `_records` dict, reset `_total_students = 0`, `_present_count = 0`, `_session_active = False`, hiển thị lại placeholder
  - [x] Internal tracking: `self._records: dict[int, dict]` — map student_id → `{'status_label': CTkLabel, 'time_label': CTkLabel, 'row_frame': CTkFrame, 'is_present': bool}`
  - [x] Internal: `self._total_students = 0`, `self._present_count = 0`
  - [x] Method `_update_stats()` — cập nhật stats label "Có mặt X/Y (Z%)". **Guard**: nếu `_total_students == 0` → hiển thị "Có mặt 0/0 (0%)" tránh ZeroDivisionError
  - [x] Guard: `self._session_active` flag — `add_record()` chỉ hoạt động khi session active

- [x] Tạo `src/gui/student_panel.py` (AC: #2, #7, #8, #10, #11)
  - [x] `import logging` + `logger = logging.getLogger(__name__)` — pattern từ camera_panel.py
  - [x] Class `StudentPanel(CTkFrame)` với constructor: `__init__(self, master)`
  - [x] Header label: "👨‍🎓 DANH SÁCH SINH VIÊN" (font 18, bold)
  - [x] `CTkScrollableFrame` cho danh sách SV
  - [x] Placeholder label: "Chưa có sinh viên. Nhấn ➕ để thêm." — hiển thị khi list rỗng, ẩn khi có SV (AC#11)
  - [x] Helper method `_create_student_row(parent, student_data) -> CTkFrame` — tạo row frame với labels (tên, MSSV) + nút xóa `CTkButton(text="❌", width=30)` right-aligned. Return row frame
  - [x] Mỗi student row: `CTkFrame` chứa labels (tên, MSSV) + nút xóa nhỏ (❌)
  - [x] Nút `[➕ Thêm sinh viên]` — mở dialog `_show_add_dialog()`
  - [x] Nút `[📊 Xuất Excel]` — emit `EXCEL_EXPORT_REQUESTED` (empty dict `{}`). Disabled mặc định, enabled khi `on_students_loaded()` được gọi
  - [x] Method `on_students_loaded(students: list)`
  - [x] Method `on_student_added(data: dict)` — idempotency guard
  - [x] Method `on_student_removed(student_id: int)` — safe skip if not found
  - [x] Method `on_error(message: str)` — hiển thị thông báo lỗi tạm thời
  - [x] Method `reset()` — clear list, disable export, show placeholder
  - [x] Method `_clear_list()` — destroy widgets, tránh memory leak
  - [x] Method `_show_add_dialog()` — transient(winfo_toplevel()), grab_release before filedialog, validation, image_path optional
  - [x] Method `_on_remove_click(student_id, student_name)` — confirmation dialog trước khi emit
  - [x] Internal tracking: `self._student_widgets: dict[int, CTkFrame]`
  - [x] Internal: `self._has_session_data = False`

- [x] Cập nhật `src/gui/app.py` (AC: #4)
  - [x] Import `AttendancePanel` từ `src.gui.attendance_panel`
  - [x] Import `StudentPanel` từ `src.gui.student_panel`
  - [x] Thay placeholder frames bằng real panels
  - [x] Xóa placeholder labels

- [x] Cập nhật `src/gui/__init__.py` (AC: #4)
  - [x] Thêm: `from .attendance_panel import AttendancePanel`
  - [x] Thêm: `from .student_panel import StudentPanel`

- [x] Cập nhật `tests/test_gui_app.py` (AC: #4 — regression)
  - [x] Sửa type checks: AttendancePanel, StudentPanel
  - [x] Thêm import `AttendancePanel`, `StudentPanel`

- [x] Viết tests `tests/test_attendance_panel.py` — 27 tests, all pass
  - [x] autouse fixture `cleanup_events`
  - [x] 7 initialization tests, 5 session started tests, 6 add_record tests
  - [x] 2 stats tests, 2 session ended tests, 5 reset tests

- [x] Viết tests `tests/test_student_panel.py` — 32 tests, all pass
  - [x] autouse fixture `cleanup_events`
  - [x] 7 initialization, 6 on_students_loaded, 3 on_student_added
  - [x] 3 on_student_removed, 2 export button, 2 remove dialog
  - [x] 4 add dialog, 1 on_error, 4 reset tests

## Dev Notes

### Architecture Constraints (CRITICAL)

- **MVP Pattern**: View layer (`src/gui`) phải "ngu" — KHÔNG import từ `src.core` **ngoại trừ** `src.core.events` (EventManager + EventType). `src.core.events` là kênh giao tiếp duy nhất được phép.
- **Attendance Panel KHÔNG gọi AttendanceSession hay Database**: Nhận data qua public methods gọi bởi Presenter. Panel chỉ hiển thị, KHÔNG query.
- **Student Panel KHÔNG gọi StudentManager hay Database**: Emit events (STUDENT_ADD_REQUESTED, STUDENT_REMOVE_REQUESTED), Presenter xử lý CRUD.
- **Thread Safety**: GUI updates PHẢI chạy trên main thread. Presenter PHẢI gọi tất cả panel methods từ main thread — dùng `app.after(0, lambda: panel.method(data))`.
- **Widget Lifecycle Guard**: Mọi `self.after()` call PHẢI kiểm tra `self.winfo_exists()` trước — tránh `TclError` khi widget đã bị destroy. Pattern giống `CameraPanel._schedule_next()` và `SessionPanel._tick_countdown()`.
- **Event Emission**: Emit `{}` (empty dict) thay vì `None` cho forward compatibility — pattern từ story 5-2 (D3 fix).

### Presenter ↔ Panel Orchestration Flow (CRITICAL)

Panels là "ngu" — Presenter (src/main.py, story 6-2) sẽ điều phối. Story này chỉ tạo panels. Nhưng panels PHẢI expose đúng API:

```
[Session bắt đầu] Presenter subscribe SESSION_STARTED →
  Presenter query students in class → enrich data →
  Presenter gọi (qua app.after): attendance_panel.on_session_started({
    'class_id': int,
    'students': [{'student_id', 'name', 'student_code'}, ...]
  })
  Presenter gọi (qua app.after): student_panel.on_students_loaded(students_list)

[SV điểm danh] Worker emit STUDENT_DETECTED(raw) →
  Presenter enrich → gọi (qua app.after): attendance_panel.add_record({
    'student_id': int, 'name': str, 'student_code': str,
    'confidence': float, 'mark_time': str  # formatted "HH:MM:SS"
  })

[Session kết thúc] Presenter subscribe SESSION_ENDED →
  Presenter gọi: attendance_panel.on_session_ended(result_data)

[Thêm SV] Student panel emit STUDENT_ADD_REQUESTED({'name','student_code','image_path'}) →
  Presenter subscribe → call student_manager.add_student() →
  Presenter gọi: student_panel.on_student_added({'student_id','name','student_code'})

[Xóa SV] Student panel emit STUDENT_REMOVE_REQUESTED({'student_id': int}) →
  Presenter subscribe → call student_manager.remove_student() →
  Presenter gọi: student_panel.on_student_removed(student_id)

[Xuất Excel] Student panel emit EXCEL_EXPORT_REQUESTED →
  Presenter subscribe → call excel_export.export_session() → thông báo
```

### Data Contracts (CRITICAL)

```python
# on_session_started (Presenter → AttendancePanel)
{
    'class_id': int,
    'students': [
        {'student_id': int, 'name': str, 'student_code': str},
        ...
    ]
}

# add_record (Presenter → AttendancePanel)
{
    'student_id': int,          # student.id
    'name': str,                # "Trần Văn B"
    'student_code': str,        # "2024001"
    'confidence': float,        # 0-100%
    'mark_time': str,           # "14:30:25" (formatted by Presenter)
}

# STUDENT_ADD_REQUESTED (StudentPanel → Presenter)
{
    'name': str,                # "Nguyễn Văn C"
    'student_code': str,        # "2024002"
    'image_path': str,          # "/path/to/photo.jpg" hoặc "" (optional — rỗng nếu không chọn ảnh)
}

# STUDENT_REMOVE_REQUESTED (StudentPanel → Presenter)
{
    'student_id': int,          # student.id
}

# on_students_loaded (Presenter → StudentPanel)
[
    {'student_id': int, 'name': str, 'student_code': str},
    ...
]

# on_session_ended (Presenter → AttendancePanel) — from AttendanceSession.end_session()
# NOTE: mark_time values are datetime objects, panel must format to str
{
    'class_id': int,
    'start_time': datetime,
    'end_time': datetime,
    'present': [{'id': int, 'student_code': str, 'name': str, 'is_present': True,
                 'confidence': float, 'image_path': str|None, 'mark_time': datetime|None}],
    'absent':  [{'id': int, 'student_code': str, 'name': str, 'is_present': False,
                 'confidence': 0.0, 'image_path': None, 'mark_time': None}]
}
```

### Constructor Signatures (Exact)

```python
# attendance_panel.py
class AttendancePanel(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master)
        self._records = {}          # dict[int, dict] — student_id → row widget refs
        #   key: student_id (int)
        #   value: {'status_label': CTkLabel, 'time_label': CTkLabel,
        #           'row_frame': CTkFrame, 'is_present': bool}
        self._total_students = 0
        self._present_count = 0
        self._session_active = False
        # ... setup header, stats, scrollable frame ...

# student_panel.py
class StudentPanel(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master)
        self._student_widgets = {}  # dict[int, CTkFrame] — student_id → row widget
        self._has_session_data = False  # controls Excel export button state
        # ... setup header, scrollable frame, buttons ...
        # ... self.export_button: state="disabled" mặc định ...
```

### Scrollable List Pattern (CRITICAL)

```python
# Dùng CTkScrollableFrame cho danh sách — KHÔNG tự implement scrollbar
self._scroll_frame = ctk.CTkScrollableFrame(self)
self._scroll_frame.pack(expand=True, fill="both", padx=5, pady=5)

# Mỗi row là CTkFrame trong scroll_frame
def _create_row(self, parent, data):
    row = ctk.CTkFrame(parent)
    row.pack(fill="x", padx=2, pady=1)
    ctk.CTkLabel(row, text=data['name'], width=120, anchor="w").pack(side="left", padx=5)
    ctk.CTkLabel(row, text=data['student_code'], width=80).pack(side="left", padx=5)
    # ... thêm labels ...
    return row
```

### Add Student Dialog Pattern

```python
from tkinter import filedialog

def _show_add_dialog(self):
    dialog = ctk.CTkToplevel(self)
    dialog.title("➕ Thêm sinh viên")
    dialog.geometry("400x350")
    dialog.transient(self.winfo_toplevel())  # C4 FIX: dùng toplevel window, KHÔNG dùng self (CTkFrame)
    dialog.grab_set()       # Block interaction with parent
    dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)  # X button safe cleanup

    name_entry = ctk.CTkEntry(dialog, placeholder_text="Tên sinh viên")
    code_entry = ctk.CTkEntry(dialog, placeholder_text="MSSV")
    image_path_var = ""  # Optional — mặc định rỗng

    def choose_image():
        nonlocal image_path_var
        dialog.grab_release()   # FIX D5: release grab trước filedialog
        path = filedialog.askopenfilename(filetypes=[("Ảnh", "*.jpg *.jpeg *.png")])
        dialog.grab_set()       # Re-grab sau filedialog
        if path:
            image_path_var = path
            # Update path label...

    # ... file chooser button ...
    # ... Nút Hủy: command=dialog.destroy ...
    # ... Nút Thêm: validate tên+MSSV không rỗng (image_path optional) → emit STUDENT_ADD_REQUESTED → dialog.destroy()
```

### Anti-Pattern Prevention

| ❌ SAI | ✅ ĐÚNG |
|--------|---------|
| `from src.core.database import DatabaseManager` trong panel | Nhận data qua public methods từ Presenter |
| `from src.core.student_manager import StudentManager` | Emit `STUDENT_ADD_REQUESTED`, Presenter xử lý |
| Panel tự query DB để load student list | Presenter gọi `panel.on_students_loaded(data)` |
| `self._records = []` (list) cho tracking | `self._records = {}` (dict by student_id) cho O(1) lookup |
| Tạo `Scrollbar` + `Canvas` thủ công | Dùng `CTkScrollableFrame` (built-in) |
| Emit `None` trong event | Emit `{}` (empty dict) cho forward compatibility |
| Gọi `panel.add_record()` từ worker thread | Presenter dùng `app.after(0, lambda: panel.add_record(data))` |
| `dialog.transient(self)` — self là CTkFrame | `dialog.transient(self.winfo_toplevel())` — reference actual window |
| `filedialog.askopenfilename()` không filter | Filter `filetypes=[("Ảnh", "*.jpg *.jpeg *.png")]` |
| Không có `_clear_list()` khi reload students | Gọi `_clear_list()` trong `on_students_loaded()` trước khi render |
| `reset()` không destroy widgets | `reset()` PHẢI gọi `widget.destroy()` cho mỗi row tránh memory leak |
| `filedialog` khi `grab_set()` đang active | `dialog.grab_release()` trước `filedialog`, `dialog.grab_set()` lại sau |
| Xóa SV trực tiếp không hỏi | Hiển thị confirmation dialog trước khi emit `STUDENT_REMOVE_REQUESTED` |
| `image_path` bắt buộc trong add dialog | `image_path` optional — mặc định `''` nếu không chọn ảnh |
| Không có placeholder khi list rỗng | Hiển thị placeholder text hướng dẫn user |

### Project Structure Notes

- **Files tạo mới**: `src/gui/attendance_panel.py`, `src/gui/student_panel.py`, `tests/test_attendance_panel.py`, `tests/test_student_panel.py`
- **Files sửa đổi**: `src/gui/app.py` (thay placeholder), `src/core/events.py` (thêm 3 constants), `src/gui/__init__.py` (thêm exports), `tests/test_gui_app.py` (update type checks)

### References

- [Source: src/gui/app.py](file:///Users/huynguyen/work/projects/BtlPython/src/gui/app.py) — Lines 47-56: placeholder frames cần thay thế
- [Source: src/core/events.py](file:///Users/huynguyen/work/projects/BtlPython/src/core/events.py) — EventManager + EventType constants hiện tại
- [Source: src/gui/session_panel.py](file:///Users/huynguyen/work/projects/BtlPython/src/gui/session_panel.py) — Pattern reference: CTkFrame, event emit, state guards
- [Source: src/gui/camera_panel.py](file:///Users/huynguyen/work/projects/BtlPython/src/gui/camera_panel.py) — Pattern reference: winfo_exists guard, _running flag
- [Source: src/gui/__init__.py](file:///Users/huynguyen/work/projects/BtlPython/src/gui/__init__.py) — Current exports: App, CameraPanel, SessionPanel
- [Source: src/core/attendance_session.py](file:///Users/huynguyen/work/projects/BtlPython/src/core/attendance_session.py) — AttendanceRecord TypedDict, end_session result format
- [Source: src/core/student_manager.py](file:///Users/huynguyen/work/projects/BtlPython/src/core/student_manager.py) — add_student/remove_student API
- [Source: config.yaml](file:///Users/huynguyen/work/projects/BtlPython/config.yaml) — paths.exports_dir = "data/exports"
- [Source: tests/test_gui_app.py](file:///Users/huynguyen/work/projects/BtlPython/tests/test_gui_app.py) — Existing test patterns (pytest fixture, Mock, event cleanup)
- [Source: sprint-status.yaml#E5-S3](file:///Users/huynguyen/work/projects/BtlPython/_bmad-output/implementation-artifacts/sprint-status.yaml) — Story requirements

### Previous Story Intelligence (5-2-camera-session-panel)

**Learnings to apply:**
- Guard flag patterns (`_running`, `_closing`) → áp dụng `_session_active` cho AttendancePanel
- `winfo_exists()` check trước mọi `self.after()` — mandatory
- Emit `{}` thay vì `None` (D3 fix) — áp dụng cho tất cả event emissions
- Idempotency guards (Q3 fix) — `add_record()` phải skip duplicate `student_id`
- `self._current_image` reference pattern → giữ widget references trong `self._records`
- Tests dùng pytest fixtures + Mock + cleanup event subscriptions
- `__init__.py` exports phải đầy đủ (H4 fix)
- Code review: rename confusing variables, add state guards, handle edge cases

**Code Review Patterns established (5-2):**
- H1-H4: Test event emissions + enriched data display + package exports ✓
- M1-M4: Test coverage accuracy + bbox drawing + logging + state guards ✓
- L1-L3: Docstring accuracy + input validation + winfo_exists guards ✓
- D1-D4: Variable naming + UX timing + idempotency + forward-compatible events ✓

**Party Mode Review Findings (5-3 pre-dev):**
- A1/D1/H1/P2: `_has_session_data` activation logic — set in `on_students_loaded()` ✓ FIXED
- P1: Confirmation dialog trước khi xóa SV (destructive action) ✓ FIXED
- H2/A2/D2: `on_session_ended` chỉ freeze, KHÔNG cần format datetime ✓ CLARIFIED
- H3: Test widget destroyed mid-session (winfo_exists guard) ✓ ADDED
- D5: `filedialog` + `grab_set()` conflict — cần `grab_release()` trước ✓ FIXED
- M4: Idempotency guard cho `on_student_added()` ✓ ADDED
- P5: `image_path` optional trong add dialog ✓ FIXED
- D3: `_create_row` helper methods ✓ ADDED
- P3: Empty state UX placeholder ✓ ADDED (AC#11)

### Technology Notes

- **CustomTkinter 5.2.2**: `CTkScrollableFrame` is available (built-in scrollable container). Use `pack(fill="both", expand=True)`. Do NOT use deprecated `CTkCanvas` approach.
- **CTkToplevel**: Use for dialog windows. Call `.transient(parent)` + `.grab_set()` for modal behavior. **QUAN TRỌNG**: Gọi `grab_release()` trước `filedialog.askopenfilename()`, rồi `grab_set()` lại sau — tránh conflict. Call `.destroy()` after submit. Thêm nút Hủy + `protocol("WM_DELETE_WINDOW", dialog.destroy)`.
- **tkinter.filedialog**: Use `askopenfilename(filetypes=[("Ảnh", "*.jpg *.jpeg *.png")])` for image selection. This is a standard tkinter module, safe to import in view layer.
- **Pillow 12.2.0**: NOT needed in this story (no image processing in panels). Only event data flows.

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (Thinking)

### Debug Log References

- CTkToplevel not found in winfo_children() → fixed by mocking all ctk widgets in dialog tests
- capture_button() missing *args → fixed: CTkButton passes parent as positional arg

### Completion Notes List

- ✅ Added 3 EventType constants (STUDENT_ADD_REQUESTED, STUDENT_REMOVE_REQUESTED, EXCEL_EXPORT_REQUESTED)
- ✅ Created AttendancePanel with scrollable list, real-time stats, session lifecycle, widget lifecycle guards
- ✅ Created StudentPanel with scrollable list, add/remove dialogs (confirmation), Excel export button
- ✅ Replaced placeholder frames in App with real panels
- ✅ Updated __init__.py exports
- ✅ Updated test_gui_app.py type checks (regression fix)
- ✅ Created test_attendance_panel.py — 28 tests covering all ACs
- ✅ Created test_student_panel.py — 35 tests covering all ACs
- ✅ Full regression suite: 196 passed, 1 pre-existing flaky failure (test_camera_runtime_disruption — timing race condition, unrelated)

### File List

- `src/core/events.py` — MODIFIED: added 3 EventType constants
- `src/gui/attendance_panel.py` — NEW: AttendancePanel class
- `src/gui/student_panel.py` — NEW: StudentPanel class
- `src/gui/app.py` — MODIFIED: replaced placeholders with real panels
- `src/gui/__init__.py` — MODIFIED: added AttendancePanel, StudentPanel exports
- `tests/test_gui_app.py` — MODIFIED: updated type checks for new panels
- `tests/test_attendance_panel.py` — NEW: 28 tests
- `tests/test_student_panel.py` — NEW: 35 tests

### Senior Developer Review (AI)

**Reviewer:** Code Review Agent — 2026-04-28
**Result:** ✅ APPROVED (all issues fixed)

**Issues Found & Fixed:**

| ID | Severity | Issue | Fix |
|---|---|---|---|
| H1 | HIGH | Missing `winfo_exists()` guards on public methods | Added guards to all public methods in both panels; `on_error()` now auto-clears after 5s with guard |
| M1 | MEDIUM | DRY violation — percentage calc duplicated | Extracted `_calc_percentage()` helper in AttendancePanel |
| M2 | MEDIUM | `on_student_added()` didn't enable export button | Now enables export when `_student_widgets` becomes non-empty |
| M3 | MEDIUM | `path.split("/")` Windows-incompatible | Replaced with `os.path.basename()` |
| L1 | LOW | No test for malformed student data | Added `test_malformed_student_data_skipped` |
| L2 | LOW | Unused return values from `_create_*_row()` | Removed return statements |
| L3 | LOW | Error label color hardcoded | `on_error()` now accepts `color` parameter |

**Test Results Post-Fix:** 70/70 passed ✅
