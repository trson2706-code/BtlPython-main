# Lịch sử thảo luận — Hệ thống Điểm danh Sinh viên

> Ngày: 15/04/2026  
> Thành viên: Huynguyen + BMAD Agents (Mary, Winston, Amelia, John, Sally, Bob)

---

## 1. Lựa chọn đề tài ban đầu

**Đề bài gốc (Đề tài 15):**
> Tìm hiểu về Computer Vision: Ý nghĩa, các đặc điểm, cài đặt. Viết một chương trình Python có ứng dụng Computer Vision để tiến hành nhận diện khuôn mặt, hoặc phân biệt các đối tượng (hình ảnh) trong máy tính. Viết tài liệu mô tả chi tiết các bước tiến hành, từ tiền xử lý dữ liệu, cho đến dựng mô hình, hiển thị dữ liệu.

**Phân tích đề bài (Mary):**
- Đề yêu cầu 3 deliverable: phần lý thuyết CV, chương trình Python, tài liệu kỹ thuật
- Chữ "hoặc" cho phép chọn 1 trong 2: nhận diện khuôn mặt HOẶC phân loại đối tượng
- Đề nói "ứng dụng Computer Vision" chứ không bắt buộc dùng OpenCV cụ thể
- Chữ "dựng mô hình" gợi ý giảng viên muốn có bước xây dựng/huấn luyện model

---

## 2. Thư viện Computer Vision trên Python

**Câu hỏi:** Đã có sẵn thư viện CV trên Python chưa?

**Trả lời:** Có, rất nhiều và rất trưởng thành. Python là ngôn ngữ số 1 cho CV.

### Phân loại thư viện:

**Tầng 1 — Xử lý ảnh cơ bản (không cần AI/ML):**
- **OpenCV** (`opencv-python`): Xử lý ảnh, video, detect khuôn mặt bằng Haar Cascade — "dao đa năng" của CV
- **Pillow** (PIL): Load/save/resize/crop ảnh
- **scikit-image**: Thuật toán xử lý ảnh học thuật

**Tầng 2 — Machine Learning / Deep Learning:**
- **TensorFlow/Keras**: Train & dùng model deep learning (CNN, pre-trained)
- **PyTorch**: Phổ biến trong nghiên cứu
- **Ultralytics (YOLOv8)**: Object detection real-time

**Tầng 3 — Chuyên biệt:**
- **face_recognition**: Nhận diện khuôn mặt — API đơn giản, 3 dòng code
- **MediaPipe** (Google): Face/hand/pose detection — nhẹ, nhanh
- **dlib**: Face landmarks, face encoding

---

## 3. Có bắt buộc dùng thư viện hay tự train được?

**Trả lời:** Có 3 cấp độ:

| Cấp | Cách làm | Mô tả |
|-----|----------|-------|
| **1. Dùng model có sẵn** | Cài thư viện, gọi hàm | Đơn giản nhất |
| **2. Transfer learning** | Lấy model đã train, train thêm trên data mình | **Sweet spot cho bài tập lớn** |
| **3. Train từ đầu** | Tự xây CNN, tự chuẩn bị dataset | Cần GPU, thời gian, data lớn |

**Quyết định:** Dùng cấp 1 (model có sẵn trong face_recognition) vì đã đủ tốt.

---

## 4. So sánh face_recognition vs DeepFace

**Câu hỏi:** Cái nào tốt hơn?

| Tiêu chí | face_recognition + dlib | DeepFace |
|----------|------------------------|----------|
| **Dễ cài trên M1** | ⚠️ Cần compile dlib | ✅ pip install |
| **Tốc độ** | ✅ ~0.05s/mặt (15-20fps) | ❌ ~0.3-1s/mặt (1-3fps) |
| **Độ chính xác** | 99.38% (LFW) | 97-99% |
| **Real-time camera** | ✅ Mượt | ⚠️ Lag |
| **Ổn định runtime** | ✅ Rất ổn | ⚠️ Lỗi lặt vặt (TF warnings) |
| **Dung lượng** | ~300 MB | ~1 GB+ |
| **Chọn model** | 1 model duy nhất | 7+ backends |

