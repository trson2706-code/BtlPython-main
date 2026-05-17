# Story 8.2: Presenter wiring — kết nối Admin vào main flow

Status: done

## Story

Là quản trị viên hệ thống,
Tôi muốn mở cửa sổ quản lý (Admin) trực tiếp từ giao diện chính khi hệ thống đang chờ giảng viên,
Để tôi có thể thêm/sửa/xóa GV, SV, Lớp, TKB mà không cần khởi động lại ứng dụng, và dữ liệu encoding được tải lại tự động khi đóng Admin.

## Acceptance Criteria

### AC1: EventType.ADMIN_REQUESTED tồn tại
- Thêm `ADMIN_REQUESTED = "admin_requested"` vào class `EventType` trong `src/core/events.py`
- Không ảnh hưởng tới các EventType hiện có (11 constants hiện tại)

### AC2: Nút [⚙️ Quản lý] trên SessionPanel
- Thêm nút `admin_button` (text "⚙️ Quản lý") vào `SessionPanel`, pack sau `end_button`
- State management theo SessionPanel states:
  - `WAITING_TEACHER` → `state="normal"` (user có thể mở admin)
  - `ATTENDANCE_ACTIVE` → `state="disabled"` (set trong `on_session_started()`)
  - `SESSION_ENDED` → `state="disabled"` (set trong `on_session_ended()`)
- Khi bấm → emit `EventType.ADMIN_REQUESTED` (data={})
- `reset()` → `admin_button.configure(state="normal")` (quay về WAITING_TEACHER)
- `on_teacher_detected()` → KHÔNG thay đổi admin_button state (vẫn normal — user có thể mở admin trước khi confirm, vì admin là modal sẽ block mọi interaction khác)

### AC3: Presenter subscribe ADMIN_REQUESTED
- Trong `_setup_events()` → thêm subscribe `EventType.ADMIN_REQUESTED` → `self._on_admin_requested`
- Handler `_on_admin_requested(self, data)`:
  - Mode guard: `if self._current_mode != 1: return`
  - Double-open guard: `if self._admin_window is not None: return`

### AC4: Pause worker khi Admin mở
- Trong `_on_admin_requested()`: gọi `self.worker.pause_scanning()` **trước** khi tạo AdminWindow
- Worker thread sẽ không emit TEACHER_DETECTED trong khi Admin đang mở

### AC5: Tạo AdminWindow từ Presenter
- `self._admin_window = AdminWindow(self.app, self.class_mgr, self.student_mgr, self.db)` 
- Parent là `self.app` (CTk root window)
- AdminWindow tự `grab_set()` + `transient(parent)` trong constructor (đã implement E8-S1)
- **Override** AdminWindow protocol: `self._admin_window.protocol("WM_DELETE_WINDOW", self._on_admin_closed)`
  - Đây sẽ override `AdminWindow._on_close()` — Presenter kiểm soát lifecycle

### AC6: Resume + reload khi Admin đóng
- `_on_admin_closed(self)` handler:
  1. Defensive grab_release: `try: self._admin_window.grab_release() except: pass`
  2. `self._admin_window.destroy()`
  3. `self._admin_window = None`
  4. `self._load_teacher_encodings()` — reload encoding mới (GV mới/xóa)
  5. `self.worker.start_scanning(mode=1)` — resume quét GV
- Phát hiện đóng bằng **protocol override** (KHÔNG dùng polling)

### AC7: Tests — thêm ≥5 test cases vào `test_main.py`
- Test 30: `_on_admin_requested` khi mode=1 → pause worker + tạo AdminWindow + override protocol
- Test 31: `_on_admin_requested` khi mode≠1 → bị bỏ qua (mode guard)
- Test 32: `_on_admin_requested` khi admin đang mở → bị bỏ qua (double-open guard)
- Test 33: `_on_admin_closed` → grab_release + destroy + reload encodings + resume scanning
- Test 34: ADMIN_REQUESTED nằm trong danh sách events subscribed
- Baseline: 29 tests hiện có phải pass 100%

---

## Tasks / Subtasks

