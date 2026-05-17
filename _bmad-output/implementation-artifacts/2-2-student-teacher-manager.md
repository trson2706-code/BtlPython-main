# Story 2.2: Module quản lý SV + GV + Lớp

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a developer,
I want to implement the `student_manager.py` and `class_manager.py` modules in `src/core/`,
so that I can perform business logic CRUD operations for students, teachers, classes, and class enrollments, including strict face validation and physical image storage.

## Acceptance Criteria

1. **StudentManager (`src/core/student_manager.py`)**: Có chức năng add, remove, get_student, get_all_students.
2. **ClassManager (`src/core/class_manager.py`)**: Có chức năng quản lý teachers (add/remove/list/get), classes (add/remove/list/get_by_teacher), và gán SV vào lớp (add/remove_student_from_class, get_students_in_class).
3. **Face Validation & Image Storage (CRITICAL)**:
   - Khi add thông qua `image_path`:
   - Phải bọc try-except khi xử lý ảnh bằng `face_recognition.load_image_file()` để bắt các lỗi file ảnh hỏng/không hợp lệ và raise `ValueError("Định dạng file ảnh không hợp lệ hoặc bị hỏng.")`.
   - Validate nghiêm ngặt: Nếu không nhận diện được mặt (`len == 0`), raise `ValueError("Không nhận diện được khuôn mặt trong ảnh.")`.
   - Validate nghiêm ngặt: Nếu lớn hơn 1 mặt (`len > 1`), raise `ValueError("Phát hiện nhiều khuôn mặt, vui lòng chọn ảnh chân dung duy nhất.")`.
   - Lấy vector 128d `face_encoding`.
   - Sao chép ảnh vật lý vào `data/students/` hoặc `data/teachers/` bằng shutil. Sử dụng tên ảnh định dạng `{code}.jpg` để dễ quản lý. Cần tự tạo parent directory nếu chưa có (`os.makedirs`).
4. **Database Behavior & Error Handling (CRITICAL)**:
   - Khởi tạo Manager theo mô hình Dependency Injection (truyền `db_manager` vào scope). 
   - **Lưu ý lớn:** Các hàm của `db_manager` ở Story 2.1 ĐÃ catch `sqlite3.Error` bên trong và trả về `None` (khi insert lỗi) hoặc `False` (khi thao tác lỗi). Hệ thống DB **KHÔNG ném Exception** ra khỏi hàm của nó.
   - Code `add_student()`: Khi add bản ghi chính (teacher/student), nếu DB func trả về `None`, phải dọn dẹp (xoá) file ảnh vật lý vừa lưu, sau đó raise custom Exception / ValueError cho view layer.
   - Rollback tự động: Nếu insert thành công bản ghi đầu tiên nhưng `add_encoding(...)` trả về `None`, **bắt buộc manual rollback** bằng cách gọi `db_manager.delete_student()` (hoặc `delete_teacher()`), xoá file ảnh, và sau đó raise Lỗi báo hệ thống.
5. **Deletion Logic**: Lệnh `remove_student()` / `remove_teacher()` gọi db func xoá DB gốc (từ đó đã cascade vào `face_encodings`), và Manager tự lo logic giải phóng ảnh vật lý. **Bắt buộc** check `os.path.exists()` trước khi gọi `os.remove()` để tránh lỗi `FileNotFoundError`.
6. Xử lý Trả về (Return Value): Hàm trả về map dữ liệu nguyên thủy (python dict) lấy ra từ Database Manager mà không chế biến dư thừa. Đẩy mọi lỗi bắt được dưới dạng `ValueError` / `Exception` chứa mã lỗi rõ ràng.

## Tasks / Subtasks

- [x] Khởi tạo file `src/core/student_manager.py`
  - [x] Implement `StudentManager` class nhận tham số `db_manager`.
  - [x] Viết hàm `add_student(name, student_code, image_path)` với flow chuẩn xác: Validation mặt -> Lưu file ảnh -> Insert record -> Insert encoding. Có tính năng tự động rollback xoá cả file lẫn gọi `delete_student` nếu insert encoding thất bại.
  - [x] Viết hàm `get_student(student_id)` và `get_all_students()`.
  - [x] Viết hàm `remove_student(student_id)` có logic xóa DB và dọn ảnh vật lý.
- [x] Khởi tạo file `src/core/class_manager.py`
  - [x] Implement `ClassManager` class nhận tham số `db_manager`.
  - [x] Viết nghiệp vụ teacher (`add_teacher`, `get_teacher`, `get_all_teachers`, `remove_teacher`) vận hành giống hệt học sinh (cùng 1 model behavior và validation khuôn mặt).
  - [x] Viết nghiệp vụ class (`add_class`, `get_class`, `get_all_classes`, `get_classes_by_teacher`, `delete_class`).
  - [x] Viết nghiệp vụ gán SV-Lớp (`add_student_to_class`, `remove_student_from_class`, `get_students_in_class`).

## Dev Notes

