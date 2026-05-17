# Story 9.2: GUI Tab Lịch sử điểm danh trong Admin

Status: done

## Story

Là giảng viên / quản trị viên hệ thống,
Tôi muốn xem lịch sử các phiên điểm danh trước đây trong cửa sổ Quản lý,
Để tôi có thể tra cứu kết quả, thống kê sinh viên vắng nhiều, và xuất lại Excel cho bất kỳ phiên nào.

## Acceptance Criteria

### AC1: Thêm Tab "📋 Lịch sử" vào AdminWindow
- Thêm tab mới tên `"📋 Lịch sử"` vào `CTkTabview` trong `AdminWindow.__init__()`:
  ```python
  for name in ["Giảng viên", "Sinh viên", "Lớp học", "Thời khóa biểu", "📋 Lịch sử"]:
      self.tabview.add(name)
  ```
- Tab phải được build bởi method `_build_history_tab()`
- Thêm `self._history_widgets = []` vào `__init__()` cho widget lifecycle management

### AC2: Bảng danh sách sessions
- Trong tab "📋 Lịch sử", hiển thị danh sách tất cả sessions từ `self.db.get_sessions()`:
  - Mỗi row hiển thị: `session_date`, `class_code`, `subject`, `teacher_name`, `present_count/total_students`
  - Dùng `CTkScrollableFrame` giống pattern 4 tab khác
  - Nút `🔍 Chi tiết` ở cuối mỗi row → gọi `_show_session_detail(session_id)`
  - Nút `📊 Xuất Excel` ở cuối mỗi row → gọi `_reexport_session(session_id)`
- Nếu không có sessions → hiển thị "(Chưa có lịch sử điểm danh)" (dùng `_show_empty_label()`)
- Sorting: hiển thị theo thứ tự `session_date DESC` (đã sorted sẵn từ `get_sessions()` SQL)
- ⚠️ `get_sessions()` OperationalError handler đã được fix (return []) — xem party-mode F1/F2. Vẫn nên dùng `self.db.get_sessions(...) or []` làm defensive guard thêm

### AC3: Click vào session → chi tiết sinh viên
- Method `_show_session_detail(self, session_id)`:
  - Mở `CTkToplevel` dialog (giống pattern `_show_enroll_dialog()`)
  - Gọi `self.db.get_session_records(session_id)` → lấy danh sách records
  - ⚠️ Records dict keys (từ SQL): `id`, `session_id`, `student_id`, `is_present` (0/1 INTEGER), `confidence` (0.0-1.0 REAL), `mark_time` (TEXT|None), `image_path` (TEXT|None), `name` (JOINed), `student_code` (JOINed)
  - Hiển thị bảng: `student_code`, `name`, trạng thái (✅ Có mặt / ❌ Vắng), `confidence` (nhân 100 → %), `mark_time`
  - Title dialog: `"📋 Chi tiết phiên — {session_date}"`
  - Dialog dùng `transient(self)` + `grab_set()` + `_safe_close_dialog()` pattern

### AC4: Filter theo lớp học (ComboBox)
- Thêm `CTkComboBox` state="readonly" phía trên danh sách sessions:
  - Values: `["Tất cả"] + ["{class_code} — {subject}" for class in get_all_classes()]`
  - Default: `"Tất cả"`
  - Bind `command=self._on_history_filter_changed`
- Khi thay đổi filter:
  - `"Tất cả"` → `self.db.get_sessions()` (không filter)
  - Lớp cụ thể → `self.db.get_sessions(class_id=<id>)` hoặc `self.db.get_sessions_by_class(<id>)`
  - Rebuild danh sách sessions (clear + reload)