- [x] Task 1 (AC: #1): Thêm EventType.ADMIN_REQUESTED
  - [x] Thêm 1 dòng `ADMIN_REQUESTED = "admin_requested"` vào `EventType` class trong `src/core/events.py` (sau `EXCEL_EXPORT_REQUESTED`)

- [x] Task 2 (AC: #2): Thêm nút [⚙️ Quản lý] vào SessionPanel
  - [x] Thêm `self.admin_button` CTkButton trong `__init__()`, pack sau `self.end_button` (line ~89)
  - [x] Text: "⚙️ Quản lý", font: `CTkFont(size=14)`, initial state: "normal"
  - [x] Command: `self._on_admin_click` → gọi `events.emit(EventType.ADMIN_REQUESTED, {})`
  - [x] Thêm `self._on_admin_click()` private method
  - [x] Trong `on_session_started()` (line ~128): thêm `self.admin_button.configure(state="disabled")`
  - [x] Trong `on_session_ended()` (line ~143): thêm `self.admin_button.configure(state="disabled")`
  - [x] Trong `reset()` (line ~155): thêm `self.admin_button.configure(state="normal")`

- [x] Task 3 (AC: #3, #4, #5, #6): Wiring trong Presenter (main.py)
  - [x] Import: thêm `from src.gui.admin_window import AdminWindow` (line ~26)
  - [x] Init: thêm `self._admin_window = None` trong `__init__()` (sau `self._last_session_result`)
  - [x] Subscribe: thêm `events.subscribe(EventType.ADMIN_REQUESTED, self._on_admin_requested)` trong `_setup_events()`
  - [x] Handler `_on_admin_requested(self, data)` — mode guard + double-open guard + pause + create + override protocol
  - [x] Handler `_on_admin_closed(self)` — grab_release + destroy + clear pending + reload + camera check + resume/idle

- [x] Task 4 (AC: #7): Tests
  - [x] Test 30: `test_admin_requested_mode1_opens_window`
  - [x] Test 31: `test_admin_requested_wrong_mode_ignored`
  - [x] Test 32: `test_admin_requested_double_open_guard`
  - [x] Test 33: `test_admin_closed_reloads_and_resumes`
  - [x] Test 34: `test_admin_requested_event_subscribed`
  - [x] Mock pattern: `patch('src.main.AdminWindow')` — mock AdminWindow constructor
  - [x] Updated Test 1 expected events + init assertions for ADMIN_REQUESTED

---

## Dev Notes

### Architecture Pattern (MVP)
- **Presenter** (`src/main.py`) là orchestrator duy nhất — KHÔNG để View layer gọi Model trực tiếp
- AdminWindow được tạo từ Presenter, truyền references trực tiếp (class_mgr, student_mgr, db) — đây là **exception** cho admin flow (sync CRUD, không qua event system)
- Event `ADMIN_REQUESTED` chỉ đi từ View → Presenter. AdminWindow CRUD operations KHÔNG dùng event system
- Presenter override `protocol("WM_DELETE_WINDOW")` để kiểm soát lifecycle — chen reload/resume logic trước destroy

### Implementation Details

**Protocol override pattern:**
AdminWindow constructor gọi `self.protocol("WM_DELETE_WINDOW", self._on_close)` tại line 32. Presenter override CÙNG protocol key → Tk chỉ giữ handler cuối cùng. Kết quả: khi user đóng window, `_on_admin_closed()` của Presenter chạy thay cho `_on_close()` của AdminWindow.

**Double-open guard:**
Nếu user click nhanh, event ADMIN_REQUESTED có thể fire 2 lần trước khi AdminWindow kịp grab_set(). Guard `self._admin_window is not None` ngăn tạo window thứ 2.

**Admin button color:**
Không dùng fg_color đặc biệt — dùng default theme color (xanh), phân biệt với end_button (đỏ). Giữ consistent với confirm_button style.

### Thread Safety
- `worker.pause_scanning()` và `start_scanning()` đều thread-safe (dùng `threading.Lock`)
- `_load_teacher_encodings()` gọi `db.get_encodings_by_type()` từ main thread — an toàn (SQLite serializes reads)
- AdminWindow chạy hoàn toàn trên main thread (GUI) — không có threading issue
- Mode guard check `self._current_mode` từ main thread (event handler) — an toàn

### Tương thích ngược
- Không sửa đổi signature của AdminWindow constructor — vẫn `(parent, class_mgr, student_mgr, db)`
- Không sửa đổi behavior của các event handler hiện có
- 29 test cases cũ trong test_main.py phải pass 100%
- SessionPanel public API unchanged — chỉ thêm button, không sửa existing methods' signatures

### Project Structure Notes
- `src/core/events.py` line 51: Thêm 1 constant `ADMIN_REQUESTED`, sau `EXCEL_EXPORT_REQUESTED`
- `src/gui/session_panel.py` line 89: Thêm button sau `end_button.pack()`
- `src/gui/session_panel.py` line 128, 143, 155: Thêm `admin_button.configure(state=...)` calls
- `src/main.py` line 26: Thêm import `AdminWindow`
- `src/main.py` line 61: Thêm `self._admin_window = None`
- `src/main.py` line 84: Thêm subscribe `ADMIN_REQUESTED`
- `src/main.py`: Thêm 2 methods `_on_admin_requested`, `_on_admin_closed`
- `tests/test_main.py`: Thêm 5 test methods, mock AdminWindow

### Previous Story Intelligence (E8-S1)
- AdminWindow constructor: `AdminWindow(parent, class_mgr, student_mgr, db)` — verified at admin_window.py:22
- `_on_close()` uses `self.protocol("WM_DELETE_WINDOW", self._on_close)` at line 32 — Presenter override replaces this
- AdminWindow tự `grab_set()` tại line 31 → modal behavior automatic
- AdminWindow exported in `src/gui/__init__.py` line 7
- [CR-9] `_on_close()` đã có defensive `grab_release()` at line 51-55

### Anti-Patterns to AVOID
- ❌ KHÔNG import AdminWindow trong session_panel — View layer không tạo View khác
- ❌ KHÔNG dùng `bind("<Destroy>")` — event này fire cho mọi child widget (tabview, scrollframes), gây duplicate calls
- ❌ KHÔNG dùng polling (`self.app.after(500, ...)`) — protocol override chính xác hơn và không tốn CPU
- ❌ KHÔNG quên `worker.start_scanning(mode=1)` sau khi admin đóng — sẽ brick Mode 1 (worker stays paused forever)
- ❌ KHÔNG gọi `_load_student_encodings()` khi admin đóng — Mode 1 chỉ cần teacher encodings
- ❌ KHÔNG tạo AdminWindow khi `_admin_window is not None` — double-open sẽ crash grab system

### Test Mock Pattern
```python
# In setUp(), add to existing patches:
p_admin = patch('src.main.AdminWindow')
self.MockAdminWindow = p_admin.start()
# Mock AdminWindow instance:
self.mock_admin = MagicMock()
self.MockAdminWindow.return_value = self.mock_admin
```

### References
- [Source: src/core/events.py#L38-L51] — EventType class, 11 existing constants
- [Source: src/gui/session_panel.py#L78-L89] — end_button placement, pack pattern
- [Source: src/gui/session_panel.py#L128-L164] — on_session_started, on_session_ended, reset
- [Source: src/main.py#L25-L26] — import section
- [Source: src/main.py#L56-L61] — state tracking section
- [Source: src/main.py#L73-L84] — _setup_events, subscribe calls
- [Source: src/gui/admin_window.py#L21-L56] — constructor, _on_close, protocol binding
- [Source: src/core/worker.py#L53-L68] — start_scanning, pause_scanning API
- [Source: tests/test_main.py#L15-L72] — setUp/tearDown mock pattern
- [Source: _bmad-output/implementation-artifacts/8-1-admin-window-gui.md] — Previous story

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (Thinking)

### Debug Log References

### Completion Notes List

- Story context engine analysis completed — comprehensive developer guide created
- Validation checklist executed — 7 findings identified and fixed:
  - [F1] Added double-open guard in AC3 and Task 3
  - [F2] Added explicit admin_button disable in `on_session_ended()` (AC2)
  - [F3] Removed ambiguous "polling" option — mandated protocol override only (AC6, Task 3)
  - [F4] Clarified modal behavior prevents stale interaction during admin open
  - [F5] Noted mode context safety for `_on_admin_closed`
  - [F6] Fixed test baseline reference to 29 tests (not 25) in AC7
  - [F7] Added Test 32 for double-open guard scenario
- Adversarial review (Party Mode Solo) executed during implementation — 4 additional fixes:
  - [F7/F9-fix] `_on_admin_closed` sets `_current_mode = 1` after resume to prevent mode guard deadlock
  - [F10-fix] `_on_admin_closed` clears `_pending_class_id` to prevent stale state leak
  - [A2-fix] Camera alive check via `camera.is_opened()` before resuming scanning
  - [F8-fix] Updated test docstring count from 31 to 34
- Implementation verified: 36/36 tests pass (29 baseline + 5 new + 2 updated assertions in Test 1)
- CR2 Party Mode Solo adversarial review — 5 actionable findings fixed:
  - [CR2-F4] `_on_admin_requested` neutralizes `_current_mode = None` immediately after `pause_scanning()` — prevents stale TEACHER_DETECTED race
  - [CR2-F1] `_on_admin_closed` camera-dead path: calls `session_panel.reset()` to clear stale teacher info
  - [CR2-F5] `_on_admin_closed`: admin button re-enabled ONLY in camera-alive branch (avoid enabled-but-non-functional UX)
  - [CR2-F8] `_on_admin_closed`: `_load_teacher_encodings()` moved inside camera-alive branch (avoid wasted DB call)
  - [CR2-F7/F9] Added 2 new test cases: stale teacher detection during admin open + admin request when idle
- Post-CR2 verification: 40/40 tests pass (38 + 2 new)

### File List

| File | Action |
|------|--------|
| `src/core/events.py` | MODIFY — Add ADMIN_REQUESTED constant to EventType class |
| `src/gui/session_panel.py` | MODIFY — Add admin_button + state management in 4 methods + _on_admin_click handler |
| `src/main.py` | MODIFY — Import AdminWindow, add state var, subscribe event, add 2 handler methods with CR2 review fixes |
| `src/core/camera.py` | MODIFY — Add is_opened() public API for camera state check |
| `tests/test_main.py` | MODIFY — Add 7 new test cases (Tests 30-38) + update Test 1 assertions |
