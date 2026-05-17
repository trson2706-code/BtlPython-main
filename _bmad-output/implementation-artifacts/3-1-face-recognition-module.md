# Story 3.1: Module nhận diện khuôn mặt
Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

Là một **hệ thống (Core System)**,
Tôi muốn **cung cấp các hàm xử lý tập trung cho tính năng nhận diện khuôn mặt (detect, encode, compare) sử dụng face_recognition và OpenCV**,
Để **hệ thống có thể trích xuất đặc trưng và đối chiếu sinh viên/giảng viên chính xác theo các quy định dung sai (tolerance) đã cấu hình.**

## Acceptance Criteria

1. File `src/core/recognition.py` chứa tất cả các hàm liên quan đến face recognition.
2. Hàm `detect_faces` có validate đầu vào (`image` không `None` và hợp lệ). Xử lý chuyển đổi ảnh OpenCV (BGR) sang RGB trước khi xử lý (bắt buộc cho thư viện `face_recognition`). 
3. Hàm `detect_faces` tối ưu trả về tọa độ bounding box khuôn mặt lớn nhất (theo cấu hình rules `faces_per_frame: 1`). Nếu tìm thấy nhiều mặt, phải tính diện tích và chỉ lấy 1 mặt to nhất (fallback lấy index `[0]` nếu bằng diện tích). Đảm bảo scale up toạ độ một cách chính xác nếu đã resize frame.
4. Hàm `encode_face` tạo ra vector 128d (NumPy array). Phải có logic xử lý lỗi an toàn nếu `face_encodings` trả về mảng rỗng.
5. Hàm `find_best_match` duyệt vector đầu vào so sánh với danh sách vector đã biết (cùng chỉ mục với danh sách `known_metadata`) ưu tiên dung sai `tolerance` (cấu hình mặc định 0.5 - 0.6).
6. Hàm `calculate_confidence` chuyển đổi khoảng cách vector sang % độ tin cậy được clamp an toàn trong khoảng `0.0` đến `100.0`.
7. Các hàm là Pure Functions, không gọi trực tiếp Database để giữ độc lập kiến trúc. Nên sử dụng `dataclass` hoặc `TypedDict` để định nghĩa kiểu dữ liệu trả về rõ ràng (không dùng tuple ngầm định).

## Tasks / Subtasks

- [x] Tạo file `src/core/recognition.py`
  - [x] Import thư viện cần thiết (`cv2`, `face_recognition`, `numpy`, `dataclass`/`TypedDict`, load config từ `src.core.config`).
  - [x] Tạo các data model cho ouput results (Ví dụ: `FaceDetectionResult`, `MatchResult`).
- [x] Xây dựng các hàm xử lý khuôn mặt căn bản (Core detection functions)
  - [x] Viết hàm `detect_faces(image)`: 
    - Early return / Handle lỗi nếu input bị rỗng hoặc là `None`.
    - Chuyển `image` từ BGR sang RGB.
    - (Optional) Thu nhỏ ảnh (resize 1/4) bằng `cv2.resize` để tăng tốc độ nhận diện.
    - Gọi `face_recognition.face_locations(rgb_small_frame, model="hog")`.
    - Tính diện tích lọc mặt. Nếu dùng tính năng scale down, BẮT BUỘC nhân tỷ lệ (VD: `top*4, right*4, bottom*4, left*4`) cho kết quả toạ độ gốc trả về.
  - [x] Viết hàm `encode_face(image, location)`: 
    - Chuyển BGR sang RGB.
    - Gọi `face_recognition.face_encodings`. Nếu kết quả rỗng (không trích xuất được do mờ/bóng), return `None`.