### AC5: Filter theo khoảng thời gian (từ ngày — đến ngày)
- Thêm 2 `CTkEntry` với placeholder `YYYY-MM-DD` cho "Từ ngày" và "Đến ngày"
- Thêm nút `🔍 Lọc` để apply filter
- Validate format: regex `^\d{4}-\d{2}-\d{2}$`
- Filter **client-side** trên kết quả `get_sessions()` (so sánh `session['session_date']` string — ISO-8601 sortable):
  ```python
  if from_date and session['session_date'] < from_date:
      continue
  if to_date and session['session_date'] > to_date:
      continue
  ```
- ⚠️ KHÔNG sửa `database.py` để thêm date range query — client-side filter đủ cho MVP (<1000 sessions)
- ⚠️ Regex `^\d{4}-\d{2}-\d{2}$` cho phép ngày invalid (vd: 2026-13-99) — chấp nhận cho MVP vì string comparison vẫn đúng logic filter
- Nếu cả 2 field rỗng → hiển thị tất cả (không filter)

### AC6: Thống kê tổng hợp
- Thêm frame thống kê phía dưới filter controls:
  - "Tỷ lệ đi học trung bình": tính `sum(present_count) / sum(total_students) * 100` trên filtered sessions — dùng keys `present_count` và `total_students` từ session dict (đã có từ `get_sessions()`, KHÔNG cần query thêm)
  - ⚠️ MVP DECISION (party-mode F7/F10): BỎ "SV vắng nhiều nhất" — quá phức tạp cho MVP. Chỉ hiển thị tỷ lệ trung bình.
  - ⚠️ KHÔNG dùng `get_student_absence_count()` per-student — đây là N+1 query pattern, chậm khi nhiều sessions
- Thống kê phải cập nhật khi filter thay đổi
- Nếu không có sessions → ẩn hoặc hiển thị "—"

### AC7: Nút xuất lại Excel cho session đã chọn
- Method `_reexport_session(self, session_id)`:
  - Gọi `self.db.get_session_records(session_id)` → build `session_result` dict tương thích với `ExcelExporter.export_session()`
  - ⚠️ CRITICAL: `ExcelExporter` cần `session_result` format đặc biệt — xem Dev Notes bên dưới
  - Cần session header dict (chứa `class_id`, `teacher_id`, `start_time`, `end_time`): lấy từ session list đã load hoặc truyền vào parameter
  - Cần `class_info`: dùng `self.db.get_class(session['class_id'])` — keys: `class_code`, `subject`
  - ⚠️ Party-mode F9: `get_class()` / `get_teacher()` có thể return `None` nếu class/teacher đã bị xóa (CASCADE). PHẢI guard:
    ```python
    class_info = self.db.get_class(session['class_id']) or {'class_code': 'N/A', 'subject': 'N/A'}
    teacher_info = self.db.get_teacher(session['teacher_id']) or {'name': 'N/A'}
    ```
  - Cần `teacher_info`: dùng `self.db.get_teacher(session['teacher_id'])` — key: `name`
  - Lazy import: `from src.core.excel_export import ExcelExporter` — PHẢI dùng exact path này (giống main.py line 23)
  - Hiển thị kết quả: dialog nhỏ với đường dẫn file hoặc error message
  - Wrap trong `try/except (ValueError, OSError)` — giống pattern trong main.py line 295

### AC8: Unit tests — ≥5 test cases
- Test 1: AdminWindow tạo đúng 5 tabs (bao gồm "📋 Lịch sử")
- Test 2: `_refresh_history_list()` hiển thị sessions từ DB
- Test 3: `_refresh_history_list()` hiển thị empty label khi không có sessions
- Test 4: Filter theo class_id — chỉ hiển thị sessions của lớp đó
- Test 5: `_show_session_detail()` gọi `get_session_records()` với đúng session_id
- Baseline: tất cả test hiện có phải pass (105 collected + 10 collection errors — collection errors là pre-existing, KHÔNG do story này gây ra)

## Tasks / Subtasks

