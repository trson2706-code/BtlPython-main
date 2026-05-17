# Story 9.1: Lưu lịch sử điểm danh vào Database

Status: done

## Story

Là giảng viên / quản trị viên hệ thống,
Tôi muốn lịch sử điểm danh được tự động lưu vào database sau mỗi phiên,
Để tôi có thể tra cứu lại kết quả điểm danh trước đây, thống kê sinh viên vắng mặt, và không mất dữ liệu khi chưa kịp xuất Excel.

## Acceptance Criteria

### AC1: Schema — Bảng `attendance_sessions`
- Thêm bảng `attendance_sessions` vào `database.py → create_tables()`:
  ```sql
  CREATE TABLE IF NOT EXISTS attendance_sessions (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      class_id INTEGER NOT NULL,
      teacher_id INTEGER NOT NULL,
      session_date TEXT NOT NULL,        -- Format 'YYYY-MM-DD'
      start_time TEXT NOT NULL,          -- Format 'YYYY-MM-DD HH:MM:SS'
      end_time TEXT NOT NULL,            -- Format 'YYYY-MM-DD HH:MM:SS'
      total_students INTEGER NOT NULL DEFAULT 0,
      present_count INTEGER NOT NULL DEFAULT 0,
      FOREIGN KEY (class_id) REFERENCES classes (id) ON DELETE CASCADE,
      FOREIGN KEY (teacher_id) REFERENCES teachers (id) ON DELETE CASCADE
  );
  ```
- ⚠️ `session_date` dùng TEXT (ISO-8601) — SQLite không có kiểu DATE native
- ⚠️ FK ON DELETE CASCADE — khi xóa class/teacher, session history cũng bị xóa (chấp nhận cho MVP)

### AC2: Schema — Bảng `attendance_records`
- Thêm bảng `attendance_records` vào `database.py → create_tables()`:
  ```sql
  CREATE TABLE IF NOT EXISTS attendance_records (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      session_id INTEGER NOT NULL,
      student_id INTEGER NOT NULL,
      is_present INTEGER NOT NULL DEFAULT 0,  -- 0=Vắng, 1=Có mặt
      confidence REAL DEFAULT 0.0,             -- 0.0-1.0
      mark_time TEXT,                          -- Format 'YYYY-MM-DD HH:MM:SS' hoặc NULL
      image_path TEXT,
      FOREIGN KEY (session_id) REFERENCES attendance_sessions (id) ON DELETE CASCADE,
      FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE
  );
  ```
- ⚠️ `is_present` dùng INTEGER (0/1) — SQLite không có kiểu BOOLEAN native
- ⚠️ `confidence` lưu dạng REAL 0.0-1.0 (giống `AttendanceSession.mark_present()`)
- ⚠️ `mark_time` nullable — NULL cho sinh viên vắng mặt

### AC3: CRUD — `save_session()`
- Thêm method `save_session(self, session_result: dict, teacher_id: int) -> int` vào `DatabaseManager`:
  - Tham số `session_result`: dict trả về từ `AttendanceSession.end_session()` — keys: `class_id`, `start_time`, `end_time`, `present`, `absent`
  - Tham số `teacher_id`: int — ID của giảng viên chủ trì phiên
  - **Trong 1 transaction duy nhất (atomicity):**
    1. INSERT vào `attendance_sessions` (extract metadata từ session_result)
    2. INSERT BATCH vào `attendance_records` (dùng `executemany()`) cho **tất cả** sinh viên (present + absent)
  - Return `session_id` (lastrowid) nếu thành công, `None` nếu lỗi
  - Error handling: `try/except sqlite3.Error` — log + return None (giống pattern CRUD hiện tại)
  - ⚠️ `datetime → TEXT`: dùng `strftime('%Y-%m-%d %H:%M:%S')` cho start_time/end_time, `strftime('%Y-%m-%d')` cho session_date
  - ⚠️ `mark_time` trong student record là `datetime` object hoặc `None` — cần convert sang TEXT

