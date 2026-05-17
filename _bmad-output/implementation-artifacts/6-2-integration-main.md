# Story 6.2: Ghép nối toàn bộ (main.py)

Status: done

<!-- Validated: 2026-05-04 — 8+13 findings identified and resolved inline -->
<!-- Party-mode review: 2026-05-04 — 13 findings (F1-F13) remediated -->
<!-- Adversarial review: 2026-05-04 — 9 findings (CR-1 to CR-9) remediated -->
<!-- Party-mode review #2: 2026-05-04 — 6 findings (PM-1 to PM-6) remediated, 6 new tests -->

## Story

As a giảng viên (teacher),
I want the system to be fully wired so that scanning my face automatically finds my timetable, confirms my class, starts attendance mode, and exports Excel when complete,
so that the entire attendance workflow runs end-to-end without manual coordination.

## Acceptance Criteria

1. **File tạo mới**: `src/main.py` — Presenter layer, điểm vào duy nhất của ứng dụng. Chạy bằng `python -m src.main` hoặc `python src/main.py`.
2. **Khởi tạo components**: Tạo tất cả core objects theo đúng dependency order:
   - `DatabaseManager()` → `ClassManager(db)` → `StudentManager(db)` → `AttendanceSession(class_mgr)` → `CameraManager()` → `RecognitionWorker(camera)` → `ExcelExporter()` → `App()` (GUI)
   - ⚠️ Tạo `src/__init__.py` (empty file) nếu chưa tồn tại — cần cho `python -m src.main`
3. **Kết nối Camera → GUI**: Đặt `camera_panel._get_frame_callback = camera.get_frame`. Gọi `camera.start()` + `camera_panel.start_preview()`. Truyền `scan_time_minutes` từ `Config().get('session', 'student_scan_time', default=60)` vào `SessionPanel` — hiện `App()` tạo `SessionPanel(self)` dùng default 60, nên Presenter phải override: `self.app.session_panel._scan_time_minutes = config.get('session', 'student_scan_time', default=60)` SAU khi tạo App.
4. **Flow Chờ GV (Mode 1)**:
   - Load tất cả teacher encodings từ DB vào worker: `db.get_encodings_by_type('teacher')` → `worker.load_encodings(encodings, metadata)`
   - `worker.start_scanning(mode=1)` — quét GV
   - Subscribe `TEACHER_DETECTED` → handler enrich data:
     1. ⚠️ **[F3-fix] Mode guard**: `if self._current_mode != 1: return` — bỏ qua stale events từ mode cũ
     2. `person_id = data['person_id']` — ⚠️ worker dùng key `person_id`, KHÔNG phải `teacher_id`
     3. `teacher_info = db.get_teacher(person_id)` → lấy name, teacher_code. ⚠️ **Guard None**: `if not teacher_info: logger.warning(...); return`
     4. `class_id = session.check_timetable(person_id)` → trả về `int` class_id. Wrap trong `try-except ValueError` — nếu không có TKB thì log warning + return
     5. `class_info = db.get_class(class_id)` → lấy class_code, subject. ⚠️ **Guard None**: `if not class_info: logger.warning(...); return`
     6. Lưu `self._pending_class_id = class_id` + `self._current_teacher_id = person_id` — cần cho SESSION_CONFIRMED handler
     7. Enrich data: `{'person_id': person_id, 'name': teacher_info['name'], 'teacher_code': teacher_info['teacher_code'], 'class_info': f"{class_info['subject']} - {class_info['class_code']}", 'confidence': data['confidence'], 'coordinates': data['coordinates']}`
     8. `app.after(0, session_panel.on_teacher_detected, enriched)` + `app.after(0, camera_panel.set_bounding_box, data['coordinates'], 'green')`
5. **Flow Xác nhận GV (SESSION_CONFIRMED)**:
   - Subscribe `SESSION_CONFIRMED` → handler: 
     1. `worker.pause_scanning()`
     2. `class_id = self._pending_class_id` — lưu từ bước 4
     3. `self._current_class_id = class_id`
     4. `session.start_session(class_id)` — ⚠️ session tự emit `SESSION_STARTED` event, nhưng Presenter chủ động update GUI
     5. Load student encodings: `_load_student_encodings(class_id)` (xem pattern bên dưới)
     6. `worker.start_scanning(mode=2)` — chuyển sang quét SV
     7. Chuẩn bị students list cho GUI: `students_in_class = db.get_students_in_class(class_id)` → map sang `[{'student_id': s['id'], 'name': s['name'], 'student_code': s['student_code']}, ...]`
     8. `app.after(0, session_panel.on_session_started, {'class_id': class_id, 'start_time': datetime.now()})`
     9. `app.after(0, attendance_panel.on_session_started, {'class_id': class_id, 'students': students_list})`
     10. `app.after(0, student_panel.on_students_loaded, students_list)`
   - `self._current_mode = 2`