**Quyết định:** Dùng **face_recognition + dlib** vì ổn định hơn, nhanh hơn, nhẹ hơn.

---

## 5. Cài đặt môi trường

### Thông tin máy:
- macOS Apple Silicon M1
- Python 3.13.12 (Miniconda)
- Xcode Command Line Tools: đã cài

### Quá trình cài đặt:
1. Tạo venv: `python3.13 -m venv .venv`
2. Cài dlib-bin: ✅ Thành công (`pip install dlib-bin`) — bản pre-compiled cho Python 3.13 + ARM64
3. Cài face-recognition: ✅ Thành công (mạng chậm, download 100MB model)
4. Cài opencv-python, customtkinter: ✅ Thành công

### Lỗi gặp phải và cách sửa:
- **Lỗi:** `ModuleNotFoundError: No module named 'pkg_resources'`
- **Nguyên nhân:** Python 3.13 loại bỏ `pkg_resources` khỏi standard library. Thư viện `face_recognition_models` vẫn dùng cách cũ.
- **Fix:** Patch file `.venv/lib/python3.13/site-packages/face_recognition_models/__init__.py` — thay `from pkg_resources import resource_filename` bằng `import os` + `os.path.join()`

### Kết quả test:
```
✅ OpenCV: 4.13.0
✅ face_recognition: OK
✅ CustomTkinter: 5.2.2
✅ NumPy: 2.4.4
✅ Pillow: 12.2.0
✅ face_locations() hoạt động
✅ face_encodings() hoạt động
✅ 4 model files đầy đủ (~126MB)
```

---

## 6. Chuyển đổi đề tài: Tội phạm → Điểm danh

### Ý tưởng ban đầu: Nhận diện khuôn mặt tội phạm
- Flow: Nhập ảnh tội phạm → camera quét → cảnh báo khi match
- **Vấn đề:** Liên quan nghiệp vụ công an quá nhiều, nhạy cảm pháp lý

### Quyết định chuyển sang: Hệ thống điểm danh sinh viên
- **Lý do:** Thực tế hơn, gần gũi, dễ demo, dùng được ngay tại trường
- **Core tech giữ nguyên 100%** — chỉ đổi business logic

---

## 7. Thiết kế hệ thống điểm danh

### 7.1 Thông tin ứng dụng
- **Tên:** Điểm danh sinh viên
- **Ngôn ngữ giao diện:** Tiếng Việt
- **Báo cáo:** File Word (.docx)
- **Ảnh sinh viên:** Tự chuẩn bị

### 7.2 Luồng hoạt động chính

```
SETUP (1 lần):
  Nhập TKB mẫu (Excel) → Đăng ký GV (ảnh + tên) → Đăng ký SV (ảnh + tên + MSSV + lớp)

BẮT ĐẦU BUỔI HỌC (MVP):
  GV mở app → Chọn lớp từ dropdown → Bấm "Bắt đầu điểm danh"
  → Hệ thống load SV lớp đó → Bắt đầu đếm ngược 1 tiếng

SINH VIÊN ĐIỂM DANH:
  SV quét mặt → Nhận diện → 🟢 "Trần Văn B - Đã có mặt" → Lưu DB
  → Hết 1 tiếng → SV chưa quét = VẮNG

XUẤT DỮ LIỆU:
  Bấm "Xuất Excel" bất cứ lúc nào → File Excel lưu vào data/exports/
```

### 7.3 Phân giai đoạn

**MVP (đủ nộp bài):**
- Chọn lớp từ dropdown
- Camera real-time + nhận diện SV
- Điểm danh + đếm ngược 1 tiếng
- Xuất Excel
- ~1000 dòng code

**V2 (nâng cấp nếu kịp):**
- GV quét mặt thay dropdown
- Tự tra TKB theo giờ
- Thống kê % đi học
- ~300-500 dòng thêm

---

## 8. Quyết định kiến trúc

### 8.1 Architecture Pattern: MVP (Model-View-Presenter)

