# Story 2.1: database-sqlite

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a developer,
I want to implement the complete SQLite database layer including all CRUD methods in `src/core/database.py`,
so that the application can store and retrieve state regarding teachers, students, classes, timetables, and face encodings securely and across multiple threads.

## Acceptance Criteria

1. File `src/core/database.py` được khởi tạo mới với class `DatabaseManager`.
2. Trình kết nối database tự động tạo thư mục parent định trước bằng `os.makedirs(..., exist_ok=True)` để tránh `FileNotFoundError`.
3. Hàm connect bắt buộc có `check_same_thread=False` để an toàn cho luồng nhận diện ngầm (worker thread).
4. `PRAGMA foreign_keys = ON;` được thiết lập trên TẤT CẢ các instances của SQLite connection.
5. `try-except sqlite3.Error` được sử dụng trên toàn bộ phương thức CRUD để tránh ứng dụng bị crash khi gặp lỗi constraints.
6. Schema các bảng (teachers, classes, students, class_students, face_encodings, timetable) được dựng chính xác theo schema cứng được khai báo (xem phần Dev Guardrails).
7. Mảng NumPy 128d cho `face_encodings` được Serialize / Deserialize chuẩn sử dụng `.tobytes()` và `np.frombuffer(row['encoding'], dtype=np.float64)`.
8. Lấy đường dẫn database thông qua `from src.core.config import Config`. Không hardcode đường dẫn database tuyệt đối.
9. Các phương thức `delete_student` và `delete_teacher` phải thực hiện thủ công xóa dữ liệu `face_encodings` tương ứng trong cùng một giao dịch (transaction) do SQLite không hỗ trợ ON DELETE CASCADE cho polymorphic reference.
10. Tham số `timeout` phải được thiết lập trong connection để tránh tình trạng Database Locked do Worker Thread và UI Thread truy xuất cùng lúc. Cần log chi tiết lỗi `sqlite3.OperationalError`.

## Tasks / Subtasks

- [x] Tạo file `src/core/database.py` và setup framework của `DatabaseManager` (bao gồm hàm khởi tạo, `get_connection`).
- [x] Implement hàm `create_tables()` dựa trên Schema Definitions ở phần chú giải phía dưới.
- [x] Thực thi CRUD cho bảng `teachers`: `add_teacher`, `get_teacher`, `get_all_teachers`, `delete_teacher` (Bao gồm manual delete `face_encodings` và quản lý transaction `conn.commit()`).
- [x] Thực thi CRUD cho bảng `classes`: `add_class`, `get_class`, `get_all_classes`, `get_classes_by_teacher`, `delete_class`.
- [x] Thực thi CRUD cho bảng `students`: `add_student`, `get_student`, `get_student_by_code`, `get_all_students`, `delete_student` (Bao gồm manual delete `face_encodings` và quản lý transaction `conn.commit()`).
- [x] Thực thi CRUD cho bảng trung gian `class_students`: `add_student_to_class`, `remove_student_from_class`, `get_students_in_class`.
- [x] Thực thi CRUD cho bảng `face_encodings`: `add_encoding`, `get_encodings_by_person`, `get_encodings_by_type`, `delete_encoding_by_person`. Implement serialization an toàn cho BLOB.
- [x] Thực thi CRUD cho bảng `timetable`: `add_timetable`, `get_timetable_by_class`, `delete_timetable`.

## Dev Guardrails (CRITICAL CONSTRAINTS)

**1. Database Integration Setup:**
Sử dụng `src/core/config.py` để tìm đường dẫn:
```python
import os
from src.core.config import Config

# Khi khởi tạo DB Manager:
config = Config()
db_path = config.get("database.path", "data/attendance.db") 
os.makedirs(os.path.dirname(db_path), exist_ok=True)
```

**2. SQLite System Configuration:**
Mọi connection phải có timeout 10s cho cơ chế concurrency block:
```python
conn = sqlite3.connect(db_path, check_same_thread=False, timeout=10.0)
conn.row_factory = sqlite3.Row
conn.execute("PRAGMA foreign_keys = ON;")
```
*Lưu ý: Bạn BẮT BUỘC phải tạo Parent Directory của `db_path` trước khi connect lần đầu tiên.*

**3. Numpy BLOB Conversion:**
- Insert: Truyền `encoding_array.tobytes()` vào SQLite parameter.
- Select: Parse cột trả về bằng `np.frombuffer(row["encoding"], dtype=np.float64)`.

