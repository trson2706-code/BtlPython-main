# Hệ Thống Điểm Danh Sinh Viên Bằng Nhận Dạng Khuôn Mặt (Face Recognition Attendance System)

Hệ thống điểm danh sinh viên tích hợp công nghệ nhận dạng khuôn mặt thời gian thực và giải thuật chống giả mạo khuôn mặt (Anti-Spoofing/Liveness Detection) đa chỉ số. Dự án được thiết kế theo mô hình kiến trúc sạch MVP (Model-View-Presenter) kết hợp Event Bus giúp tối ưu hóa hiệu năng, dễ dàng bảo trì và mở rộng.

---

## 🌟 Tính Năng Nổi Bật

1. **Nhận Diện Khuôn Mặt Thời Gian Thực**:
   * Tự động phát hiện khuôn mặt lớn nhất trong khung hình (tránh nhiễu từ đám đông).
   * Trích xuất đặc trưng khuôn mặt (128-d Face Embedding) thông qua mô hình HOG/CNN của thư viện `dlib` và `face-recognition`.
   * Khớp khuôn mặt với cơ sở dữ liệu nhanh chóng và chính xác.

2. **Chống Giả Mạo Khuôn Mặt (Liveness Detection)**:
   * Tích hợp bộ lọc chống giả mạo heuristic đa chỉ số (không phụ thuộc vào mạng Deep Learning nặng nề):
     * **Texture (Cấu trúc bề mặt)**: Sử dụng phương sai Laplacian để phát hiện ảnh chụp in trên giấy hoặc màn hình có độ sắc nét giả lập.
     * **Color (Phân bố màu sắc)**: Kiểm tra tỷ lệ màu da trong không gian màu YCrCb.
     * **Moiré (Vân sọc màn hình)**: Phân tích tần số FFT để phát hiện các vân nhiễu Moire khi chụp qua màn hình điện thoại/máy tính bảng.
     * **Reflection (Phản xạ ánh sáng)**: Nhận biết hiện tượng phản quang chói sáng từ màn hình thiết bị hoặc kính.
     * **Edge Density (Mật độ cạnh)**: Sử dụng Canny Edge Detection để phân tích cấu trúc biên.
   * Cấu hình linh hoạt trọng số (weights) và ngưỡng (thresholds) trực tiếp trong file cấu hình.

3. **Điểm Danh Tự Động Theo Thời Khóa Biểu**:
   * **Chế độ 1 (Quét Giảng viên)**: Chờ giảng viên đứng lớp xác nhận danh tính trước camera để mở phiên học phù hợp theo lịch dạy.
   * **Chế độ 2 (Điểm danh Sinh viên)**: Tự động tải danh sách sinh viên của lớp đó và bắt đầu điểm danh.
   * **Điểm danh thủ công**: Cho phép giảng viên bấm chọn điểm danh thủ công trực tiếp trên giao diện đối với các trường hợp đặc biệt.

4. **Giao Diện CustomTkinter Hiện Đại**:
   * Giao diện phong cách Dark Mode chuyên nghiệp, tối ưu hiển thị cho máy tính Windows.
   * Tích hợp ô hiển thị Bounding Box thông minh (Màu xanh: Nhận diện thành công / Màu đỏ: Không khớp hoặc Phát hiện giả mạo).
   * Popup hiển thị thống kê tức thì ngay sau khi kết thúc phiên điểm danh kèm nút mở file báo cáo nhanh.

5. **Trình Quản Trị Hệ Thống (Admin Window)**:
   * Quản lý thông tin Giảng viên, Sinh viên, Môn học/Lớp học.
   * Xếp lịch học (Thời khóa biểu) cho từng lớp.
   * Tra cứu và xem lịch sử điểm danh trực quan theo từng lớp học, xuất Excel thủ công bất cứ lúc nào.

6. **Xuất Báo Cáo Excel Tự Động**:
   * Tự động tạo và lưu trữ tệp báo cáo điểm danh định dạng `.xlsx` ngay sau khi phiên học kết thúc.
   * Ghi nhận đầy đủ thông tin: Mã sinh viên, Họ tên, Thời gian quét mặt, Độ tin cậy (Confidence) và Trạng thái điểm danh.

---

## 📂 Cấu Trúc Mã Nguồn