### Architecture Compliance
- **Dependency Injection**: Inject instance module `DatabaseManager` để module Manager chỉ là Business Logic Layer vận hành lệnh tới Storage Layer. Các config này tuân thủ MVP Architecture trong thiết kế, Presenter (`main.py`) sau này sẽ connect instance DBManager với Class/StudentManager.

### File Structure Requirements
- Path đích: `src/core/student_manager.py`, `src/core/class_manager.py`.
- Path thư mục chứa nội dung media: `data/students/` và `data/teachers/`.

### Library & Framework Requirements
- `face_recognition`: Sử dụng API chuẩn của lib, `load_image_file()`, `face_locations()` (kiểm tra `len == 1`), `face_encodings(...)[0]` để extract 128 dimension array (dùng NumPy).
- DBManager ở epic trước đã xử lý serialize BLOB nên Manager hiện tại chỉ cần đẩy Numpy array vào API DB mà không cần tobytes().
- Image transfer operation: Import module `shutil` và os function cho copy ảnh vật lý.  

### Previous Story Intelligence
- `2-1-database-sqlite.md` cho biết là DBManager delete helper func đã tự thủ công xóa DB tuple tại bảng `face_encodings` trên cùng transaction nên Dev Không cần phải call xoá encodings table. Manager chỉ call `db_manager.delete_student(student_id)` và clear media.
- DBManager APIs trả về Python `dict` thay vì SQLite row và trả về `None`/`False` khi lỗi rớt mạng/lock. **Lưu ý: Không dùng try...except bao bọc lệnh gọi db vì DBManager không quăng lỗi.**
- Tối ưu DRY (Don't Repeat Yourself): Bước validation face và xử lý ảnh ở Student hay Teacher là y hệt nhau. Viết chung logic này thành một internal static method `_process_and_save_face(image_path, person_code, output_dir)` để các method `add_student` và `add_teacher` gọi chung, tránh bôi code 2 nơi.

### References

- [Source: sprint-status.yaml#L209-L220] - Đích thân story yêu cầu nghiệp vụ E2-S2
- [Source: docs/lich-su-thao-luan.md#L341-L356] - Flow nhận diện 1 người tại 1 thời điểm quy tắc xử lý
- [Source: _bmad-output/implementation-artifacts/2-1-database-sqlite.md#L67-L69] - Deletion/Cascading constraints requirement behavior của lớp phía dưới (DB)

## Dev Agent Record

### Agent Model Used

Gemini 3.1 Pro (High)

### Document Updates
- Ultimate context engine analysis completed - comprehensive developer guide created.

### Completion Notes
- ✅ Processed and extracted face encoding logic into `src/core/face_utils.py` to keep code DRY.
- ✅ Implemented `StudentManager` incorporating business logic for faces validations, DB insertion, robust error handling, and manual rollback.
- ✅ Implemented `ClassManager` performing teachers operations with same rules applied, combined with classes/enrollments logic.
- ✅ Thoroughly verified behavior with complete TDD coverage via `unittest`.

## File List
- [NEW] src/core/face_utils.py
- [NEW] src/core/student_manager.py
- [NEW] src/core/class_manager.py
- [NEW] tests/test_face_utils.py
- [NEW] tests/test_student_manager.py
- [NEW] tests/test_class_manager.py
- [CHANGE] src/core/__init__.py

## Senior Developer Review (AI)
### Action Items
- [x] [AI-Review][High] `add_student` and `add_teacher` must return the primitive DB dictionary mapping instead of boolean `True`.
- [x] [AI-Review][Medium] `_process_and_save_face` was writing `filename = {person_code}.jpg` which is susceptible to path traversal.
- [x] [AI-Review][Low] `os.remove(photo_path)` should gracefully be ignored if the physical disk deletes it underneath the system context, to prevent API collapse.

### Review Follow-ups (AI)
- [x] Addressed findings by automatically resolving return types and file system calls (`src/core/class_manager.py`, `src/core/student_manager.py`, `src/core/face_utils.py`). Tests mutated to reflect structure successfully.
- [x] [AI-Review][High] Raised descriptive `ValueError` during failed operations in `add_student_to_class` and `remove_student_from_class`.
- [x] [AI-Review][High] Filled TDD coverage gaps with complete failure paths for `add_class`, enrollments, and explicit OSError assertion.
- [x] [AI-Review][Medium] Removed illegal `tolist()` coercions inside `_process_and_save_face` in observance of interface agreements.
- [x] [AI-Review][Medium] Tracked untracked project initialization modules into the Story manifest.

## Change Log
- 2026-04-21: Implemented logic layer for Student and Teacher managers. Included robust DB transaction rollbacks manually according to database implementation limitations. All unit tests generated successfully.
- 2026-04-21: Code Review executed. Resolved finding: Return dict from addition APIs, path traversal security vulnerability in `face_utils`, and `OSError` robustness in manager teardowns.
- 2026-04-21: Second Code Review executed. Fixed missing exception handling in enrollment operations, supplemented missing unhappy path unit tests, strictly cast encoding arrays to numpy variants, and resolved undocumented Git file changes.