6. **Flow Điểm danh SV (Mode 2)**:
   - Subscribe `STUDENT_DETECTED` → handler `_on_student_detected(data)`:
     1. **Guard nguồn event**: `if 'coordinates' not in data: return` — bỏ qua event từ `AttendanceSession.mark_present()` (không có coordinates)
     2. ⚠️ **[F3-fix] Mode guard**: `if self._current_mode != 2: return` — bỏ qua stale events
     3. `student_id = data['person_id']` — ⚠️ worker dùng `person_id`, map thành `student_id`
     4. `raw_confidence = data['confidence']` — giá trị 0-100 từ `calculate_confidence()`
     5. `session_confidence = raw_confidence / 100.0` — ⚠️ CRITICAL: chuyển về 0.0-1.0 cho session (ExcelExporter nhân 100 lại)
     6. `snapshot_path = data.get('snapshot_path')`
     7. `success = session.mark_present(student_id, session_confidence, snapshot_path)` — ⚠️ session sẽ emit `STUDENT_DETECTED` nội bộ, bị bỏ qua ở bước 1
     8. `if not success: return` — SV đã điểm danh hoặc không thuộc lớp
     9. Query student info: `student = db.get_student(student_id)` → enrich. ⚠️ **Guard None**: `if not student: return`
     10. `mark_time_str = datetime.now().strftime('%H:%M:%S')`
     11. `enriched = {'student_id': student_id, 'name': student['name'], 'student_code': student['student_code'], 'confidence': raw_confidence, 'mark_time': mark_time_str}`
     12. `app.after(0, attendance_panel.add_record, enriched)` + `app.after(0, session_panel.on_student_detected, enriched)` + `app.after(0, camera_panel.set_bounding_box, data['coordinates'], 'green')`
   - Bounding box tự clear sau 2 giây: `app.after(2000, self.app.camera_panel.clear_bounding_box)`