| Layer | Folder | Vai trò |
|-------|--------|---------|
| **Model** | `src/core/` | Logic nghiệp vụ, DB, recognition — không biết GUI |
| **View** | `src/gui/` | Giao diện CustomTkinter — chỉ hiển thị |
| **Presenter** | `src/main.py` | Khởi tạo + kết nối Model ↔ View qua events |

**Tại sao MVP:**
- View "ngu" — GUI chỉ biết hiển thị
- Presenter điều phối = main.py kết nối events
- Khớp với event/callback đã chọn
- Dễ giải thích trong báo cáo

### 8.2 Giao tiếp giữa modules: Event/Callback

**Lý do chọn:** Nếu sửa GUI thì không phải sửa core logic — modules độc lập.

```python
# Ví dụ: worker nhận diện xong → phát event → GUI tự cập nhật
worker.on_match = None  # callback
# main.py kết nối:
worker.on_match = gui.show_attendance_result
```

### 8.3 Config: File config.yaml riêng
**Lý do:** Dễ sửa thông số (tolerance, fps, camera_id) mà không đụng code.

### 8.4 Threading
- **Main thread:** GUI (CustomTkinter mainloop) — hiển thị camera 30fps
- **Worker thread:** Nhận diện ngầm mỗi 0.5-1 giây — không block GUI
- **Giao tiếp:** Queue (thread-safe)

---

## 9. Database Schema (SQLite — 7 bảng)

| Bảng | Mô tả | Cột chính |
|------|--------|-----------|
| **teachers** | Giảng viên | id, name, teacher_code, photo_path |
| **classes** | Lớp học phần | id, class_code, subject, teacher_id (FK) |
| **students** | Sinh viên | id, name, student_code, photo_path |
| **class_students** | SV-Lớp (N:M) | class_id, student_id |
| **face_encodings** | Encoding mặt | id, person_type, person_id, encoding (BLOB 128d) |
| **sessions** | Buổi điểm danh | id, class_id, date, start_time, end_time, status |
| **attendance** | Chi tiết điểm danh | id, session_id, student_id, check_time, status, confidence |

**Quan hệ:** teachers →1:N→ classes →N:M→ students, classes →1:N→ sessions →1:N→ attendance

---

## 10. Thuật toán nhận diện khuôn mặt

### Cách face_recognition hoạt động:

```
Ảnh đầu vào
  → 1. HOG (Histogram of Oriented Gradients) → Detect vùng có mặt
  → 2. Face Landmark Detection → 68 điểm đặc trưng (mắt, mũi, miệng)
  → 3. Affine Transform → Căn chỉnh mặt thẳng
  → 4. Deep CNN (ResNet-29) → Encode thành vector 128 chiều
  → 5. Euclidean Distance → So sánh 2 vector
     < 0.6 → CÙNG NGƯỜI
     ≥ 0.6 → KHÁC NGƯỜI
```

### Thông số kỹ thuật:
- **Độ chính xác:** 99.38% trên LFW dataset (13,000 ảnh)
- **Model:** ResNet-29, train trên 3 triệu ảnh khuôn mặt
- **Output:** Vector 128 số thực (float64)
- **Tolerance:** 0.5-0.6 (có thể config)
- **Tốc độ:** ~0.05s/mặt trên CPU

### Điều kiện hoạt động tốt:
- Ánh sáng đủ, đều
- Khuôn mặt chính diện hoặc nghiêng <30°
- Khoảng cách 0.5m - 2m
- Không che mặt

### Ứng dụng thực tế cùng công nghệ:
- Hệ thống Skynet (Trung Quốc) — bắt tội phạm trong đám đông
- Sân bay quốc tế — kiểm tra hộ chiếu tự động
- Face ID (Apple) — mở khóa iPhone

---

## 11. GUI Design

- **Framework:** CustomTkinter 5.2.2
- **Theme:** Dark mode mặc định
- **Layout 4 panel:** Camera (trái trên), Session (phải trên), Điểm danh (trái dưới), Sinh viên (phải dưới)
- **Tính năng:** Bounding box xanh/đỏ, đếm ngược, thống kê %, xuất Excel

---

## 12. Tech Stack tổng hợp