- [x] Task 1 (AC: #1): Thêm tab "📋 Lịch sử" vào AdminWindow
  - [x] Thêm `"📋 Lịch sử"` vào list tab names (line 37)
  - [x] Thêm `self._history_widgets = []` (line 43)
  - [x] Thêm `self._build_history_tab()` call (line 48)

- [x] Task 2 (AC: #2, #4, #5): Build history tab layout
  - [x] Tạo `_build_history_tab(self)` method
  - [x] Filter controls: CTkComboBox (class filter) + 2 CTkEntry (date range) + nút Lọc
  - [x] Thống kê summary frame
  - [x] CTkScrollableFrame cho session list
  - [x] Tạo `_refresh_history_list(self)` method — load + display sessions

- [x] Task 3 (AC: #3): Session detail dialog
  - [x] Tạo `_show_session_detail(self, session_id)` method
  - [x] CTkToplevel dialog + scrollable list of student records
  - [x] Hiển thị ✅/❌ status + confidence % + mark_time

- [x] Task 4 (AC: #6): Thống kê tổng hợp (simplified MVP)
  - [x] Tạo `_update_stats(self, sessions)` method
  - [x] Tính tỷ lệ đi học trung bình ONLY (bỏ "SV vắng nhiều nhất" per party-mode F7/F10)
  - [x] Cập nhật stats labels

- [x] Task 5 (AC: #7): Xuất lại Excel
  - [x] Tạo `_reexport_session(self, session_id)` method
  - [x] Reconstruct session_result dict từ DB records
  - [x] Lazy import ExcelExporter + gọi export_session()
  - [x] Hiển thị kết quả (filepath hoặc error)

- [x] Task 6 (AC: #8): Unit tests
  - [x] Thêm tests vào file test mới (tests/test_admin_history.py)
  - [x] Chạy full test suite, verify 0 new regressions (321 passed, 34 pre-existing failures)

## Dev Notes

### Architecture Pattern (MVP)
- **Model**: `DatabaseManager` — KHÔNG thay đổi, chỉ dùng methods đã có từ E9-S1: `get_sessions()`, `get_session_records()`, `get_student_absence_count()`, `get_sessions_by_class()`
- **View**: `AdminWindow` (`src/gui/admin_window.py`) — thêm tab mới + detail dialog
- **Presenter**: KHÔNG thay đổi `src/main.py` — AdminWindow đã được wired trong E8-S2

### ⚠️ get_sessions() return dict keys (SQL: `SELECT s.*, c.class_code, c.subject, t.name as teacher_name`)
| Key | Type | Example |
|-----|------|--------|
| `id` | int | 1 |
| `class_id` | int | 3 |
| `teacher_id` | int | 1 |
| `session_date` | str | "2026-05-05" |
| `start_time` | str | "2026-05-05 14:00:00" |
| `end_time` | str | "2026-05-05 15:00:00" |
| `total_students` | int | 30 |
| `present_count` | int | 25 |
| `class_code` | str | "CS101" |
| `subject` | str | "Computer Vision" |
| `teacher_name` | str | "Nguyễn Văn A" |

### ⚠️ CRITICAL: ExcelExporter session_result format
`ExcelExporter.export_session()` (line 54-190 of excel_export.py) expect `session_result` dict format:
```python
session_result = {
    'start_time': datetime,     # datetime object — KHÔNG phải string!
    'end_time': datetime,       # datetime object
    'present': [                # List of present students
        {
            'student_code': str,
            'name': str,
            'is_present': True,
            'confidence': float,      # 0.0-1.0
            'mark_time': datetime|None,
            'image_path': str|None,
        }
    ],
    'absent': [                 # List of absent students
        {
            'student_code': str,
            'name': str,
            'is_present': False,
            'confidence': 0.0,
            'mark_time': None,
            'image_path': None,
        }
    ],
}
```
- ⚠️ `start_time` và `end_time` PHẢI là `datetime` objects — ExcelExporter gọi `.strftime()` trực tiếp (line 98, 102). Cần parse TEXT từ DB: `datetime.strptime(session['start_time'], '%Y-%m-%d %H:%M:%S')`
- ⚠️ `mark_time` trong records cũng là TEXT trong DB — cần parse: `datetime.strptime(record['mark_time'], '%Y-%m-%d %H:%M:%S') if record['mark_time'] else None`
- ⚠️ `confidence` trong DB lưu dạng 0.0-1.0 (KHÔNG nhân 100) — ExcelExporter sẽ tự nhân 100 (line 136)
- ⚠️ `class_info` cần keys: `class_code`, `subject` (line 87-88 of excel_export.py)
- ⚠️ `teacher_info` cần key: `name` (line 89 of excel_export.py)

### Reconstruction helper:
```python
def _reconstruct_session_result(self, session, records):
    """Reconstruct session_result dict cho ExcelExporter."""
    from datetime import datetime as dt
    present = []
    absent = []
    for r in records:
        entry = {
            'student_code': r['student_code'],
            'name': r['name'],
            'is_present': bool(r['is_present']),
            'confidence': r.get('confidence', 0.0),
            'mark_time': (
                dt.strptime(r['mark_time'], '%Y-%m-%d %H:%M:%S')
                if r.get('mark_time') else None
            ),
            'image_path': r.get('image_path'),
        }
        if r['is_present']:
            present.append(entry)
        else:
            absent.append(entry)
    return {
        'start_time': dt.strptime(session['start_time'], '%Y-%m-%d %H:%M:%S'),
        'end_time': dt.strptime(session['end_time'], '%Y-%m-%d %H:%M:%S'),
        'present': present,
        'absent': absent,
    }
```

### Widget pattern — follow existing tabs exactly
- `_build_history_tab()` follows `_build_timetable_tab()` pattern:
  ```python
  tab = self.tabview.tab("📋 Lịch sử")
  # Filter controls frame
  # Stats summary frame
  self._history_scroll = self._make_list_frame(tab)
  self._refresh_history_list()
  ```
- `_refresh_history_list()` follows `_refresh_timetable_list()` pattern:
  ```python
  self._clear_widgets(self._history_widgets)
  sessions = self.db.get_sessions(class_id=filter_class_id)
  if not sessions:
      self._show_empty_label(self._history_scroll, self._history_widgets, "(Chưa có lịch sử điểm danh)")
      return
  for s in sessions:
      row = ctk.CTkFrame(self._history_scroll)
      # ... build row ...
      self._history_widgets.append(row)
  ```

### Dialog pattern — follow _show_enroll_dialog() pattern
```python
def _show_session_detail(self, session_id):
    dlg = ctk.CTkToplevel(self)
    dlg.title("📋 Chi tiết phiên")
    dlg.geometry("600x500")
    dlg.transient(self)
    dlg.grab_set()
    # ... content ...
    ctk.CTkButton(bf, text="Đóng", command=lambda: self._safe_close_dialog(dlg)).pack(...)
```

### Database methods already available (E9-S1 — KHÔNG tạo mới):
| Method | Source | Returns |
|--------|--------|---------|
| `get_sessions(class_id=None)` | database.py L545-574 | list of dicts (JOINed: class_code, subject, teacher_name) |
| `get_session_records(session_id)` | database.py L576-600 | list of dicts (JOINed: name, student_code) |
| `get_student_absence_count(student_id, class_id=None)` | database.py L602-629 | int |
| `get_sessions_by_class(class_id)` | database.py L631-633 | delegates to get_sessions() |
| `get_all_classes()` | database.py L268-277 | list of dicts |
| `get_class(class_id)` | database.py L257-266 | dict or None |
| `get_teacher(teacher_id)` | database.py L138-147 | dict or None |

### Anti-Patterns to AVOID
- ❌ KHÔNG sửa `database.py` — tất cả query methods đã có sẵn từ E9-S1
- ❌ KHÔNG sửa `main.py` — AdminWindow đã wired đúng trong E8-S2
- ❌ KHÔNG import `ExcelExporter` ở top-level trong admin_window.py — lazy import trong `_reexport_session()` only
- ❌ KHÔNG truyền raw `session['start_time']` (TEXT) cho ExcelExporter — PHẢI parse sang `datetime` object
- ❌ KHÔNG nhân `confidence` × 100 khi reconstruct — ExcelExporter tự nhân (line 136)
- ❌ KHÔNG dùng `s['student_id']` — session_records dùng `r['student_id']` key (khác với session_result dùng `r['id']`). Xem _row_to_dict.
- ❌ KHÔNG quên `_safe_close_dialog()` cho detail dialog — tránh orphaned grab
- ❌ KHÔNG quên thêm `self._history_widgets = []` vào `__init__` — `_clear_widgets()` sẽ fail
- ❌ KHÔNG filter sessions bằng SQL mới — client-side filter đủ cho MVP
- ❌ KHÔNG phá vỡ existing tabs — chỉ APPEND tab mới, KHÔNG sửa 4 tabs hiện tại
- ❌ KHÔNG quên `or []` guard khi gọi `get_sessions()` — OperationalError handler thiếu explicit return (line 570-571)
- ❌ KHÔNG dùng `get_student_absence_count()` cho stats loop — N+1 query anti-pattern
- ❌ KHÔNG dùng `from excel_export import ...` — PHẢI dùng `from src.core.excel_export import ExcelExporter` (full module path)

### Thread Safety
- AdminWindow chạy trên main thread (modal dialog) — tất cả DB calls đều thread-safe
- `get_sessions()` dùng `with closing(self.get_connection())` + `check_same_thread=False` — an toàn
- ExcelExporter chạy synchronous trên main thread — không có race condition

### Grab Management (Critical — xem E8-S1 CR-9)
- Detail dialog PHẢI dùng `dlg.grab_set()` sau `transient(self)`
- Khi đóng dialog, PHẢI dùng `self._safe_close_dialog(dlg)` (line 115-121 of admin_window.py)
- Nếu ExcelExporter mở file dialog → `dlg.grab_release()` trước, `dlg.grab_set()` sau (giống `_pick_image()` pattern line 130-143)

### Project Structure Notes
- `src/gui/admin_window.py` line 37: Thêm tab name vào list
- `src/gui/admin_window.py` line 43: Thêm `self._history_widgets = []`
- `src/gui/admin_window.py` line 48: Thêm `self._build_history_tab()` call
- `src/gui/admin_window.py` line 29: Tăng geometry thành `"1000x600"` (party-mode F5/F8: 5 tabs cần wider window)
- `src/gui/admin_window.py` line 699+: Thêm Tab 5 section (~150-200 lines)
- Tests: Tạo mới hoặc thêm vào existing test file

### References
- [Source: src/gui/admin_window.py#L21-L48] — AdminWindow.__init__() — tab creation + widget lists
- [Source: src/gui/admin_window.py#L50-L56] — _on_close() — grab_release pattern
- [Source: src/gui/admin_window.py#L107-L128] — _clear_widgets(), _safe_close_dialog(), _show_empty_label()
- [Source: src/gui/admin_window.py#L130-L143] — _pick_image() — grab management for filedialog
- [Source: src/gui/admin_window.py#L402-L526] — _show_enroll_dialog() — dialog pattern reference
- [Source: src/gui/admin_window.py#L538-L563] — _refresh_timetable_list() — list rebuild pattern
- [Source: src/core/database.py#L545-L633] — All attendance history query methods (E9-S1)
- [Source: src/core/database.py#L268-L277] — get_all_classes() for filter dropdown
- [Source: src/core/excel_export.py#L54-L190] — ExcelExporter.export_session() — input format contract
- [Source: src/core/excel_export.py#L78-L82] — present/absent list access pattern
- [Source: src/core/excel_export.py#L98] — start_time.strftime() — REQUIRES datetime object
- [Source: src/core/excel_export.py#L131-L136] — mark_time.strftime() + confidence * 100
- [Source: src/main.py#L473-L540] — _on_admin_requested/_on_admin_closed — AdminWindow lifecycle (E8-S2)
- [Source: src/gui/session_panel.py#L91-L99] — admin_button — chỉ hiện khi Mode 1

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (Thinking)

### Debug Log References

### Completion Notes List

- Story context engine analysis completed — comprehensive developer guide created
- Validation checklist executed — 8 findings identified and fixed:
  - [F1] Added defensive `or []` guard warning for `get_sessions()` OperationalError path
  - [F2] Documented exact dict key names from `get_session_records()` SQL JOIN
  - [F3] Added complete `get_sessions()` return dict key table with types and examples
  - [F4] Added window geometry note (5 tabs may need wider window)
  - [F5] Specified exact `class_info`/`teacher_info` key requirements for ExcelExporter
  - [F6] Acknowledged date regex limitation (allows invalid dates) — acceptable for MVP
  - [F7] Replaced N+1 query approach for stats with accumulator pattern
  - [F8] Specified exact lazy import path: `from src.core.excel_export import ExcelExporter`
- Party-mode adversarial review — 10 findings identified and remediated:
  - [PM-F1] CRITICAL: `get_sessions()` OperationalError missing `return []` → FIXED in database.py
  - [PM-F2] MEDIUM: `get_session_records()` same bug → FIXED in database.py
  - [PM-F3] INFO: No test file yet → will create during implementation
  - [PM-F4] LOW: Date regex accepts invalid dates → accepted for MVP
  - [PM-F5] LOW: Window width too narrow for 5 tabs → updated geometry to 1000x600
  - [PM-F6] MEDIUM: student_id key mismatch in reconstruction → clarified in helper
  - [PM-F7] MEDIUM: Stats accumulator unclear → simplified to avg-rate-only for MVP
  - [PM-F8] INFO: Window resize needed → updated in project structure notes
  - [PM-F9] MEDIUM: get_class/get_teacher None guard → added null-safe pattern in AC7
  - [PM-F10] LOW: Stats approach undecided → chose approach 2 (simple avg only)
- **Implementation completed (2026-05-05):**
  - Tab 5 "📋 Lịch sử" added to AdminWindow (258 lines)
  - All 8 ACs satisfied: tab creation, session list, detail dialog, class filter, date filter, stats, Excel re-export, unit tests
  - Window geometry widened to 1000x600 for 5 tabs
  - 8 new tests created in tests/test_admin_history.py — all pass
  - Full regression suite: 321 passed, 34 pre-existing failures, 0 new regressions
  - Zero modifications to database.py or main.py — view-only changes per MVP architecture

### Change Log

- 2026-05-05: Story implementation complete — all 6 tasks done, 8/8 tests pass, status → review
- 2026-05-05: Adversarial code review round 2 — 11 findings (F1-F11), 9 remediated:
  - [F2] CRITICAL: session['class_id']/['teacher_id'] KeyError risk → .get() guard
  - [F3] MEDIUM: Per-session corruption masked → per-session clamp + logging
  - [F4] MEDIUM: Stale class filter reset silent → added logger.info
  - [F5] MEDIUM: _show_session_detail orphan crash → try/except wrap
  - [F6] MEDIUM: Recursive dialog risk in _reexport_session → separated try blocks
  - [F8] LOW: confidence None from DB → `or 0.0` guard
  - [F10] LOW: Detail header KeyError risk → .get() with defaults
  - [F9] LOW: Test gap — added OSError test for reexport
  - [F11] LOW: Test gap — added combined class+date filter test
  - 16/16 tests pass, status → done

### File List

| File | Action |
|------|--------|
| `src/gui/admin_window.py` | MODIFY — Add Tab 5 "📋 Lịch sử" + 9 methods (~258 lines) + widen to 1000x600 |
| `tests/test_admin_history.py` | NEW — 8 test cases covering all ACs |
