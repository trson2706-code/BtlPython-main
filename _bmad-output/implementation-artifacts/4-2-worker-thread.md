# Story 4.2: worker-thread

Status: done

## Story

As a developer,
I want to implement a background worker thread for face recognition,
so that the application can seamlessly detect and identify faces (teachers or students) continuously without freezing the main GUI, maintaining a smooth 30fps camera preview.

## Acceptance Criteria

1. **Worker Module**: `src/core/worker.py` is created with a `RecognitionWorker` class extending `threading.Thread`.
2. **Recognition Modes**: Supports two distinct scanning modes based on state: Mode 1 (Teacher Authentication mode - wait for teacher & match with teacher DB) and Mode 2 (Student Attendance mode - match against students of the currently loaded class).
3. **Throttled Processing**: Limits CPU usage by NOT processing every frame. Fetches a frame from `CameraManager` and runs detection every 0.5 to 1.0 seconds.
4. **Single-face Rule**: Only processes one face at a time per frame (`faces_per_frame: 1`).
5. **Auto-capture**: Automatically saves a snapshot to `data/detections/` when a successful recognition occurs.
6. **Thread-safe Output**: Emits results (person identified, confidence, coordinates) and handles GUI communication safely via the centralized `src.core.events` module without directly invoking GUI.
7. **Lifecycle Controls**: Implement `start_scanning()` and `stop_scanning()` to allow temporary pausing/resuming, and properly handle graceful thread shutdown on application exit.

## Tasks / Subtasks

- [x] Tạo module `src/core/worker.py` với class `RecognitionWorker(threading.Thread)`.
  - [x] Khởi tạo Thread nền daemon (daemon=True) để tránh block app khi exit.
  - [x] Lấy các cấu hình từ `src.core.config.Config()` như `scan_interval`, `tolerance` và `faces_per_frame`.
  - [x] Set up state management (`self.running`, `self.paused`, `self.current_mode`, `self._lock`).
- [x] Implement hàm `run()` thực thi vòng lặp vòng đời worker.
  - [x] Áp dụng cơ chế throttling vòng lặp kết hợp graceful shutdown bằng cách sử dụng `self.stop_event.wait(timeout=config.scan_interval)` để đảm bảo tần suất lấy mẫu khoảng 0.5 - 1s/frame mà không dùng `time.sleep()`.
  - [x] Trích xuất ảnh RGB từ `CameraManager.get_frame()`. **LƯU Ý:** Ảnh đã được convert sang RGB trong CameraManager, KHÔNG convert lại. Bắt buộc thêm kiểm tra `if frame is None:` trước khi xử lý để tránh crash khi camera lỗi nhịp.
  - [x] Gọi hàm detect/encode từ `src.core.recognition` (đảm bảo chỉ detect tối đa `faces_per_frame` khuôn mặt).
- [x] Implement 2 chế độ nhận diện.
  - [x] Chế độ chờ Giảng viên: lấy danh sách encodings giảng viên để dò tìm `compare_faces`.
  - [x] Chế độ điểm danh: giới hạn tập so sánh là sinh viên của class_id hiện hành.
- [x] Xử lý lưu ảnh và phát sự kiện thành công.
  - [x] Tạo module tự chụp ảnh vào thư mục `data/detections/` khi tìm thấy matching face.
- [x] Truyền dữ liệu kết quả phân tích về GUI thông qua `src.core.events.emit()` như đã thống nhất trong kiến trúc (sử dụng EventType phù hợp). TUYỆT ĐỐI KHÔNG dùng Queue hay gọi trực tiếp GUI.
- [x] Viết unit tests cho module này trong `tests/test_worker.py`.
  - [x] Kiểm thử việc stop/pause thread thành công và gọn gàng.
  - [x] Thử nghiệm luồng emit events xem có hoạt động đúng trong môi trường test hay không.

## Dev Notes & Architecture Constraints

- **Frame Color Space**: Theo Story 4.1 (Camera), `CameraManager.get_frame()` đã trả về ảnh **RGB**. Thư viện `face_recognition` yêu cầu RGB gốc. **TUYỆT ĐỐI KHÔNG** sử dụng `cv2.cvtColor` để đổi RGB sang BGR hoặc ngược lại trong Worker vì sẽ làm hỏng dữ liệu model.
- **Resource Constraints**: CPU Bound! Thư viện dlib/face_recognition rất ngốn CPU khi chạy `encode_face()`. Không gọi hàm `time.sleep()` có thể gây treo thread khi shutdown, thay vào đó hãy dùng `stop_event.wait(timeout=config.scan_interval)`. Lấy `scan_interval` từ lớp `Config` đễ giãn cách frame xử lý (thường là 0.5s - 1.0s). 
- **Threading Risks**: Tuyệt đối không được gọi trực tiếp đối tượng Tkinter/CustomTkinter từ Worker thread, điều này sẽ làm UI system crash (SIGSEGV) ngay lập tức. Bắt buộc phải cấu hình backend events thông qua `src.core.events.emit()`.
- **Face DB Fetching**: Thay vì call DB trực tiếp trong vòng lặp, hãy nạp trước danh sách face encodings vào RAM (ví dụ một dict mapping id → encoding) mỗi khi bắt đầu một session điểm danh hoặc chờ giảng viên, giúp quá trình so sánh real-time diễn ra O(1).
- **Graceful Shutdown**: Method `stop()` phải sử dụng system events (`threading.Event` thay vì cờ boolean thường) để break loop sleep bên trong, không dùng thủ thuật kill thread.
- **Image Capturing**: Khi chụp ảnh tĩnh, nhớ sử dụng `cv2.cvtColor(rgb_frame, cv2.COLOR_RGB2BGR)` trước khi lưu bằng `cv2.imwrite()`, vì OpenCV chỉ lưu chuẩn form BGR!

### Project Structure Notes

- **File thêm**: `src/core/worker.py`
- **File test thêm**: `tests/test_worker.py`
- Giữ nguyên thống nhất kiến trúc Model-View-Presenter (thuộc Model layer).
  
### References

- [Docs: Lịch sử thảo luận](file:///Users/huynguyen/work/projects/BtlPython/docs/lich-su-thao-luan.md)
  (Sections 13: Luồng hoạt động chính thức, Section 15: Threading Model)
- [Sprint Status Document](file:///Users/huynguyen/work/projects/BtlPython/_bmad-output/implementation-artifacts/sprint-status.yaml)
- Tham khảo code từ `src/core/camera.py` trong previous story (4-1).

## Dev Agent Record

### Agent Model Used



### Debug Log References



### Completion Notes List

- Implemented `RecognitionWorker` as a subclass of `threading.Thread` with daemon set to True.
- Throttled loops cleanly using `self.stop_event.wait(timeout=scan_interval)`.
- Ensured thread-safe parameter loads via `load_encodings` where the worker keeps its own copies of lists during its wait loop.
- Properly saving detected faces via OpenCV by converting RGB directly back to BGR.
- Evaluated unit testing logic that proves thread throttling and event emitting using mocks.
- **[Code Review Fix]** Added `faces_per_frame` to configuration extraction.
- **[Code Review Fix]** Moved sleep throttling to the end of the loop and utilized a `wake_event` to ensure immediate processing upon unpausing, resolving frontend UX lag.
- **[Code Review Fix]** Bound database validation strictly to its runtime mode via `person_type` metadata parsing to prevent race conditions during DB swapping.

### File List

- `src/core/worker.py`
- `tests/test_worker.py`