7. **Flow Kết thúc (SESSION_END_REQUESTED)**:
   - Subscribe `SESSION_END_REQUESTED` (từ nút Kết thúc hoặc countdown hết giờ) → handler:
     1. ⚠️ **[F7-fix] Duplicate guard**: Wrap toàn bộ handler trong `try-except ValueError` — tránh crash khi `end_session()` gọi 2 lần (countdown + nút bấm gần cùng lúc)
     2. `worker.pause_scanning()`
     3. `result = session.end_session()` — ⚠️ raises ValueError nếu state=None (đã kết thúc)
     4. ⚠️ **[F4-fix]**: `self._last_session_result = result` — lưu result cho xuất Excel thủ công (AC#9)
     5. `self._current_mode = None` — chuyển sang idle
     6. Query: `class_info = db.get_class(self._current_class_id)`, `teacher_info = db.get_teacher(self._current_teacher_id)`
     7. ⚠️ **[F8-fix]**: Wrap export trong `try-except (ValueError, OSError)`: `filepath = exporter.export_session(result, class_info, teacher_info)` → `logger.info(f"Đã xuất Excel: {filepath}")`. Nếu exception → `logger.error(...)` + `app.after(0, student_panel.on_error, str(e))`
     8. Update GUI: `app.after(0, session_panel.on_session_ended, result)` + `app.after(0, attendance_panel.on_session_ended, result)`
     9. Sau 5 giây delay: `app.after(5000, self._reset_to_teacher_mode)` → quay về Flow Chờ GV (AC#8)
8. **Auto-reset sau khi kết thúc**: ⚠️ **[F12-fix]**: Đầu method kiểm tra `if not self.app.winfo_exists(): return` — tránh crash khi app đóng trong 5 giây delay. Sau đó reset tất cả panels (`session_panel.reset()`, `attendance_panel.reset()`, `student_panel.reset()`, `camera_panel.clear_bounding_box()`) + load lại teacher encodings + `worker.start_scanning(mode=1)`. Sử dụng `app.after(5000, self._reset_to_teacher_mode)` ⚠️ **[F5-fix]**: dùng `self._reset_to_teacher_mode` (có `self.` prefix).
9. **EXCEL_EXPORT_REQUESTED**: Subscribe event (từ nút Xuất Excel trên StudentPanel) → handler: gọi `exporter.export_session()` với session result hiện tại (nếu session đã kết thúc). Nếu chưa có result → log warning + hiển thị lỗi qua `student_panel.on_error()`.
10. **STUDENT_ADD_REQUESTED**: Subscribe → handler:
    1. ⚠️ **[F6-fix] Guard class_id**: `if self._current_class_id is None: app.after(0, student_panel.on_error, "Chưa có lớp học đang hoạt động."); return`
    2. `data = event_data` — chứa `{'name', 'student_code', 'image_path'}` từ StudentPanel dialog
    3. Wrap trong `try-except (ValueError, Exception)`: `student = student_mgr.add_student(data['name'], data['student_code'], data.get('image_path', ''))` → ⚠️ **[F11-fix]**: `student_id = student['id']` (return value là dict từ `get_student()`)
    4. `db.add_student_to_class(self._current_class_id, student_id)`
    5. Enrich data cho GUI: `enriched = {'student_id': student_id, 'name': student['name'], 'student_code': student['student_code']}`
    6. `app.after(0, student_panel.on_student_added, enriched)`
    7. Nếu exception → `app.after(0, student_panel.on_error, str(e))`
11. **STUDENT_REMOVE_REQUESTED**: Subscribe → handler: `student_mgr.remove_student(student_id)` → update GUI qua `app.after(0, student_panel.on_student_removed, student_id)`. Wrap trong try-except → `app.after(0, student_panel.on_error, str(e))`.
12. **Graceful Shutdown (SHUTDOWN_REQUESTED)**: Subscribe → handler: `worker.stop_scanning()` → `camera.stop()` → `camera_panel.stop_preview()` → `app.after(0, app.destroy)`. Đảm bảo dọn dẹp resources trước khi thoát.
13. **ERROR_OCCURRED**: Subscribe → handler: log lỗi qua logger. Hiển thị lỗi trên GUI nếu phù hợp.
14. **CAMERA_STOPPED** ⚠️ **[F13-fix]**: Subscribe → handler `_on_camera_stopped(data)`: log `logger.warning("Camera đã ngắt kết nối.")`. Nếu `self._current_mode is not None` → `app.after(0, session_panel.on_error_display, "Camera ngắt kết nối")` (hoặc hiển thị thông báo phù hợp trên info_label). Reset mode: `self._current_mode = None`.
15. **Logging**: Cấu hình `logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')` ở đầu main.
16. **Thread safety**: Tất cả GUI updates PHẢI qua `app.after(0, ...)` — không gọi trực tiếp từ worker thread. Event handlers chạy trên thread gọi emit → cần bridge sang main thread.
17. **Entry point**: File có `if __name__ == '__main__':` block. Cũng có thể chạy từ project root: `python -m src.main`.
18. **Test file**: `tests/test_main.py` — unit tests cho Presenter logic (mock tất cả components). Tối thiểu 18 test cases, hiện có **31 tests**.

## Tasks / Subtasks

- [x] Tạo `src/__init__.py` nếu chưa tồn tại (AC: #16)
  - [x] Empty file — cần cho `python -m src.main`

- [x] Tạo `src/main.py` (AC: #1, #2, #3, #14, #16)
  - [x] Import tất cả modules: `DatabaseManager`, `ClassManager`, `StudentManager`, `AttendanceSession`, `CameraManager`, `RecognitionWorker`, `ExcelExporter`, `App`, `events`, `EventType`
  - [x] `logging.basicConfig(...)` cấu hình
  - [x] Class `Presenter` — orchestrator chính
  - [x] `__init__()`: khởi tạo tất cả components theo dependency order (AC#2)
  - [x] Wire camera vào GUI + override scan_time_minutes từ config (AC#3)

- [x] Wire Event Handlers (AC: #4-#14, #16)
  - [x] `_setup_events()`: subscribe tất cả events (bao gồm CAMERA_STOPPED)
  - [x] `_on_teacher_detected(data)` — Mode 1 flow (AC#4) + [F3-fix] mode guard
  - [x] `_on_session_confirmed(data)` — xác nhận GV, chuyển Mode 2 (AC#5)
  - [x] `_on_student_detected(data)` — điểm danh SV (AC#6) + [F3-fix] mode guard
  - [x] `_on_session_end_requested(data)` — kết thúc session (AC#7) + [F7-fix] try-except + [F4-fix] save result + [F8-fix] export error handling
  - [x] `_reset_to_teacher_mode()` — auto-reset (AC#8) + [F12-fix] winfo_exists guard
  - [x] `_on_excel_export_requested(data)` — xuất Excel thủ công (AC#9)
  - [x] `_on_student_add_requested(data)` — thêm SV (AC#10) + [F6-fix] class_id guard + [F11-fix] data mapping
  - [x] `_on_student_remove_requested(data)` — xóa SV (AC#11)
  - [x] `_on_shutdown(data)` — graceful shutdown (AC#12)
  - [x] `_on_error(data)` — error handling (AC#13)
  - [x] `_on_camera_stopped(data)` — camera disconnect (AC#14) [F13-fix]

- [x] Tạo `run()` method + `__main__` block (AC: #17)
  - [x] `run()`: `self.worker.start()` (Thread.start) → `camera.start()` → `_load_teacher_encodings()` → `worker.start_scanning(mode=1)` → `self._current_mode = 1` → `camera_panel.start_preview()` → `app.mainloop()` — ⚠️ **[F1-fix]**: `worker.start()` PHẢI gọi trước `start_scanning()` để thread chạy loop
  - [x] `if __name__ == '__main__':` block

- [x] Tạo `tests/test_main.py` (AC: #18)
  - [x] Mock tất cả dependencies (DatabaseManager, ClassManager, etc.)
  - [x] Test: Presenter khởi tạo thành công (components created in order)
  - [x] Test: TEACHER_DETECTED → enriched data truyền vào session_panel
  - [x] Test: TEACHER_DETECTED khi mode != 1 → bị bỏ qua [F3-fix]
  - [x] Test: SESSION_CONFIRMED → switch to Mode 2 + load student encodings
  - [x] Test: STUDENT_DETECTED → mark_present + update attendance_panel
  - [x] Test: STUDENT_DETECTED khi mode != 2 → bị bỏ qua [F3-fix]
  - [x] Test: SESSION_END_REQUESTED → end_session + export Excel + save _last_session_result
  - [x] Test: SESSION_END_REQUESTED duplicate → ValueError caught, no crash [F7-fix]
  - [x] Test: auto-reset sau 5 giây + winfo_exists guard [F12-fix]
  - [x] Test: EXCEL_EXPORT_REQUESTED → gọi exporter
  - [x] Test: STUDENT_ADD_REQUESTED → add student + add_to_class + update GUI [F11-fix]
  - [x] Test: STUDENT_ADD_REQUESTED khi class_id=None → on_error [F6-fix]
  - [x] Test: STUDENT_REMOVE_REQUESTED → remove student + update GUI
  - [x] Test: SHUTDOWN_REQUESTED → cleanup resources
  - [x] Test: ERROR_OCCURRED → log error
  - [x] Test: TEACHER_DETECTED khi check_timetable raise ValueError → handle gracefully
  - [x] Test: mark_present returns False → không update GUI
  - [x] Test: export_session raise OSError → log error + show error in GUI [F8-fix]
  - [x] Test: empty teacher encodings → worker.load_encodings([], []) no crash [F10-fix]
  - [x] Test: CAMERA_STOPPED → log warning + reset mode [F13-fix]
  - [x] Test: run() startup sequence — worker.start → camera.start → mainloop [PM-7]
  - [x] Test: _load_student_encodings filters encoding bởi class_id [PM-8]
  - [x] Test: STUDENT_REMOVE_REQUESTED error path → on_error [PM-9]
  - [x] Test: SESSION_END_REQUESTED resets _pending_class_id [PM-1/PM-5]
  - [x] Test: Excel export success → shows green feedback [PM-6]
  - [x] Test: SHUTDOWN sets _current_mode = None before cleanup [PM-2]

## Dev Notes

### Architecture Constraints (CRITICAL)

- **MVP Pattern**: `src/main.py` là PRESENTER layer. Nó import từ CẢ `src/core/` VÀ `src/gui/`. Các GUI panels KHÔNG import core ngoại trừ `events.py`. Core modules KHÔNG import GUI.
- **Thread Safety**: `RecognitionWorker` chạy trên background thread. Khi worker emit events (`TEACHER_DETECTED`, `STUDENT_DETECTED`), handler sẽ chạy trên worker thread (do `EventManager.emit()` gọi listener trực tiếp). Mọi GUI update PHẢI dùng `app.after(0, callback, *args)` để chuyển sang main thread.
- **Singleton Events**: Dùng `events` singleton từ `src.core.events`. Subscribe 1 lần trong `__init__()`, unsubscribe trong shutdown.
- **State Machine**: Presenter quản lý state nội bộ qua biến `self._current_mode` (1=teacher, 2=student, None=idle) và `self._current_class_id`, `self._current_teacher_id`, `self._last_session_result`.

### Component Initialization Order (EXACT)

```python
# src/main.py
import logging
import os
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

logger = logging.getLogger(__name__)

class Presenter:
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
        self.app.session_panel._scan_time_minutes = config.get('session', 'student_scan_time', default=60)
        
        # 5. State tracking
        self._current_mode = None          # 1=teacher, 2=student
        self._current_class_id = None
        self._pending_class_id = None      # Lưu class_id chờ xác nhận
        self._current_teacher_id = None
        self._last_session_result = None   # Lưu result để xuất Excel thủ công
        
        # 6. Wire camera → GUI
        self.app.camera_panel._get_frame_callback = self.camera.get_frame
        
        # 7. Setup events
        self._setup_events()

    def run(self):
        """[F1-fix] Start worker thread, camera, và GUI mainloop."""
        self.worker.start()          # Thread.start() — PHẢI gọi trước start_scanning()
        self.camera.start()
        self._load_teacher_encodings()
        self.worker.start_scanning(mode=1)
        self._current_mode = 1
        self.app.camera_panel.start_preview()
        self.app.mainloop()
```

### Event Wiring Map (CRITICAL)

```
EventType                    → Handler method
────────────────────────────────────────────────────
TEACHER_DETECTED             → _on_teacher_detected(data)
SESSION_CONFIRMED            → _on_session_confirmed(data)
STUDENT_DETECTED             → _on_student_detected(data)   ← ⚠️ CẢ worker LẪN session emit event này!
SESSION_END_REQUESTED        → _on_session_end_requested(data)
SESSION_STARTED              → (session emits — Presenter update GUI)
SESSION_ENDED                → (session emits — Presenter đã xử lý trong end_requested)
EXCEL_EXPORT_REQUESTED       → _on_excel_export_requested(data)
STUDENT_ADD_REQUESTED        → _on_student_add_requested(data)
STUDENT_REMOVE_REQUESTED     → _on_student_remove_requested(data)
SHUTDOWN_REQUESTED           → _on_shutdown(data)
ERROR_OCCURRED               → _on_error(data)
CAMERA_STOPPED               → _on_camera_stopped(data)   ← [F13-fix] log warning + reset mode
```

### ⚠️ CRITICAL: STUDENT_DETECTED Event Deduplication

`STUDENT_DETECTED` event được emit bởi **CẢ HAI** nguồn:
1. **RecognitionWorker** (file `worker.py` line 148) — khi worker nhận diện SV thành công
2. **AttendanceSession.mark_present()** (file `attendance_session.py` line 140) — khi session đánh dấu SV có mặt

Presenter PHẢI xử lý cẩn thận:
- Subscribe `STUDENT_DETECTED` **1 lần duy nhất**
- Trong `_on_teacher_detected()`, Presenter subscribe `TEACHER_DETECTED` từ worker
- Trong mode 2, worker emit `STUDENT_DETECTED` → Presenter handler gọi `session.mark_present()` → session CŨNG emit `STUDENT_DETECTED`
- **Giải pháp**: Presenter CHỈ xử lý `STUDENT_DETECTED` từ **worker** (chứa `person_id` + `confidence` + `coordinates`). Bỏ qua event thứ hai từ session (không có `coordinates`). Hoặc: kiểm tra `'coordinates' in data` để phân biệt nguồn.

### ⚠️ CRITICAL: confidence là 0-100 từ recognition.py

`recognition.py` → `calculate_confidence()` trả về giá trị **0-100** (ĐÃ nhân 100 rồi).
`worker.py` gửi `confidence` từ `find_best_match()` → đây là giá trị 0-100.
`AttendanceSession.mark_present()` lưu `confidence` nguyên bản từ caller.

**QUAN TRỌNG**: Khi gọi `session.mark_present(student_id, confidence/100, ...)`, phải **chia 100** để lưu dạng 0.0-1.0 trong session (vì ExcelExporter nhân 100 lại khi xuất). Hoặc giữ nguyên 0-100 nhưng thì ExcelExporter KHÔNG nhân 100.

**Kiểm chứng**: `recognition.py` line 148: `return float(max(0.0, min(100.0, round(val, 2))))` → trả về 0-100.
`ExcelExporter` AC#3 + line 43 story 6-1: `confidence * 100` → nếu input đã là 0-100 thì sẽ hiển thị 8500% (SAI!).

**Giải pháp chính xác**: Khi truyền confidence từ worker → session → excel:
```python
# Trong _on_student_detected():
raw_confidence = data.get('confidence')  # 0-100 từ recognition.py
session_confidence = raw_confidence / 100.0  # 0.0-1.0 cho session lưu trữ
self.session.mark_present(student_id, session_confidence, snapshot_path)
```
ExcelExporter sẽ nhân 100 lại → hiển thị đúng XX.X%.

### Data Flow Diagrams

```
Mode 1 (Chờ GV):
  CameraManager.get_frame() → RecognitionWorker (bg thread)
  → detect_faces() → encode_face() → find_best_match(teacher_encodings)
  → events.emit(TEACHER_DETECTED, {person_id, confidence, coordinates})
  → Presenter._on_teacher_detected()
  → [F3-fix] if _current_mode != 1: return
  → db.get_teacher() + session.check_timetable() + db.get_class()
  → app.after(0, session_panel.on_teacher_detected, enriched)
  → app.after(0, camera_panel.set_bounding_box, coords, 'green')

Mode 2 (Điểm danh SV):
  CameraManager.get_frame() → RecognitionWorker (bg thread)
  → find_best_match(student_encodings)
  → events.emit(STUDENT_DETECTED, {person_id, confidence, coordinates})
  → Presenter._on_student_detected()
  → [F3-fix] if _current_mode != 2: return
  → session.mark_present(student_id, confidence/100, snapshot_path)
  → [session emits STUDENT_DETECTED internally — IGNORE]
  → app.after(0, attendance_panel.add_record, enriched)
  → app.after(0, session_panel.on_student_detected, enriched)

Session End:
  SessionPanel countdown → events.emit(SESSION_END_REQUESTED)
  → Presenter._on_session_end_requested()
  → [F7-fix] try: worker.pause_scanning() → session.end_session()
  → [F4-fix] self._last_session_result = result
  → [F8-fix] try: ExcelExporter.export_session() except (ValueError, OSError)
  → app.after(0, update GUI panels)
  → app.after(5000, self._reset_to_teacher_mode)  # [F5-fix]

Auto-Reset:
  [F12-fix] if not app.winfo_exists(): return
  → reset panels → _load_teacher_encodings() → worker.start_scanning(mode=1)
```

### Encoding Loading Pattern (CRITICAL)

```python
def _load_teacher_encodings(self):
    """Load tất cả teacher encodings vào worker cho Mode 1."""
    raw_encodings = self.db.get_encodings_by_type('teacher')
    encodings = [r['encoding'] for r in raw_encodings]
    metadata = [{'person_id': r['person_id'], 'person_type': 'teacher'} for r in raw_encodings]
    self.worker.load_encodings(encodings, metadata)

def _load_student_encodings(self, class_id: int):
    """Load student encodings CHỈ cho lớp hiện tại vào worker cho Mode 2."""
    students = self.db.get_students_in_class(class_id)
    student_ids = {s['id'] for s in students}
    
    all_student_encodings = self.db.get_encodings_by_type('student')
    encodings = []
    metadata = []
    for r in all_student_encodings:
        if r['person_id'] in student_ids:
            encodings.append(r['encoding'])
            metadata.append({'person_id': r['person_id'], 'person_type': 'student'})
    
    self.worker.load_encodings(encodings, metadata)
    # ⚠️ [F2-note] O(N) filter — chấp nhận cho MVP. Tech debt cho future optimization.
```

### Anti-Pattern Prevention

| ❌ SAI | ✅ ĐÚNG |
|--------|---------|
| GUI panel gọi trực tiếp `DatabaseManager` | Presenter query DB rồi truyền data vào GUI |
| `session_panel.on_teacher_detected()` gọi từ worker thread | `app.after(0, session_panel.on_teacher_detected, data)` |
| Subscribe `STUDENT_DETECTED` và xử lý cả event từ session | Chỉ xử lý event có `'coordinates'` key (từ worker) |
| `confidence` từ worker (0-100) truyền thẳng vào session | Chia 100 trước khi truyền vào session (ExcelExporter sẽ nhân 100) |
| Gọi `app.mainloop()` trước khi start camera/worker | Start camera/worker trước, rồi `app.mainloop()` |
| Không cleanup khi shutdown | `worker.stop_scanning()` → `camera.stop()` → `app.destroy()` |
| `import *` hoặc circular imports | Import cụ thể, main.py import cả core + gui (Presenter role) |
| Hardcode scan_time_minutes | Đọc từ `Config().get('session', 'student_scan_time', default=60)` |
| Tạo multiple Presenter instances | Single Presenter, tạo trong `__main__` block |
| Không kiểm tra mode trong event handler | [F3-fix] Guard `if self._current_mode != expected: return` |
| Gọi `_reset_to_teacher_mode` không kiểm tra widget | [F12-fix] `if not self.app.winfo_exists(): return` |
| Gọi `_reset_to_teacher_mode` thiếu `self.` | [F5-fix] `self._reset_to_teacher_mode` |
| Không lưu session result cho xuất Excel | [F4-fix] `self._last_session_result = result` |

### GUI Panel Public API Summary

```python
# SessionPanel (src/gui/session_panel.py)
.on_teacher_detected(data)    # {'name', 'teacher_code', 'class_info', 'confidence', 'coordinates'}
.on_student_detected(data)    # {'name', 'student_code', 'confidence'}
.on_session_started(data)     # {'class_id', 'start_time'}
.on_session_ended(data)       # dict (any)
.reset()

# AttendancePanel (src/gui/attendance_panel.py)
.on_session_started(data)     # {'class_id', 'students': [{'student_id', 'name', 'student_code'}, ...]}
.add_record(data)             # {'student_id', 'name', 'student_code', 'confidence', 'mark_time'}
.on_session_ended(data)       # session result dict
.reset()

# StudentPanel (src/gui/student_panel.py)
.on_students_loaded(students) # [{'student_id', 'name', 'student_code'}, ...]
.on_student_added(data)       # {'student_id', 'name', 'student_code'}
.on_student_removed(sid)      # int
.on_error(message, color)     # str, str
.reset()

# CameraPanel (src/gui/camera_panel.py)
.start_preview()
.stop_preview()
.set_bounding_box(coords, color)  # dict, str
.clear_bounding_box()
```

### Project Structure Notes

- **File tạo mới**: `src/__init__.py` (empty, nếu chưa tồn tại), `src/main.py`, `tests/test_main.py`
- **Files KHÔNG sửa**: Tất cả core modules + GUI panels đã hoàn thành và đã qua code review. KHÔNG sửa bất kỳ file nào khác.
- Entry point: `python -m src.main` (cần `src/__init__.py` nếu chưa có) hoặc `python src/main.py`
- `src/main.py` là file DUY NHẤT import cả `src.core` và `src.gui`
- ⚠️ `src/__init__.py` PHẢI tồn tại (có thể empty) để `python -m src.main` hoạt động

### References

- [Source: src/core/events.py](file:///Users/huynguyen/work/projects/BtlPython/src/core/events.py) — EventManager singleton + EventType constants (all 11 events)
- [Source: src/core/database.py](file:///Users/huynguyen/work/projects/BtlPython/src/core/database.py) — DatabaseManager CRUD: `get_teacher()`, `get_class()`, `get_students_in_class()`, `get_encodings_by_type()`
- [Source: src/core/class_manager.py](file:///Users/huynguyen/work/projects/BtlPython/src/core/class_manager.py) — ClassManager: `get_classes_by_teacher()`, `get_timetable_by_class()`, `get_students_in_class()`
- [Source: src/core/student_manager.py](file:///Users/huynguyen/work/projects/BtlPython/src/core/student_manager.py) — StudentManager: `add_student()`, `remove_student()`
- [Source: src/core/attendance_session.py](file:///Users/huynguyen/work/projects/BtlPython/src/core/attendance_session.py) — AttendanceSession: `check_timetable()`, `start_session()`, `mark_present()`, `end_session()`, `is_expired()`
- [Source: src/core/camera.py](file:///Users/huynguyen/work/projects/BtlPython/src/core/camera.py) — CameraManager: `start()`, `stop()`, `get_frame()`
- [Source: src/core/worker.py](file:///Users/huynguyen/work/projects/BtlPython/src/core/worker.py) — RecognitionWorker: `load_encodings()`, `start_scanning(mode)`, `pause_scanning()`, `stop_scanning()`
- [Source: src/core/recognition.py](file:///Users/huynguyen/work/projects/BtlPython/src/core/recognition.py) — `calculate_confidence()` returns 0-100 (line 148)
- [Source: src/core/excel_export.py](file:///Users/huynguyen/work/projects/BtlPython/src/core/excel_export.py) — ExcelExporter: `export_session(session_result, class_info, teacher_info)` → str
- [Source: src/gui/app.py](file:///Users/huynguyen/work/projects/BtlPython/src/gui/app.py) — App(CTk): 4-panel layout, `on_closing()` emits SHUTDOWN_REQUESTED
- [Source: src/gui/session_panel.py](file:///Users/huynguyen/work/projects/BtlPython/src/gui/session_panel.py) — SessionPanel: 3 states, countdown, emits SESSION_CONFIRMED/SESSION_END_REQUESTED
- [Source: src/gui/camera_panel.py](file:///Users/huynguyen/work/projects/BtlPython/src/gui/camera_panel.py) — CameraPanel: `_get_frame_callback`, `start_preview()`, `set_bounding_box()`
- [Source: src/gui/attendance_panel.py](file:///Users/huynguyen/work/projects/BtlPython/src/gui/attendance_panel.py) — AttendancePanel: `on_session_started()`, `add_record()`, `on_session_ended()`
- [Source: src/gui/student_panel.py](file:///Users/huynguyen/work/projects/BtlPython/src/gui/student_panel.py) — StudentPanel: `on_students_loaded()`, `on_student_added()`, emits EXCEL_EXPORT_REQUESTED
- [Source: config.yaml](file:///Users/huynguyen/work/projects/BtlPython/config.yaml) — camera_id, tolerance, scan_interval, student_scan_time=60
- [Source: sprint-status.yaml#E6-S2](file:///Users/huynguyen/work/projects/BtlPython/_bmad-output/implementation-artifacts/sprint-status.yaml) — Story requirements (lines 341-349)

### Previous Story Intelligence (6-1-excel-export)

**Learnings to apply:**
- `Config()` Singleton — dùng trực tiếp, không truyền qua constructor
- Logging pattern: `logger = logging.getLogger(__name__)` ở đầu file
- Error messages bằng Tiếng Việt
- `ExcelExporter` là stateless, tạo 1 instance trong Presenter
- `export_session()` trả về absolute path file → log path này
- Confidence conversion: `ExcelExporter` nhân 100 → input PHẢI là 0.0-1.0
- Party-mode review findings: defensive guards cho None values, `str()` cast trong sort key
- Testing pattern: mock `Config().get()` bằng `monkeypatch` hoặc `unittest.mock.patch.object`

### Technology Notes

- **CustomTkinter**: `app.after(0, callback, *args)` an toàn để gọi từ thread khác. Callback sẽ chạy trên main thread trong event loop tick tiếp theo.
- **threading.Thread(daemon=True)**: Worker thread tự tắt khi main thread exit. Nhưng vẫn cần `stop_scanning()` để cleanup sạch.
- **Python entry point**: `if __name__ == '__main__':` + `python -m src.main` cần file `src/__main__.py` (hoặc chạy trực tiếp `python src/main.py`).
- **Logging format**: `'%(asctime)s - %(name)s - %(levelname)s - %(message)s'` — đồng nhất với các module đã có.

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (Thinking)

### Debug Log References

- Tất cả 31 unit tests passed trong 1.59s
- Full regression suite: 264 tests passed trong 8.71s, 0 failures

### Completion Notes List

- ✅ Tạo `src/__init__.py` — empty file cho `python -m src.main`
- ✅ Tạo `src/main.py` — Presenter class (~480 dòng) với:
  - Component initialization theo đúng dependency order (AC#2)
  - Camera→GUI wiring + config override (AC#3)
  - 10 event handlers covering AC#4-#14
  - Mode guards [F3-fix], duplicate guards [F7-fix], winfo_exists guard [F12-fix]
  - Confidence conversion 0-100 → 0.0-1.0 (AC#6)
  - Session result caching [F4-fix] cho manual export (AC#9)
  - Export error handling [F8-fix]
  - Graceful shutdown + auto-reset after 5s (AC#8, #12)
  - Entry point `if __name__ == '__main__'` (AC#17)
- ✅ Tạo `tests/test_main.py` — 31 test cases (vượt AC#18 yêu cầu 18 tests):
  - Component init verification
  - All event handler flows
  - Mode guard tests [F3-fix]
  - Duplicate session end [F7-fix]
  - winfo_exists guard [F12-fix]
  - Export error handling [F8-fix]
  - Empty encodings [F10-fix]
  - Camera disconnect [F13-fix]
  - Startup sequence [PM-7]
  - Student encoding filtering [PM-8]
  - Student remove error path [PM-9]
  - Pending state reset [PM-1/PM-5]
  - Export success feedback [PM-6]
  - Shutdown mode neutralization [PM-2]

### File List

- `src/__init__.py` — NEW (empty, cho python -m src.main)
- `src/main.py` — NEW (Presenter layer, ~480 dòng)
- `tests/test_main.py` — NEW (31 unit tests)

### Change Log

- 2026-05-04: Implement E6-S2 Integration-Main — Presenter orchestrator hoàn chỉnh với 10 event handlers, state machine (Mode 1/2/idle), thread-safe GUI updates, confidence conversion, encoding loading, auto-reset, graceful shutdown. 23 tests passed, 256 regression tests passed.
- 2026-05-04: Adversarial code review (CR-1–CR-9) — 9 findings remediated: mode guard on SESSION_CONFIRMED (CR-1), camera_stopped GUI fix (CR-2), pending_class_id None guard (CR-3), narrowed exception handler (CR-4), defensive DB None guards (CR-6/7/8), test docstring (CR-9), 2 new tests (CR-10/11). 25 tests passed, 258 regression tests passed.
- 2026-05-04: Party-mode review #2 (PM-1–PM-6) — 6 findings remediated: stale state reset (PM-1/PM-5), shutdown mode neutralization (PM-2), narrowed exception handler (PM-3), pause_scanning outside try (PM-4), export success feedback (PM-6). 6 new tests. 31 tests passed, 264 regression tests passed.