| Thư viện | Version | Dung lượng | Vai trò |
|----------|---------|------------|---------|
| Python | 3.13.12 | — | Runtime |
| OpenCV | 4.13.0 | ~60 MB | Xử lý ảnh, camera |
| face_recognition | 1.3.0 | ~3 MB | Nhận diện khuôn mặt |
| dlib | 20.0.1 (via dlib-bin) | ~3 MB (pre-compiled) | Engine ML cho face_recognition |
| face_recognition_models | 0.3.0 | ~100 MB | Model files (4 files) |
| CustomTkinter | 5.2.2 | ~5 MB | GUI framework |
| NumPy | 2.4.4 | ~30 MB | Xử lý array/vector |
| Pillow | 12.2.0 | ~5 MB | Load/save ảnh |
| SQLite | (built-in) | — | Database |
| openpyxl | (cần cài) | ~5 MB | Xuất Excel |

---

## 13. Luồng hoạt động chính thức (cập nhật cuối cùng)

> Phần này cập nhật lại mục 7.2 — flow đã được hoàn thiện dựa trên thảo luận chi tiết.

### Flow trước đó (MVP ban đầu):
- GV **chọn lớp từ dropdown** → SV điểm danh

### Flow chính thức (đã thống nhất):
- GV **quét mặt** + **hệ thống tự tra TKB** → SV điểm danh

### Sơ đồ chi tiết:

```
APP MỞ LÊN → Camera bật → Trạng thái: CHỜ GIẢNG VIÊN

BƯỚC 1: GIẢNG VIÊN QUÉT MẶT
┌──────────────────────────────────────────────────┐
│  GV soi mặt vào camera                          │
│  → Hệ thống nhận diện ngầm (chạy background)    │
│  → Xác định: "Thầy Nguyễn Văn A"               │
│  → Tra thời khoá biểu theo giờ hiện tại:        │
│     ├── CÓ tiết (trong 30 phút tới)             │
│     │   → Hiện: "Thầy A - CNTT01 - Python"      │
│     │   → GV bấm [✅ XÁC NHẬN]                  │
│     │   → Chuyển sang bước 2                     │
│     ├── QUÁ SỚM (ngoài 30 phút)                 │
│     │   → ❌ "Chưa đến giờ dạy"                 │
│     └── KHÔNG CÓ TIẾT                           │
│         → ❌ "Hôm nay không có lịch dạy"        │
└──────────────────────────────────────────────────┘
   * GV phải bấm nút "Xác nhận" → mới chuyển bước
   * Không có chức năng đổi lớp khác

BƯỚC 2: SINH VIÊN ĐIỂM DANH (1 tiếng)
┌──────────────────────────────────────────────────┐
│  Hệ thống load encoding SV lớp CNTT01 vào RAM   │
│  Camera tiếp tục chạy                            │
│  Nhận diện ngầm mỗi 0.5-1 giây                  │
│  Xử lý 1 mặt / 1 thời điểm                     │
│                                                  │
│  SV soi mặt:                                    │
│  → Nhận diện thành công                         │
│  → Tự động chụp 1 ảnh (chạy ngầm)              │
│  → 🟢 "Trần Văn B - MSSV 2024001 - Có mặt"     │
│  → Lưu vào bộ nhớ tạm (chưa ghi Excel)         │
│                                                  │
│  Đồng hồ đếm ngược: 60:00 → 00:00              │
│  * Nút [📊 Xuất Excel] có thể bấm bất cứ lúc nào│
└────────────────────┬─────────────────────────────┘
                     │ Hết 1 tiếng HOẶC GV bấm "Kết thúc"

BƯỚC 3: KẾT THÚC SESSION
┌────────────────────▼─────────────────────────────┐
│  SV chưa quét mặt → đánh dấu VẮNG              │
│  Tự động xuất file Excel                         │
│  → Lưu vào data/exports/                        │
│  Giải phóng data SV khỏi RAM                    │
│  Quay về BƯỚC 1 (chờ GV quét lại)               │
└──────────────────────────────────────────────────┘
```

### Các quy tắc quan trọng:

| Quy tắc | Chi tiết |
|---------|---------|
| **Nhận diện** | Chạy ngầm (background thread), tự nhận diện + tự chụp 1 ảnh |
| **Xử lý mặt** | 1 mặt / 1 thời điểm (không xử lý nhiều mặt cùng lúc) |
| **Ảnh SV** | 1 ảnh duy nhất cho mỗi sinh viên trong database |
| **TKB check** | Cho phép GV quét trước 30 phút so với giờ dạy trong TKB |
| **Ngoài giờ** | Quá sớm hoặc không có tiết → báo lỗi, không cho điểm danh |
| **Xác nhận** | GV phải bấm nút "Xác nhận" sau khi hệ thống nhận diện xong |
| **Đổi lớp** | Không được phép — 1 session = 1 lớp, không chuyển đổi |
| **Điểm danh trùng** | Mỗi SV chỉ điểm danh 1 lần trong 1 session |
| **Thời lượng** | 1 tiếng kể từ khi GV xác nhận |
| **Kết thúc** | Hết giờ tự động HOẶC GV bấm "Kết thúc" |
| **Lưu trữ** | Kết quả lưu thẳng vào Excel (không lưu dài hạn trong DB) |
| **Sau session** | Xuất Excel → giải phóng RAM → quay về trạng thái chờ |

---

## 14. Database Schema (cập nhật — 6 bảng)

> Cập nhật: Bỏ bảng `sessions` và `attendance` vì kết quả điểm danh lưu thẳng vào Excel, không cần giữ trong DB. DB chỉ lưu **data cố định**.

| Bảng | Mô tả | Cột chính |
|------|--------|-----------|
| **teachers** | Giảng viên | id, name, teacher_code, photo_path, added_date |
| **classes** | Lớp học phần | id, class_code, subject, teacher_id (FK) |
| **students** | Sinh viên | id, name, student_code, photo_path, added_date |
| **class_students** | SV-Lớp (N:M) | class_id (FK), student_id (FK) |
| **face_encodings** | Encoding mặt | id, person_type ("teacher"/"student"), person_id, encoding (BLOB 128 float64) |
| **timetable** | Thời khoá biểu | id, class_id (FK), day_of_week, start_time, end_time |

### Quan hệ:
```
teachers ──1:N──→ classes ──N:M──→ students (qua class_students)
classes  ──1:N──→ timetable
```

### Dữ liệu runtime (KHÔNG lưu DB):
- Kết quả điểm danh → lưu trong RAM → xuất Excel khi kết thúc session
- Ảnh chụp tự động → lưu file trong data/detections/

---

## 15. Threading Model (cập nhật)

### Giải thích "scan ngầm":

Camera chạy 30 frame/giây, nhưng **không nhận diện mọi frame** — chỉ nhận diện 1-2 frame/giây để tiết kiệm CPU:

```
Camera:    ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓  (30 frames/giây)
Hiển thị:  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓  (tất cả 30 → mượt)
Nhận diện: ▓░░░░░░░░░░░░░░▓░░░░░░░░░░░░░░▓  (chỉ 2 frames → tiết kiệm)
```

### 2 threads:
- **Main thread (GUI):** Hiển thị camera mượt, xử lý click, cập nhật UI
- **Worker thread:** Mỗi 0.5-1 giây lấy 1 frame → detect → encode → so sánh → gửi kết quả cho GUI qua Queue

---

## 16. Thời khoá biểu

### Cách nhập:
- Dùng **file Excel mẫu** có sẵn dữ liệu demo
- App đọc file Excel → import vào bảng `timetable` trong SQLite
- File Excel do user tự làm (sau)

### Logic tra TKB:
```
GV quét mặt → biết teacher_id
→ Query: SELECT * FROM timetable 
         JOIN classes ON timetable.class_id = classes.id
         WHERE classes.teacher_id = ?
         AND timetable.day_of_week = ngày_hôm_nay
         AND timetable.start_time BETWEEN (giờ_hiện_tại - 30 phút) AND (giờ_hiện_tại + 30 phút)
→ Có kết quả → hiển thị lớp, chờ GV xác nhận
→ Không có → báo lỗi
```