### AC4: CRUD — `get_sessions()`
- Thêm method `get_sessions(self, class_id: int = None) -> list` vào `DatabaseManager`:
  - Nếu `class_id` is None → trả về TẤT CẢ sessions (SELECT * FROM attendance_sessions ORDER BY session_date DESC)
  - Nếu `class_id` có giá trị → trả về sessions của lớp đó (WHERE class_id = ?)
  - Return list of dicts (dùng `_rows_to_list()`)
  - JOIN với classes và teachers để lấy class_code, subject, teacher name:
    ```sql
    SELECT s.*, c.class_code, c.subject, t.name as teacher_name
    FROM attendance_sessions s
    JOIN classes c ON s.class_id = c.id
    JOIN teachers t ON s.teacher_id = t.id
    ORDER BY s.session_date DESC, s.start_time DESC
    ```

### AC5: CRUD — `get_session_records()`
- Thêm method `get_session_records(self, session_id: int) -> list` vào `DatabaseManager`:
  - SELECT tất cả records cho session_id, JOIN với students để lấy name, student_code:
    ```sql
    SELECT r.*, st.name, st.student_code
    FROM attendance_records r
    JOIN students st ON r.student_id = st.id
    WHERE r.session_id = ?
    ORDER BY st.student_code ASC
    ```
  - Return list of dicts

### AC6: Query thống kê — `get_student_absence_count()`
- Thêm method `get_student_absence_count(self, student_id: int, class_id: int = None) -> int`:
  - Đếm số lần vắng mặt (is_present = 0) của sinh viên
  - Nếu `class_id` có giá trị → chỉ đếm trong lớp đó
  - SQL:
    ```sql
    SELECT COUNT(*) FROM attendance_records r
    JOIN attendance_sessions s ON r.session_id = s.id
    WHERE r.student_id = ? AND r.is_present = 0
    [AND s.class_id = ?]
    ```
  - Return int (0 nếu lỗi)

### AC7: Query thống kê — `get_sessions_by_class()`
- Thêm method `get_sessions_by_class(self, class_id: int) -> list`:
  - Shortcut cho `get_sessions(class_id=class_id)`
  - Có thể implement inline hoặc delegate — nhưng phải tồn tại như public method riêng

### AC8: Hook vào AttendanceSession.end_session()
- **KHÔNG** sửa `AttendanceSession.end_session()` trực tiếp
- Thay vào đó, hook tại **Presenter** (`src/main.py → _on_session_end_requested()`):
  - Sau khi `self.session.end_session()` trả về result:
    ```python
    # Lưu lịch sử vào DB — best-effort (không block Excel export)
    try:
        self.db.save_session(result, self._current_teacher_id)
    except Exception as e:
        # ⚠️ PHẢI dùng broad Exception — save_session có thể raise
        # sqlite3.Error, TypeError (datetime conversion), KeyError, etc.
        logger.error(f"Lỗi lưu lịch sử điểm danh: {e}")
    ```
  - Hook TRƯỚC `self.exporter.export_session()` — đảm bảo DB ghi trước khi xuất Excel
  - ⚠️ PHẢI dùng `self._current_teacher_id` (set trong `_on_teacher_detected()`) — KHÔNG truyền teacher_id qua event system
  - ⚠️ Best-effort: nếu save_session() fail, Excel export vẫn tiếp tục

### AC9: Unit tests — ≥8 test cases
- Test 1: Schema — 2 bảng mới tồn tại (attendance_sessions, attendance_records)
- Test 2: `save_session()` — lưu thành công, return session_id
- Test 3: `save_session()` — kiểm tra data lưu đúng (session_date, total_students, present_count)
- Test 4: `save_session()` — kiểm tra attendance_records đúng (present + absent đều lưu)
- Test 5: `get_sessions()` — trả về tất cả sessions (no filter)
- Test 6: `get_sessions(class_id)` — filter theo lớp
- Test 7: `get_session_records()` — trả về records JOIN student info
- Test 8: `get_student_absence_count()` — đếm đúng số lần vắng
- Test 9: CASCADE delete — xóa class → sessions bị xóa
- Test 10: `save_session()` với session rỗng (0 students) — vẫn lưu session header
- Baseline: tất cả test hiện có phải pass

## Tasks / Subtasks

