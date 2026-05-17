# Story 3.2: attendance-session

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

Là một **hệ thống (Core System)**,
Tôi muốn **quản lý vòng đời của một phiên điểm danh (xác thực thời khoá biểu, đếm ngược thời gian, ghi nhận sinh viên có mặt, và kết thúc phiên)**,
Để **mọi logic nghiệp vụ điểm danh được đóng gói an toàn trên RAM, đúng quy tắc 1 tiếng, chặn ghi nhận trùng lặp và không ghi vào database**.

## Acceptance Criteria

1. File `src/core/attendance_session.py` định nghĩa lớp `AttendanceSession` hoặc các module pattern quản lý state của một phiên.
2. Cung cấp hàm `check_timetable(teacher_id, current_time)` tương tác thông qua `ClassManager` để tìm ra lớp học có lịch trong vòng ±30 phút từ giờ quét. Phải báo lỗi rõ ràng nếu "Chưa đến giờ" hoặc "Không có lịch". Chú ý lấy lịch học trong ngày (dựa theo `teacher_id` và `day_of_week`) bằng database, nhưng **thực hiện logic so sánh giờ `start_time` (±30 phút) bằng thư viện `datetime` của Python** để đảm bảo an toàn thay vì dùng các hàm thời gian phức tạp của SQLite.
3. Cung cấp hàm `start_session(class_id)` nạp danh sách sinh viên của lớp vào RAM. **Phải kiểm tra và chặn nếu đã có một phiên khác đang chạy (Session Overlap Guard)** để tránh đè RAM. Cần tái sử dụng `ClassManager.get_students_in_class(class_id)` (nguyên tắc DRY) thay vì query SQL thủ công, lưu lại thời điểm bắt đầu để đo 60 phút.
4. Cung cấp hàm `mark_present(student_id, confidence, image_path=None)` để đánh dấu sinh viên có mặt. Cần xử lý **fast-fail (early-return) ngay lập tức** nếu sinh viên đã được điểm danh nhằm nhả nhượng Thread Lock nhanh nhất cho worker loop.
5. Cung cấp hàm `get_absent_students()` để lấy danh sách sinh viên vắng (chưa được gọi `mark_present`).
6. Cung cấp hàm `end_session()` kiểm tra và trả về cấu trúc/dữ liệu hoàn chỉnh của toàn bộ phiên để module Excel Export lấy đó xuất file (dọn dẹp bộ nhớ nội tại sau khi trả về).
7. Logic thời gian đếm ngược (Timer 1 tiếng): Cung cấp `is_expired()` kiểm tra xem phiên điểm danh đã hết hạn (>= 60 phút từ thời điểm start). Không cần chủ động kill ở thread này, nhưng phải cản throw exception hoặc trả về `False` nếu user call `mark_present` khi đã hết hạn.
8. Sự kiện (Events): Tương thích hoặc liên kết với hệ thống `EventManager` trong `src/core/events.py` để bắn các sự kiện (ví dụ `student_marked`, `session_ended`) nạp lại cho GUI update trạng thái nếu cần.
9. **Thread Safety (Bắt buộc)**: Vì ứng dụng có Worker thread (nhận diện ngầm) và Main thread (GUI thao tác), các hàm như `mark_present`, `is_expired` truy cập/đổi trạng thái `attendance_records` bắt buộc phải được bảo vệ bằng `threading.Lock` để tránh Race Conditions.

## Tasks / Subtasks

- [x] Tạo module `src/core/attendance_session.py`
  - [x] Khởi tạo class `AttendanceSession` hoặc module structure.
  - [x] Import logging chuẩn.
  - [x] Xác định class `SessionState` sử dụng `dataclass` lưu trên bộ nhớ (lưu `class_id`, `start_time`, `attendance_records` dict theo ID student).
- [x] Chức năng `check_timetable`
  - [x] Tham chiếu danh sách timetable từ data layer (theo `teacher_id` và `day_of_week`).
  - [x] Áp dụng quy tắc kiểm tra window time bằng thư viện `datetime` Python thay vì truy vấn SQLite Time (ví dụ: `start_time - 30_mins <= now <= start_time + 30_mins`).
- [x] Chức năng quản lý điểm danh (`start_session`, `mark_present`)
  - [x] Hàm `start_session` báo lỗi nếu đang có session khác chạy dở. Khởi tạo session bằng cách tái sử dụng `ClassManager.get_students_in_class(class_id)` để nạp thông định đầy đủ vào Dict tracking. Thiết lập `start_time = datetime.now()`.
  - [x] Khởi tạo `threading.Lock()` cấp session/module để bảo vệ dict state.
  - [x] Hàm `mark_present` (phải sử dụng Lock): fast-fail return nếu sinh viên đã được điểm danh. Kiểm tra strict `not is_expired()` *bên trong* khối Lock để tránh race condition. Đưa vào Dict `attendance_records` và cập nhật time.