**4. Data Output Standardization:**
Mọi phương thức "Get" phải mapping `sqlite3.Row` thành kiểu `dict` tiêu chuẩn trước khi break context, để tầng Application dễ dàng thao tác, không trả object connection thô. Dev nên tạo một helper method để mapper và tự động dịch ngược cột `encoding` BLOB thành mảng Numpy trước khi trả về. Các Exception phải được catch và xử lý nội bộ, đặc biệt `sqlite3.OperationalError` do db lock phải được log cụ thể. Return theo quy ước (vd `False`, `None` hoặc raise Custom Error) nhưng KHÔNG được làm crash GUI app vì các lỗi Database.

**5. Polymorphic Caching & Deletion:**
Bảng `face_encodings` sử dụng cấu trúc đa chức năng `(person_type, person_id)`, vì vậy `DEFAULT ON DELETE CASCADE` ở Database Engine KHÔNG DÙNG ĐƯỢC. Dev bắt buộc phải bổ sung câu lệnh thủ công `DELETE FROM face_encodings WHERE person_type=? AND person_id=?` vào bên trong `delete_student` và `delete_teacher`. Phải quản lý transaction (vd: chạy qua context manager `with conn:` hoặc `conn.commit()`) để đảm bảo hệ thống rollback toàn bộ nếu quá trình xóa encoding bị lỗi.

## SQL Schema Definitions

Bạn BẮT BUỘC phải dùng thiết kế Schema này trong query `CREATE TABLE IF NOT EXISTS`:

```sql
CREATE TABLE IF NOT EXISTS teachers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    teacher_code TEXT UNIQUE NOT NULL,
    photo_path TEXT,
    added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS classes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    class_code TEXT UNIQUE NOT NULL,
    subject TEXT NOT NULL,
    teacher_id INTEGER,
    FOREIGN KEY (teacher_id) REFERENCES teachers (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    student_code TEXT UNIQUE NOT NULL,
    photo_path TEXT,
    added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS class_students (
    class_id INTEGER,
    student_id INTEGER,
    PRIMARY KEY (class_id, student_id),
    FOREIGN KEY (class_id) REFERENCES classes (id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS face_encodings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_type TEXT NOT NULL, -- 'student' or 'teacher'
    person_id INTEGER NOT NULL,
    encoding BLOB NOT NULL
);

CREATE TABLE IF NOT EXISTS timetable (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    class_id INTEGER NOT NULL,
    day_of_week INTEGER NOT NULL, -- 0-6 cho Thứ 2 - Chủ Nhật
    start_time TEXT NOT NULL, -- Format 'HH:MM'
    end_time TEXT NOT NULL, -- Format 'HH:MM'
    FOREIGN KEY (class_id) REFERENCES classes (id) ON DELETE CASCADE
);
```

### References

- [Source: sprint-status.yaml#L108-L125] - System Database Schema
- [Source: sprint-status.yaml#L191-L208] - Epic 2 Database Core Tasks
- [Source: config.yaml] - Configuration Source Reference

## Dev Agent Record

### Agent Model Used

Gemini 3.1 Pro (High)

### Debug Log References

- [x] All 7 Unit tests passed locally for CRUD logic (`tests/test_database.py`)
- [x] Zero resource warnings for SQLite connections via `contextlib.closing`

### Completion Notes List

- ✅ Tạo cấu trúc `DatabaseManager` với đầy đủ kết nối an toàn thread `check_same_thread=False` và set `timeout=10.0`.
- ✅ Xây dựng hệ thống unit tests TDD cho tất cả các bảng.
- ✅ Serialize/Deserialize NumPy array an toàn.
- ✅ Hỗ trợ CASCADE DELETE thủ công cho bảng polymophic `face_encodings`.
- ✅ Trả về dictionary (Python `dict`) tiêu chuẩn thay vì `sqlite3.Row` trên kết quả Get.
- ✅ Quản lý tài nguyên an toàn với block `try-finally/with` (kết hợp `contextlib.closing`).

### Review Follow-ups (AI)
- ✅ Fix `__init__` database path directory check to avoid `FileNotFoundError`.
- ✅ Fix `add_encoding` casting logic (use `np.array.tobytes()`).
- ✅ Fix CRUD delete methods missing `.rowcount` checks.
- ✅ Fix exception handling to explicitly log `sqlite3.OperationalError` as well as generic `sqlite3.Error`.

### File List

- `src/core/database.py` (Mới tạo, Full Code Implementation)
- `tests/test_database.py` (Mới tạo, Unit tests hoàn chỉnh)