- [ ] Task 1 (AC: #1, #2): Thêm schema 2 bảng mới
  - [ ] Thêm CREATE TABLE attendance_sessions vào `create_tables()` trong `database.py`
  - [ ] Thêm CREATE TABLE attendance_records vào `create_tables()` trong `database.py`
  - [ ] Đặt SAU bảng `timetable` (phụ thuộc classes, teachers, students)

- [ ] Task 2 (AC: #3): Implement `save_session()`
  - [ ] Thêm method `save_session(self, session_result, teacher_id)` vào `DatabaseManager`
  - [ ] Single transaction: INSERT session header + executemany records
  - [ ] datetime → TEXT conversion (strftime)
  - [ ] Null-safe: handle mark_time None cho absent students

- [ ] Task 3 (AC: #4, #5, #7): Implement query methods
  - [ ] Thêm `get_sessions(self, class_id=None)` — JOIN classes + teachers
  - [ ] Thêm `get_session_records(self, session_id)` — JOIN students
  - [ ] Thêm `get_sessions_by_class(self, class_id)` — delegate to get_sessions

- [ ] Task 4 (AC: #6): Implement `get_student_absence_count()`
  - [ ] COUNT WHERE is_present=0, optional class_id filter
  - [ ] Return 0 on error

- [ ] Task 5 (AC: #8): Hook vào Presenter
  - [ ] Thêm `self.db.save_session(result, self._current_teacher_id)` vào `_on_session_end_requested()` trong `src/main.py`
  - [ ] Đặt SAU `end_session()` và TRƯỚC `export_session()`
  - [ ] Wrap trong try/except — best-effort, không block flow

- [ ] Task 6 (AC: #9): Unit tests
  - [ ] Thêm tests vào `tests/test_database.py` (schema + CRUD — baseline: 6 tests)
  - [ ] Thêm test vào `tests/test_main.py` (Presenter hook — baseline: 38 tests)
  - [ ] Chạy full test suite, verify 0 regressions trên TOÀN BỘ test files

## Dev Notes

### Architecture Pattern (MVP)
- **Model**: `DatabaseManager` (`src/core/database.py`) — thêm schema + CRUD methods
- **View**: KHÔNG thay đổi trong story này (GUI sẽ ở E9-S2)
- **Presenter**: `src/main.py` — hook save_session() vào _on_session_end_requested()
- **KHÔNG** sửa `AttendanceSession` — session vẫn là in-memory, stateless (clean RAM after end). Persistence là trách nhiệm của Presenter qua DatabaseManager

### ⚠️ CRITICAL: Missing Import
- `database.py` hiện tại **KHÔNG** import `datetime` — cần thêm `from datetime import datetime` vào đầu file
- Kiểm tra: line 1-6 chỉ có `import os, sqlite3, logging, numpy, contextlib.closing, Config`
- PHẢI thêm `from datetime import datetime` để dùng `isinstance(mark_time, datetime)` trong `save_session()`

### Implementation Details

**save_session() transaction pattern:**
```python
def save_session(self, session_result, teacher_id):
    try:
        with closing(self.get_connection()) as conn:
            with conn:  # Auto-commit/rollback
                # 1. INSERT session header
                cursor = conn.execute(
                    "INSERT INTO attendance_sessions (...) VALUES (...)",
                    (...)
                )
                session_id = cursor.lastrowid

                # 2. BATCH INSERT records (present + absent)
                all_students = list(session_result.get('present') or []) + \
                               list(session_result.get('absent') or [])
                records = []
                for s in all_students:
                    mark_time_str = s.get('mark_time')
                    if mark_time_str and isinstance(mark_time_str, datetime):
                        mark_time_str = mark_time_str.strftime('%Y-%m-%d %H:%M:%S')
                    records.append((
                        session_id, s['id'],
                        1 if s.get('is_present') else 0,
                        s.get('confidence', 0.0),
                        mark_time_str,
                        s.get('image_path')
                    ))
                conn.executemany(
                    "INSERT INTO attendance_records (...) VALUES (?, ?, ?, ?, ?, ?)",
                    records
                )
                return session_id
    except sqlite3.OperationalError as e:
        logger.error(f"Database Locked or Operational Error during 'saving session': {e}")
    except sqlite3.Error as e:
        logger.error(f"Error saving session: {e}")
        return None
```

**session_result dict structure** (từ `AttendanceSession.end_session()` — line 172-178):
```python
result = {
    'class_id': int,          # ID lớp
    'start_time': datetime,   # Thời điểm bắt đầu (datetime object)
    'end_time': datetime,     # Thời điểm kết thúc (datetime object)
    'present': [              # Danh sách SV có mặt
        {
            'id': int,                # ⚠️ KEY LÀ 'id' — KHÔNG PHẢI 'student_id'!
            'student_code': str,
            'name': str,
            'is_present': True,
            'confidence': float,      # 0.0-1.0
            'image_path': str|None,
            'mark_time': datetime|None,  # datetime object hoặc None
        }
    ],
    'absent': [               # Danh sách SV vắng
        {
            'id': int,                # ⚠️ KEY LÀ 'id' — KHÔNG PHẢI 'student_id'!
            'student_code': str,
            'name': str,
            'is_present': False,
            'confidence': 0.0,
            'image_path': None,
            'mark_time': None,
        }
    ],
}
```

> **⚠️ CRITICAL KEY NAMING TRAP:** `end_session()` tại line 166 dùng `{'id': s_id, **record}` — key là `'id'`. Dev agent PHẢI dùng `s['id']` để lấy student_id, KHÔNG dùng `s['student_id']` (key đó KHÔNG tồn tại và sẽ gây KeyError).

**Presenter hook location** — `_on_session_end_requested()` (lines 249-297 of main.py):
```python
def _on_session_end_requested(self, data):
    self.worker.pause_scanning()
    try:
        result = self.session.end_session()
    except ValueError as e:
        logger.warning(f"end_session() duplicate call: {e}")
        return

    self._last_session_result = result
    self._current_mode = None
    self._pending_class_id = None

    # ★ NEW: Lưu lịch sử vào DB (best-effort)
    try:
        self.db.save_session(result, self._current_teacher_id)
    except Exception as e:
        logger.error(f"Lỗi lưu lịch sử điểm danh: {e}")

    # Existing: export Excel
    class_info = self.db.get_class(self._current_class_id)
    teacher_info = self.db.get_teacher(self._current_teacher_id)
    ...
```

### Thread Safety
- `save_session()` chạy trên main thread (event handler) — an toàn cho SQLite
- `get_connection()` dùng `check_same_thread=False` + `timeout=10.0` — tương thích pattern hiện tại
- `executemany()` trong single transaction — atomic (all-or-nothing)

### Data Integrity
- FK ON DELETE CASCADE cho class_id, teacher_id, student_id — nếu xóa GV/SV/Lớp trong Admin, lịch sử liên quan cũng bị xóa
- `is_present` dùng INTEGER 0/1 thay vì TEXT 'true'/'false' — efficient + standard SQLite pattern
- `confidence` lưu 0.0-1.0 (giống `AttendanceRecord` trong `attendance_session.py`) — KHÔNG phải 0-100

### Anti-Patterns to AVOID
- ❌ KHÔNG sửa `AttendanceSession.end_session()` — session layer KHÔNG biết về persistence
- ❌ KHÔNG import `DatabaseManager` vào `attendance_session.py` — vi phạm MVP
- ❌ KHÔNG dùng `datetime.now()` cho session timestamps — PHẢI dùng `result['start_time']` và `result['end_time']` từ session_result
- ❌ KHÔNG lưu `confidence` dạng 0-100 — session lưu dạng 0.0-1.0, giữ consistent
- ❌ KHÔNG tạo file mới — chỉ MODIFY `database.py` và `main.py`
- ❌ KHÔNG quên lưu absent students — `save_session()` phải ghi CẢ present VÀ absent
- ❌ **KHÔNG dùng `s['student_id']`** — session_result dùng `'id'` key (xem end_session() line 166). Dùng `s['id']` để lấy student_id
- ❌ KHÔNG dùng `LEFT JOIN` trong get_sessions — nếu class/teacher bị xóa, session sẽ bị CASCADE delete → INNER JOIN luôn đúng
- ❌ KHÔNG quên thêm `from datetime import datetime` vào database.py — file hiện tại KHÔNG import datetime
- ❌ KHÔNG quên explicit `return None` trong `save_session()` OperationalError handler — tránh fall-through ambiguity
- ❌ KHÔNG giả sử `_row_to_dict()` tự handle — method này chỉ convert `encoding` BLOB key. attendance_records/sessions KHÔNG có `encoding` key nên an toàn, nhưng TUYỆT ĐỐI KHÔNG đặt tên column là `encoding` trong bảng mới

### Test Mock Pattern
```python
# test_database.py — thêm tests cho save_session(), get_sessions(), etc.
# Dùng test_attendance.db giống pattern setUp hiện tại (line 11-14)
# Tạo test data: teacher → class → students → class_students → session_result dict

# test_main.py — thêm test cho Presenter hook
# Mock self.db.save_session = MagicMock() 
# Verify save_session() được gọi trong _on_session_end_requested()
# Verify save_session() failure không block Excel export
```

### Backward Compatibility
- Schema migration: `CREATE TABLE IF NOT EXISTS` — DB cũ sẽ tự thêm 2 bảng mới khi khởi chạy
- 6 bảng cũ KHÔNG bị thay đổi — zero regression risk
- `_on_session_end_requested()` thêm try/except block — nếu save_session fail, flow cũ vẫn chạy đúng
- Tất cả test hiện có phải pass 100%
- Baseline counts: test_database.py (6 tests), test_main.py (38 tests), test_attendance_session.py (12 tests)

### Project Structure Notes
- `src/core/database.py` line 26-73: Thêm 2 CREATE TABLE vào schema string (sau timetable)
- `src/core/database.py` line 436+: Thêm 5 methods mới sau timetable CRUD section
- `src/main.py` line 262-265: Thêm save_session() hook (sau end_session(), trước export)
- `tests/test_database.py`: Thêm ~10 test methods mới
- `tests/test_main.py`: Thêm 1-2 test methods mới

### References
- [Source: src/core/database.py#L26-L73] — create_tables() schema string, 6 bảng hiện tại
- [Source: src/core/database.py#L84-L93] — _row_to_dict(), _rows_to_list() helper methods
- [Source: src/core/database.py#L96-L448] — CRUD pattern: try/except + closing(get_connection()) + with conn
- [Source: src/core/attendance_session.py#L156-L186] — end_session() return dict structure
- [Source: src/core/attendance_session.py#L11-L17] — AttendanceRecord TypedDict (keys: student_code, name, is_present, confidence, image_path, mark_time)
- [Source: src/main.py#L249-L297] — _on_session_end_requested() flow: pause → end → save result → export → GUI update → reset timer
- [Source: src/main.py#L56-L63] — State tracking: _current_teacher_id, _current_class_id
- [Source: src/core/excel_export.py#L77-L82] — ExcelExporter access pattern cho session_result keys
- [Source: tests/test_database.py#L8-L19] — TestDatabaseManager setUp/tearDown pattern
- [Source: config.yaml#L20] — db_path: data/attendance.db

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (Thinking)

### Debug Log References

### Completion Notes List

- Story context engine analysis completed — comprehensive developer guide created
- Validation checklist executed — 8 findings identified and fixed:
  - [F1] Emphasized `from datetime import datetime` import requirement (database.py missing it)
  - [F2] Noted `_row_to_dict()` encoding conversion safety — no column naming collisions
  - [F3] Critical emphasis on `'id'` key vs `'student_id'` trap in session_result dict
  - [F4] Explicit `return None` in OperationalError handler for save_session()
  - [F5] Broad `Exception` catch rationale documented (datetime conversion, KeyError risks)
  - [F6] Accurate baseline test counts: test_database.py=6, test_main.py=38, test_attendance_session.py=12
  - [F7] INNER JOIN defense documented (CASCADE delete guarantees referential integrity)
  - [F8] Anti-pattern: never name column 'encoding' in new tables (collides with _row_to_dict)

### File List

| File | Action |
|------|--------|
| `src/core/database.py` | MODIFY — Add 2 new tables to schema + 5 new CRUD methods |
| `src/main.py` | MODIFY — Add save_session() hook in _on_session_end_requested() |
| `tests/test_database.py` | MODIFY — Add ~10 new test cases for history schema + CRUD |
| `tests/test_main.py` | MODIFY — Add 1-2 test cases for Presenter save_session hook |
