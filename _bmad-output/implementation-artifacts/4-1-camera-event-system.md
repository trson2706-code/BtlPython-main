# Story 4.1: camera-event-system

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a developer,
I want to implement the camera and event system module,
so that the application can capture video frames smoothly without crashing and broadcast hardware events out to other components.

## Acceptance Criteria

1. **Camera Module**: `src/core/camera.py` includes a `CameraManager` class to encapsulate OpenCV's `VideoCapture` functionality.
2. **Configuration**: Retrieves `camera_id` (e.g., 0, 1) and settings from the environment or `Config` properly.
3. **Continuous Background Reading**: To prevent GUI stutter and buffer lag, `CameraManager` MUST use an internal background thread to continuously read frames (`cap.read()`) and store the latest frame.
4. **Frame Processing**: `get_frame()` safely returns a copy of the latest recorded RGB frame (converted from OpenCV's BGR) without blocking or reading from the camera directly.
5. **Resilience & Runtime Disruption**: `open_camera()` handles errors when the camera is unavailable. If the connection is lost mid-stream (e.g., `cap.read()` returns `False` or raises an exception), the background thread MUST catch it, break the loop, release resources, and emit `EventType.ERROR_OCCURRED` and `EventType.CAMERA_STOPPED`.
6. **Event Emission**: Emits `EventType.CAMERA_STOPPED` or `EventType.ERROR_OCCURRED` using `events.emit` when the stream stops or fails, both during initialization and runtime.
7. **Thread Safety**: Access to the latest frame and camera state is protected by `threading.Lock()`. The lock MUST ONLY wrap the variable assignment/copying (`_latest_frame`), NOT the `cap.read()` call itself, to avoid blocking the GUI thread.

## Tasks / Subtasks

- [x] Tạo module `src/core/camera.py` với class `CameraManager`.
  - [x] Nhập các dependencies cơ bản: `cv2`, `threading`, `logging`, `numpy`, `src.core.events.events`, `src.core.events.EventType`.
- [x] Implement methods `start()` và `stop()`.
  - [x] `start()`: Gọi `cv2.VideoCapture(camera_id)`. Nếu lỗi, logging và phát sự kiện `ERROR_OCCURRED`. Nếu thành công, khởi động một internal `threading.Thread` (daemon=True) chạy hàm `_update_frame` liên tục.
  - [x] `stop()`: Đặt cờ dừng thread, đợi thread kết thúc (`join` với một timeout hợp lý để tránh treo GUI), gọi `cap.release()`, và emit `CAMERA_STOPPED` ngay sau khi thiết bị giải phóng.
- [x] Implement hàm internal `_update_frame()` chạy trong thread.
  - [x] Vòng lặp liên tục đọc frame bằng `cap.read()` bên trong khối `try/except`.
  - [x] Nếu `ret` là False hoặc gặp ngoại lệ (mất kết nối vật lý), catch lỗi, phát `ERROR_OCCURRED`, nhả resource, phát `CAMERA_STOPPED` rồi `break` vòng lặp.
  - [x] Nếu `ret` là True, convert BGR to RGB bằng `cv2.cvtColor`.
  - [x] Lưu frame vào `self._latest_frame` với `threading.Lock()`. Chú ý KHÔNG để Lock bao trùm lệnh `cap.read()`.
- [x] Implement method `get_frame()`.
  - [x] Trả về copy của `self._latest_frame` một cách thread-safe (dùng Lock). Trả về None nếu camera chưa sẵn sàng.
- [x] Tạo unit tests cho `CameraManager` trong `tests/test_camera.py`.
  - [x] Mock `cv2.VideoCapture` và `threading.Thread` để tránh việc camera thật được bật khi test.
  - [x] Test tính thread-safe khi get_frame.
  - [x] Test event emission cả 2 trường hợp: Initialization failure (lỗi ngay lúc khởi tạo) và Runtime disruption (đang chạy thì `cap.read` trả về `False`).

## Dev Notes

- **Architecture Patterns**: Singleton dùng chung cho events (`events` global). CameraManager thuộc layer Model. GUI (View) tuyệt đối không truy cập trực tiếp opencv mà bắt buộc gọi method của CameraManager.
- **Continuous Reading Thread**: Cực kỳ quan trọng! `cv2.VideoCapture.read()` chạy đồng bộ (blocking). Nếu không có background thread liên tục lấy frame, bộ đệm camera của hệ điều hành sẽ đầy gây trễ hình (lag). Hơn nữa, việc cho nhiều thread cùng gọi `cap.read()` sẽ dễ gây crash hệ thống.
- **Threading**: Cực kỳ quan trọng, sử dụng `threading.Lock` trong `CameraManager` khi ghi/đọc `self._latest_frame`. GUI thread sẽ lấy frame liên tục để hiển thị 30fps (thông qua `get_frame()`), đồng thời Worker thread (nhận diện ngầm) cũng sẽ gọi nó. **LƯU Ý:** Khóa chỉ được bật lúc copy hoặc assign đối tượng ảnh, cấm bọc Lock quanh quá trình blocking IO như bước `cap.read()`.
- **Thread Joining**: Cần cẩn thận khi dùng `thread.join()` trong `stop()` để không đụng phải Deadlock. Luôn dùng timeout.
- **Formats**: Thư viện OpenCV trả về BGR, nhưng CustomTkinter và thư viện `face_recognition` đều đang giả định định dạng là RGB. Thực hiện convert ngay tại hàm `_update_frame()` để cho các modules được nhất quán.

### Project Structure Notes

- **Thêm file:** `src/core/camera.py`
- **Thêm file:** `tests/test_camera.py`
- Tuân thủ thống nhất MVP và thư mục như đã quyết định trong tài liệu.

### References

- [Sprint Status Document](file:///Users/huynguyen/work/projects/BtlPython/_bmad-output/implementation-artifacts/sprint-status.yaml)
- [Kiến trúc & Lịch sử thảo luận](file:///Users/huynguyen/work/projects/BtlPython/docs/lich-su-thao-luan.md)

## Dev Agent Record

### Agent Model Used

Gemini 3.1 Pro (High)

### Debug Log References

N/A

### Completion Notes List

- ✅ Đã phát triển thành công `CameraManager` chạy trên thread nền.
- ✅ Implement lock bao quanh việc lấy frame, không block quá trình capture.
- ✅ BGR sang RGB convert được thực hiện trên background thread.
- ✅ Unit tests bao phủ các tình huống mất kết nối (`cap.read` fail) và lỗi initialization được pytest pass 100%.
- ✅ Đã emit đúng event `CAMERA_STOPPED` và `ERROR_OCCURRED`.

### Senior Developer Review (AI)

- **High/Medium Issues Fixed**: 
  - AC 2: Implemented environment variable retrieval (`CAMERA_ID`) for camera configuration.
  - Test Performance: Throttled `mock_cap.read()` in unit tests to prevent 100% CPU pinning via infinite while loop execution.
  - Logical Bug: Prevented duplicate `CAMERA_STOPPED` event emissions on shutdown.
  - Segfault Risk: Deferred `self.cap.release()` to the background thread to prevent OpenCV crashes from conflicting threads.
- **Low Issues Fixed**: Removed unused numpy import in camera.py.

### File List

- `src/core/camera.py`
- `tests/test_camera.py`