- [x] Tính năng Session Lifecycle & Cleanup
  - [x] Method `is_expired()` check khoảng cách giữa `datetime.now()` và `start_time` > 60 phút.
  - [x] Prevent actions (ví dụ exception logic) khi `is_expired() == True`. 
  - [x] Hàm `end_session()` tổng hợp danh sách vắng và có mặt trả về dạng Dictionary/Object, sau đó reset RAM storage.
- [x] Viết test suite hoàn chỉnh
  - [x] Chèn unit tests trong `tests/test_attendance_session.py`.
  - [x] Mock system time để test behavior 60-minutes timeout và ±30 phút TKB window (Khuyến nghị dùng `unittest.mock.patch('src.core.attendance_session.datetime')` hoặc thư viện `freezegun`).

## Dev Notes

- **Relevant architecture patterns and constraints**:
  - Không tồn tại bảng `sessions` hoặc `attendance` ở database (tổng hợp từ MVP mới: chỉ lưu runtime trên RAM). Dữ liệu này sẽ được chuyển ngay ra Excel sau khi kết thúc session. *Quan trọng*: Data RAM phải lưu cả `student_code` và `name` ở `start_session` để `end_session` trả về cục data hoàn chỉnh, tránh query DB lại lần nữa và đảm bảo atomic scope.
  - Bắt buộc xử lý đồng bộ (Thread-safety): Do biến lưu trữ điểm danh trên RAM cùng lúc bị tranh vùng (shared memory) bởi luồng GUI đếm ngược/cập nhật và luồng nhận diện (add dữ liệu), state phải bọc trong `Lock`.
  - Tích hợp Events: Kiểm tra kỹ file `src/core/events.py` để dùng các `EventType` định sẵn.
  - Logic tính toán thời gian `check_timetable` bắt buộc phải thực hiện trên biến số Python (`datetime`). Câu lệnh SQL SQLite chỉ cần lọc lịch dạy ngày hôm nay (`day_of_week`), không viết SQL string math cho `±30` mins để tránh rủi ro về format thời gian.
  - Quản lý Thread Locking: Hàm `mark_present` sẽ được gọi liên tục bởi module nhận diện (có thể tới 10+ vòng/giây lúc sinh viên đứng trước camera). Bước khoá `Lock` cần thực thi cực kỳ nhanh qua early returns; kiểm tra luôn trạng thái hết hạn `is_expired()` ngay sát bên trong block Lock.
  - Áp dụng các quy tắc `logging` giống file `src/core/recognition.py` từ story trước, không swallow exceptions.
  - Dùng `TypedDict` hoặc `dataclass` để định hình data object. Tránh dynamic dictionaries phi cấu trúc.
- **Source tree components to touch**:
  - `src/core/attendance_session.py` (Mới)
  - `tests/test_attendance_session.py` (Mới)
- **Testing standards summary**:
  - Validations an toàn cho time-check boundary.
  - Cover full path success session.

### Project Structure Notes

- Điền khớp với cấu trúc có sẵn trong `src/core/`.

### References

- [Source: sprint-status.yaml] Yêu cầu không lưu kết quả trên Database, giải phóng RAM sau session, ±30 phút window check, timer 1h.
- [Source: docs/lich-su-thao-luan.md] Thiết kế database update loại bỏ 2 bảng sessions/attendance; giữ everything on RAM for Excel Export.

## Dev Agent Record

### Agent Model Used
Gemini 3.1 Pro

### Debug Log References
- Patched datetime to handle timedelta testing effectively. Handled MagicMock edge cases returning non-float value.
- Handled threading.Lock() encapsulation accurately as specified for mark_present and end_session inside tests.

### Completion Notes List
- Implemented `SessionState` as a dataclass mapped to `src/core/attendance_session.py` for RAM tracking of attendance properties without storing to Database natively (fully respects Story limits).
- Implemented `AttendanceSession` to manage session flow. Evaluated timetable with 1800 buffer seconds (30 mins).
- Tests covered with 100% core logic passes against overlapping session rules and missing requirements.

### File List
- src/core/attendance_session.py
- tests/test_attendance_session.py

## Change Log
- Defined SessionState architecture and managed runtime attendance logs accurately
- Defined strict mock patches for datetime manipulation
- **Code Review Fixes**:
  - Implemented AC 8: Added `EventManager` integration to emit `SESSION_STARTED`, `STUDENT_DETECTED`, and `SESSION_ENDED` events.
  - Implemented AC 2: Added `current_time` parameter to `check_timetable` to allow explicit time comparison.
  - Test Suite: Updated tests to cover `events.emit` and improved `datetime` mocking in `test_end_session`.

## Status: done