- [x] Xây dựng các hàm đối chiếu và so sánh (Matching logic)
  - [x] Viết hàm `compare_faces(unknown, known_list, tolerance)`: wrap lại `face_recognition.face_distance`.
  - [x] Viết hàm `find_best_match(encoding, known_encodings, known_metadata, tolerance)`: 
    - Lấy index `distance` nhỏ nhất.
    - Nếu `min_distance <= tolerance`, trả về data array dưới dạng strongly-typed object .
  - [x] Viết hàm `calculate_confidence(face_distance, face_match_threshold=0.6)`: Trả về float được clamp giới hạn trong khoảng `0.0` - `100.0`.

## Dev Notes

- **Relevant architecture patterns and constraints:** 
  - KHÔNG truy vấn trực tiếp SQLite (`src/core/database.py`) trong file này. Vector sẽ được truyền vào từ bên ngoài (như Worker thread).
  - Config `tolerance: "0.5 - 0.6"` mặc định lấy từ module config chung.
  - **🚨 CRITICAL - BGR vs RGB**: OpenCV mặc định sử dụng BGR format, `face_recognition` yêu cầu RGB. Cần thêm dòng `rgb_frame = image[:, :, ::-1]`.
  - **🚨 CRITICAL - M1 Performance & Scaling Coordinate**: Ở macOS M1, BẮT BUỘC dùng tham số `model='hog'`, NÊN resize ảnh `fx=0.25, fy=0.25` trên luồng 30fps. Quan trọng: nếu resize thì sau khi thư viện trả về bbox, PHẢI tự động "scale-up" bounding box lại trước khi trả ra kết quả.
  - **🚨 CRITICAL - IndexError Protection**: Hàm `face_encodings` thỉnh thoảng trả về list rỗng `[]` kể cả khi có tọa độ. Code phải phòng thủ trường hợp length mảng bằng 0.
- **Source tree components to touch:**
  - `src/core/recognition.py` (Mới)
- **Testing standards summary:**
  - Viết Type Hints đầy đủ.
  - Xử lý kịch bản test input bị empty, hoặc giá trị fallback khi detect nhiều face có diện tích y hệt nhau.
  - Kiểm tra range cho calculate_confidence từ 0 - 100.

### Project Structure Notes

- Alignment with unified project structure: Sẽ nằm ở package `src/core/`.

### References

- `sprint-status.yaml` : `tech_stack: face_recognition 1.3.0 + dlib 20.0.1`, `tolerance: 0.5 - 0.6`, quy tắc 1 khuôn mặt/frame.

## Dev Agent Record

### Agent Model Used

Gemini 3.1 Pro (High)

### Debug Log References

### Completion Notes List
- Ultimate context engine analysis completed - comprehensive developer guide created.
- [Party Mode Updates] Thêm Data models (TypedDict), safe bounding box coordinate tracking, input corrupt checks, and edge-cases safety bounding.
- Định dạng mảng numpy đã được bắt lỗi cẩn thận, bao gồm cả hỗ trợ ảnh Grayscale (2D). Thời gian xử lý lỗi đủ chuẩn (có log thay vì swallow exception).
- Hoàn thành module `src/core/recognition.py` bao gồm chức năng detect, encode, compare và tính toán confidence.
- Viết bộ test suite bao phủ logic trong `tests/test_recognition.py` (11 tests). 
- Các Action Items từ đợt Review Adverasrial đã được tự động fix 100%.

### File List
- `src/core/recognition.py` (Mới)
- `tests/test_recognition.py` (Mới)

### Change Log
- Ngày 21/04/2026: Sửa lại lỗi "Swallowed exception" bằng cách tích hợp standard `logging`, nâng cấp bộ validate đầu vào hình ảnh cho `detect_faces` \& `encode_face` (`.ndim` shape checks cho ảnh BGR/BGRA/Grayscale). Chỉnh sửa đúng đắn các assertion unit test.
- Ngày 21/04/2026: Triển khai các pure functions của module face recognition, đảm bảo xử lý hình ảnh độc lập (chuyển BGR sang RGB, HOG detection, padding boxes). Hoàn tất các Unit Tests tương ứng.