```text
BtlPython-main/
├── config.yaml                    # File cấu hình các thông số hệ thống
├── requirements.txt               # Định nghĩa các thư viện phụ thuộc
├── setup_demo.py                  # Script tạo dữ liệu mẫu ban đầu để kiểm thử nhanh
├── fix_db.py                      # Script hỗ trợ bảo trì, nâng cấp cấu trúc database
├── data/                          # Dữ liệu của hệ thống
│   ├── attendance.db              # Database SQLite chính
│   ├── detections/                # Lưu ảnh chụp khuôn mặt khi điểm danh thành công
│   ├── exports/                   # Thư mục lưu trữ file Excel báo cáo đã xuất
│   ├── students/                  # Chứa ảnh đăng ký của Sinh viên
│   └── teachers/                  # Chứa ảnh đăng ký của Giảng viên
├── src/                           # Mã nguồn chính
│   ├── main.py                    # Điểm chạy duy nhất (Presenter / Orchestrator)
│   ├── core/                      # Tầng Model (Logic nghiệp vụ và Xử lý AI nền)
│   │   ├── config.py              # Đọc/ghi cấu hình từ config.yaml
│   │   ├── database.py            # Quản trị cơ sở dữ liệu SQLite
│   │   ├── camera.py              # Quản lý luồng video OpenCV
│   │   ├── worker.py              # Luồng nền nhận diện khuôn mặt (Threading)
│   │   ├── recognition.py         # Thao tác phát hiện & so khớp khuôn mặt
│   │   ├── liveness.py            # Xử lý chống giả mạo khuôn mặt (Anti-spoofing)
│   │   ├── attendance_session.py  # Quản lý vòng đời một phiên điểm danh
│   │   ├── excel_export.py        # Xuất dữ liệu ra Excel
│   │   └── events.py              # Event Bus truyền tin nội bộ (Pub/Sub)
│   └── gui/                       # Tầng View (Giao diện CustomTkinter)
│       ├── app.py                 # Khung ứng dụng chính
│       ├── camera_panel.py        # Widget hiển thị camera và Bounding Box
│       ├── session_panel.py       # Quản lý trạng thái phiên học và nút bấm GV
│       ├── attendance_panel.py    # Danh sách sinh viên đã điểm danh thành công
│       ├── student_panel.py       # Quản lý danh sách sinh viên lớp hiện tại
│       └── admin_window.py        # Cửa sổ quản trị hệ thống
└── tests/                         # Thư mục chứa mã nguồn kiểm thử tự động
```

---

## 🛠️ Hướng Dẫn Cài Đặt

### 1. Yêu cầu hệ thống
* **Hệ điều hành**: Windows 10/11, macOS, Linux.
* **Phiên bản Python**: Khuyến nghị dùng **Python 3.9, 3.10 hoặc 3.11** để cài đặt thư viện `dlib` dễ dàng nhất.

### 2. Cài đặt các thư viện
Mở Command Prompt / Terminal tại thư mục dự án và chạy lệnh sau:
```bash
pip install -r requirements.txt
```
*Lưu ý đối với dlib:* Nếu gặp lỗi khi build dlib từ mã nguồn, bạn cần cài đặt Build Tools cho Visual Studio (đối với Windows) hoặc tải bản wheel tiền biên dịch phù hợp (như gói `dlib-bin` đã được cấu hình sẵn trong file `requirements.txt`).

---

## 🚀 Hướng Dẫn Sử Dụng

### Bước 1: Khởi tạo dữ liệu mẫu (Demo Data)
Để chạy thử hệ thống ngay lập tức với dữ liệu giả lập (thời khóa biểu giảng viên dạy ngày hôm nay, danh sách lớp học và sinh viên mẫu), chạy lệnh sau:
```bash
python setup_demo.py
```
*Script này cũng sẽ tự tạo các thư mục lưu trữ ảnh và cơ sở dữ liệu ban đầu tại thư mục `data/`.*

### Bước 2: Chạy ứng dụng
Khởi chạy ứng dụng bằng lệnh:
```bash
python src/main.py
```
hoặc:
```bash
python -m src.main
```

### Bước 3: Luồng vận hành ứng dụng
1. **Chờ giảng viên**:
   * Hệ thống khởi động ở trạng thái **Chờ Giảng viên**.
   * Giảng viên đứng trước camera để hệ thống quét khuôn mặt và kiểm tra Liveness.
   * Khi khớp thông tin giảng viên và lịch dạy hợp lệ của ngày hôm nay, nút **Xác nhận mở lớp** sẽ sáng lên.
2. **Tiến hành điểm danh**:
   * Giảng viên bấm **Xác nhận**. Hệ thống tự động chuyển sang chế độ điểm danh sinh viên của lớp học tương ứng.
   * Sinh viên đứng trước camera để thực hiện điểm danh. Nếu hợp lệ, hệ thống ghi nhận trạng thái có mặt và chụp ảnh snapshot lưu vào thư mục `data/detections/`.
3. **Kết thúc & Xuất báo cáo**:
   * Khi hết thời gian hoặc giảng viên bấm **Kết thúc**, hệ thống lưu toàn bộ dữ liệu phiên học vào lịch sử DB, tự động xuất file Excel báo cáo vào thư mục `data/exports/` và hiển thị Popup kết quả.
   * Sau 5 giây, hệ thống tự động dọn dẹp và quay về trạng thái **Chờ Giảng viên** ban đầu.

---

## ⚙️ Cấu Hình Hệ Thống (`config.yaml`)

File `config.yaml` cho phép bạn tinh chỉnh các thông số hoạt động của hệ thống mà không cần sửa code:
* **`camera`**: Cấu hình ID camera, độ phân giải hiển thị và FPS.
* **`recognition.tolerance`**: Ngưỡng khoảng cách đặc trưng khuôn mặt (khoảng từ `0.4` - `0.6`). Trị số càng thấp yêu cầu nhận diện càng khắt khe.
* **`liveness`**:
  * `enabled`: Bật/tắt chế độ chống giả mạo (`true`/`false`).
  * `final_score_threshold`: Ngưỡng đánh giá độ tin cậy khuôn mặt thật (mặc định `0.6`).
  * `weights`: Điều chỉnh tỷ trọng đóng góp của 5 bộ lọc heuristic (Texture, Color, Moiré, Reflection, Edge Density) vào điểm số cuối cùng.
