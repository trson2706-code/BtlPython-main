# Story 7.2: Chương 3-4: Kỹ thuật + Mô hình

Status: done

<!-- Validated: 2026-05-04 — create-story + validation checklist applied -->
<!-- V1-V8 findings remediated inline -->
<!-- Party-mode review #1: 13 findings (F1-F14) remediated inline -->
<!-- Party-mode review #2: 6 findings (F1-F5,F7) — weak assertions, missing tests, type hints — remediated -->

## Story

As a sinh viên nộp bài tập lớn (student submitting coursework),
I want the system to extend the existing Word report with Chapter 3 (Installation & Preprocessing) and Chapter 4 (Model Architecture — HOG, CNN ResNet-29, encoding 128d, Euclidean distance),
so that the deliverable `docs/bao_cao.docx` includes complete technical documentation covering environment setup, data preparation, and the face recognition pipeline.

## Acceptance Criteria

1. **File sửa**: `src/core/report_generator.py` — thêm `_add_chapter_3(doc)` và `_add_chapter_4(doc)`, gọi từ `generate()` SAU `_add_chapter_2()`. ⚠️ KHÔNG tạo file mới — extend module hiện có.
2. **Cấu trúc báo cáo (Chương 3 — Cài đặt & Tiền xử lý)**:
   - 3.1 Môi trường phát triển — macOS M1, Python 3.13.12 (Miniconda), venv, Xcode Command Line Tools, IDE
   - 3.2 Cài đặt thư viện — bảng 9 packages từ `requirements.txt` (opencv-python, face-recognition, dlib-bin, customtkinter, pillow, openpyxl, numpy, pyyaml, python-docx) + version + vai trò
   - 3.3 Xử lý lỗi Python 3.13 — patch `pkg_resources` trong `face_recognition_models` (§5 `lich-su-thao-luan.md`)
   - 3.4 Chuẩn bị dữ liệu — ảnh GV/SV (1 ảnh/người), cấu trúc thư mục `data/teachers/`, `data/students/`, yêu cầu ảnh (chính diện, ánh sáng đều, 0.5-2m)
   - 3.5 Cấu hình hệ thống — bảng **toàn bộ** thông số từ `config.yaml` (camera, recognition, session, paths) — tối thiểu 12 params
3. **Cấu trúc báo cáo (Chương 4 — Xây dựng mô hình nhận diện)**:
   - 4.1 Tổng quan pipeline nhận diện — 5 bước: HOG → Landmark → Affine → CNN → Distance (§10 `lich-su-thao-luan.md`)
   - 4.2 HOG (Histogram of Oriented Gradients) — giải thích thuật toán detect vùng có mặt, gradient calculation, cell/block, sliding window
   - 4.3 Face Landmark Detection — 68 điểm đặc trưng (mắt, mũi, miệng, viền mặt), vai trò căn chỉnh
   - 4.4 CNN ResNet-29 — kiến trúc mạng, 29 convolutional layers, train trên 3 triệu ảnh, output vector 128 chiều (float64), model ~100MB (face_recognition riêng)
   - 4.5 Encoding và so sánh khuôn mặt — Euclidean distance giữa 2 vector 128d, tolerance 0.5-0.6, công thức d = √Σ(ai-bi)², ngưỡng < 0.6 = cùng người
   - 4.6 Thông số kỹ thuật — bảng: độ chính xác 99.38% LFW, tốc độ 0.05s/mặt, tolerance configurable, model size ~300MB total (bao gồm dlib)
   - 4.7 Điều kiện hoạt động — ánh sáng, góc mặt, khoảng cách, không che mặt
4. **Định dạng Word**: Giữ nguyên format từ Chương 1-2 — Times New Roman 13pt body, 14pt H2, 16pt H1, 1.5 spacing, justify, page numbering. ⚠️ KHÔNG thay đổi `_setup_document()` hay `_add_cover_page()`.
5. **Nội dung**: Content là **STATIC** — hardcode trong code. ⚠️ KHÔNG đọc file runtime. Tham khảo `lich-su-thao-luan.md` §5 (cài đặt), §10 (thuật toán), `config.yaml`, `requirements.txt`, `sprint-status.yaml` khi **viết code**.
6. **Bảng biểu**: Dùng helper `_add_table()` hiện có. Tối thiểu 4 bảng: (1) thư viện cài đặt (9 rows), (2) config params (≥12 rows, bao gồm paths), (3) pipeline 5 bước, (4) thông số kỹ thuật.
7. **Test**: Mở rộng `tests/test_report_generator.py` — thêm tối thiểu 12 test cases mới cho Chương 3-4 (total ≥38). Dùng pattern từ test hiện có. ⚠️ Tests phải SCOPED — keyword search chỉ trong context chapter tương ứng.
8. **Backward compatible**: Chạy lại `generate()` phải tạo file chứa CẢ 4 chương (1-2-3-4). Tests cũ (26 tests) phải vẫn pass. Bảng từ Chương 1-2 phải vẫn tồn tại.
9. **Idempotent**: Chạy lại vẫn overwrite, content giống nhau.

## Tasks / Subtasks

- [x] Sửa `src/core/report_generator.py` — thêm Chapter 3-4 (AC: #1, #4, #5)
  - [x] Thêm `self._add_chapter_3(doc)` và `self._add_chapter_4(doc)` vào `generate()` sau `self._add_chapter_2(doc)`
  - [x] Implement `_add_chapter_3(doc)` — 5 sections (3.1-3.5) (AC: #2)
  - [x] Implement `_add_chapter_4(doc)` — 7 sections (4.1-4.7) (AC: #3)
  - [x] Sử dụng helpers hiện có: `_add_heading()`, `_add_body()`, `_add_table()`, `_format_paragraph()`, `_set_run_font()` (AC: #4, #6)
  - [x] Content hardcode — KHÔNG import thêm module nào (AC: #5)
  - [x] Docstring module-level: update mô tả thành "Chương 1-4" thay vì "Chương 1 & 2"

- [x] Mở rộng `tests/test_report_generator.py` (AC: #7, #8)
  - [x] Test 27: Chương 3 heading tồn tại
  - [x] Test 28: Chương 4 heading tồn tại
  - [x] Test 29: Section 3.2 — bảng thư viện cài đặt (≥9 rows data) + assert package names (opencv-python, face-recognition, dlib-bin)
  - [x] Test 30: Section 3.5 — bảng config params tồn tại (STRICT: phải tìm bảng có header "Tham số", KHÔNG fallback text)
  - [x] Test 31: Section 4.1 — text chứa "HOG" SCOPED sau heading "Chương 4" (tránh false positive từ Chương 1)
  - [x] Test 32: Section 4.4 — text chứa "ResNet" SCOPED sau heading "Chương 4"
  - [x] Test 33: Section 4.5 — text chứa "Euclidean" SCOPED sau heading "Chương 4"
  - [x] Test 34: Section 4.6 — bảng thông số kỹ thuật tồn tại
  - [x] Test 35: Backward compat — Chương 1, 2 headings + bảng từ Ch1-2 (library comparison, database schema) vẫn tồn tại
  - [x] Test 36: Total heading count ≥ 27 (4 H1 + 23 H2: Ch1=5, Ch2=6, Ch3=5, Ch4=7)
  - [x] Test 37: Bullet lists tồn tại trong Chương 3 (e.g., section 3.4 yêu cầu ảnh)
  - [x] Test 38: Config params bảng có ≥12 rows (bao gồm paths group)

- [x] Verify (AC: #8, #9)
  - [x] Chạy 26 tests cũ — tất cả pass
  - [x] Chạy 12 tests mới (27-38) — tất cả pass
  - [x] Chạy `python -m src.core.report_generator` — mở file verify 4 chương

## Dev Notes

### Architecture Constraints (CRITICAL)

- **EXTEND, không tạo mới**: Thêm 2 methods `_add_chapter_3()`, `_add_chapter_4()` vào class `ReportGenerator` hiện có. KHÔNG tạo file Python mới.
- **generate() orchestration**: Thêm 2 dòng gọi SAU `self._add_chapter_2(doc)`:
  ```python
  def generate(self):
      doc = Document()
      self._setup_document(doc)
      self._add_cover_page(doc)
      self._add_chapter_1(doc)
      self._add_chapter_2(doc)
      self._add_chapter_3(doc)  # ← THÊM
      self._add_chapter_4(doc)  # ← THÊM
      # ... save logic giữ nguyên
  ```
- **Helpers đã có**: Dùng `_add_heading(doc, text, level)`, `_add_body(doc, text)`, `_add_table(doc, headers, rows)`. KHÔNG tạo helper mới trừ khi thật sự cần.
- **Import**: KHÔNG thêm import mới — tất cả imports cần thiết đã có (docx, os, logging).

### Content Sources (CRITICAL)

| Nội dung | Source file | Section tham khảo |
|----------|------------|-------------------|
| Môi trường cài đặt | `docs/lich-su-thao-luan.md` | §5 (macOS M1, Python 3.13, venv, dlib-bin) |
| Patch pkg_resources | `docs/lich-su-thao-luan.md` | §5 (lỗi Python 3.13, cách fix) |
| Thuật toán nhận diện | `docs/lich-su-thao-luan.md` | §10 (HOG → Landmark → CNN → Euclidean) |
| Thư viện + version | `requirements.txt` | 9 packages với version constraints |
| Config thông số | `config.yaml` | camera, recognition, session, paths |
| Tech stack | `sprint-status.yaml` | technical_decisions.tech_stack |
| Điều kiện hoạt động | `docs/lich-su-thao-luan.md` | §10 (ánh sáng, góc, khoảng cách) |

### Chương 3 Content Guide

**3.1 Môi trường phát triển:**
- macOS Apple Silicon M1
- Python 3.13.12 (Miniconda), venv: `.venv`
- Xcode Command Line Tools (required for dlib compilation)
- IDE: VS Code / PyCharm
- ⚠️ Dùng `List Bullet` cho danh sách, `_add_body()` cho prose

**3.2 Cài đặt thư viện — bảng 9 packages:**

| Thư viện | Version | Vai trò |
|----------|---------|---------|
| opencv-python | ≥4.11.0 (installed 4.13.0) | Xử lý ảnh, camera |
| face-recognition | ≥1.3.0 | Nhận diện khuôn mặt |
| dlib-bin | ≥20.0.1 | ML engine (pre-compiled ARM64) |
| customtkinter | ≥5.2.2 | GUI framework |
| pillow | ≥11.1.0 (installed 12.2.0) | Load/save ảnh |
| openpyxl | ≥3.1.5 | Xuất Excel |
| numpy | ≥2.2.0 (installed 2.4.4) | Xử lý array/vector |
| pyyaml | ≥6.0.2 | Đọc config |
| python-docx | ≥1.1.0 | Tạo báo cáo Word |

**3.3 Xử lý lỗi Python 3.13:**
- Lỗi: `ModuleNotFoundError: No module named 'pkg_resources'` — Python 3.13 loại bỏ `pkg_resources`
- Fix: Patch `face_recognition_models/__init__.py` — thay `from pkg_resources import resource_filename` bằng `import os` + `os.path.join()`

**3.4 Chuẩn bị dữ liệu:**
- 1 ảnh/người (GV và SV)
- Thư mục: `data/teachers/`, `data/students/`
- Yêu cầu: chính diện hoặc nghiêng <30°, ánh sáng đều, 0.5-2m, không che mặt

**3.5 Cấu hình hệ thống — bảng TOÀN BỘ config.yaml (≥12 params):**

| Tham số | Giá trị | Mô tả |
|---------|---------|-------|
| camera_id | 0 | Webcam mặc định |
| resolution | 640×480 | Độ phân giải |
| fps | 30 | Tốc độ khung hình |
| tolerance | 0.55 | Ngưỡng nhận diện |
| scan_interval | 1s | Tần suất quét |
| model | hog | Thuật toán detect |
| teacher_check_window | 30 phút | Thời gian GV quét trước giờ |
| student_scan_time | 60 phút | Thời lượng điểm danh |
| db_path | data/attendance.db | Đường dẫn database |
| teachers_dir | data/teachers | Thư mục ảnh giảng viên |
| students_dir | data/students | Thư mục ảnh sinh viên |
| exports_dir | data/exports | Thư mục xuất Excel |

### Chương 4 Content Guide

**4.1 Pipeline tổng quan (5 bước):**
```
Ảnh → HOG detect → 68 landmarks → Affine transform → CNN ResNet-29 (128d vector) → Euclidean distance
```

**4.2 HOG:**
- Histogram of Oriented Gradients
- Tính gradient hướng cho mỗi pixel → chia thành cells → tạo histogram → sliding window detect vùng mặt
- Nhanh, chạy trên CPU, phù hợp real-time

**4.3 Face Landmark:**
- 68 điểm đặc trưng: 17 viền mặt, 10 mũi, 12 miệng, 12 mắt, 10 lông mày, 7 khác
- Dùng để căn chỉnh (affine transform) mặt về position chuẩn trước khi encode

**4.4 CNN ResNet-29:**
- 29 convolutional layers, train trên 3 triệu ảnh
- Output: vector 128 số thực (float64)
- Mỗi người có 1 "fingerprint" 128d duy nhất
- Model size: ~100MB (face_recognition model riêng, ~300MB total bao gồm dlib)
- ⚠️ Dùng `List Bullet` cho các items trên

**4.5 Euclidean Distance:**
- Công thức: d = √Σ(ai - bi)²
- d < 0.6 → CÙNG NGƯỜI
- d ≥ 0.6 → KHÁC NGƯỜI
- Tolerance có thể config (mặc định 0.55 trong project)

**4.6 Bảng thông số:**

| Thông số | Giá trị |
|----------|---------|
| Độ chính xác | 99.38% (LFW, 13,000 ảnh) |
| Tốc độ | ~0.05s/mặt (CPU) |
| Model | ResNet-29 |
| Training data | 3 triệu ảnh |
| Output | Vector 128 float64 |
| Tolerance | 0.5-0.6 (configurable) |
| Model size | ~300MB total |

**4.7 Điều kiện hoạt động:**
- Ánh sáng đủ, đều
- Khuôn mặt chính diện hoặc nghiêng <30°
- Khoảng cách 0.5m - 2m
- Không che mặt (khẩu trang, kính râm)

### Anti-Pattern Prevention

| ❌ SAI | ✅ ĐÚNG |
|--------|---------|
| Tạo file mới `report_generator_ch3.py` | Extend `report_generator.py` hiện có |
| Import thêm thư viện (matplotlib, diagrams) | Dùng bảng Word cho sơ đồ pipeline |
| Đọc `config.yaml` tại runtime để lấy params | Hardcode params trong code |
| Đọc `requirements.txt` tại runtime | Hardcode danh sách thư viện |
| Thay đổi `_setup_document()` hoặc `_add_cover_page()` | Chỉ thêm methods mới, không sửa cũ |
| Tạo methods helper mới không cần thiết | Dùng `_add_heading()`, `_add_body()`, `_add_table()` đã có |
| Sửa signature hoặc logic của methods cũ | Giữ nguyên 100% code Chương 1-2 |

### Testing Strategy

```python
# Pattern — thêm vào tests/test_report_generator.py SAU test 26
# ⚠️ CRITICAL: keyword tests MUST be scoped to Chapter context

# Helper: extract text after a specific chapter heading
def _text_after_heading(doc, chapter_keyword):
    """Return concatenated text of paragraphs after the chapter heading."""
    found = False
    texts = []
    for p in doc.paragraphs:
        if found and p.style.name == 'Heading 1' and chapter_keyword not in p.text:
            break  # Reached next chapter
        if chapter_keyword in p.text and p.style.name.startswith('Heading'):
            found = True
            continue
        if found:
            texts.append(p.text)
    return '\n'.join(texts)

# Test 27: Chương 3 heading
def test_chapter_3_heading(doc):
    headings = [p.text for p in doc.paragraphs if p.style.name.startswith('Heading')]
    assert any('Chương 3' in h for h in headings)

# Test 28: Chương 4 heading
def test_chapter_4_heading(doc):
    headings = [p.text for p in doc.paragraphs if p.style.name.startswith('Heading')]
    assert any('Chương 4' in h for h in headings)

# Test 29: Bảng thư viện cài đặt (≥9 rows + content validation)
def test_installation_packages_table(doc):
    for table in doc.tables:
        headers = [cell.text for cell in table.rows[0].cells]
        if 'Thư viện' in headers and 'Vai trò' in headers:
            assert len(table.rows) >= 10, f"Expected ≥10 rows, got {len(table.rows)}"
            # Validate specific package names exist
            all_cells = [table.rows[r].cells[0].text for r in range(1, len(table.rows))]
            for pkg in ['opencv-python', 'face-recognition', 'dlib-bin']:
                assert any(pkg in c for c in all_cells), f"Missing package: {pkg}"
            return
    pytest.fail("Bảng thư viện cài đặt không tìm thấy")

# Test 30: Bảng config params — STRICT table check, no text fallback
def test_config_params_table(doc):
    for table in doc.tables:
        headers = [cell.text for cell in table.rows[0].cells]
        if 'Tham số' in headers and 'Giá trị' in headers:
            return
    pytest.fail("Bảng config params không tìm thấy (cần header 'Tham số' + 'Giá trị')")

# Test 31: Pipeline text chứa HOG — SCOPED to Chapter 4
def test_chapter_4_hog_content(doc):
    ch4_text = _text_after_heading(doc, 'Chương 4')
    assert 'HOG' in ch4_text, "Chapter 4 missing HOG content"

# Test 32: ResNet content — SCOPED to Chapter 4
def test_chapter_4_resnet_content(doc):
    ch4_text = _text_after_heading(doc, 'Chương 4')
    assert 'ResNet' in ch4_text or '128' in ch4_text, "Chapter 4 missing ResNet/128d content"

# Test 33: Euclidean content — SCOPED to Chapter 4
def test_chapter_4_euclidean_content(doc):
    ch4_text = _text_after_heading(doc, 'Chương 4')
    assert 'Euclidean' in ch4_text or 'distance' in ch4_text.lower(), "Chapter 4 missing Euclidean content"

# Test 34: Bảng thông số kỹ thuật
def test_technical_specs_table(doc):
    for table in doc.tables:
        headers = [cell.text for cell in table.rows[0].cells]
        if 'Thông số' in headers and 'Giá trị' in headers:
            return
    pytest.fail("Bảng thông số kỹ thuật không tìm thấy")

# Test 35: Backward compat — headings + tables from Ch1-2
def test_backward_compat_full(doc):
    headings = [p.text for p in doc.paragraphs if p.style.name.startswith('Heading')]
    assert any('Chương 1' in h for h in headings)
    assert any('Chương 2' in h for h in headings)
    # Tables from Ch1-2 must still exist
    found_lib = found_db = False
    for table in doc.tables:
        headers = [cell.text for cell in table.rows[0].cells]
        if 'Thư viện' in headers and 'Version' in headers and 'Ưu điểm' in headers:
            found_lib = True
        if 'Bảng' in headers and 'Mô tả' in headers:
            found_db = True
    assert found_lib, "Library comparison table from Ch1 missing"
    assert found_db, "Database schema table from Ch2 missing"

# Test 36: Total heading count ≥ 27 (4 H1 + 23 H2)
def test_total_heading_count(doc):
    headings = [p for p in doc.paragraphs if p.style.name.startswith('Heading')]
    assert len(headings) >= 27, f"Expected ≥27 headings, got {len(headings)}"

# Test 37: Bullet lists exist in Chapter 3
def test_chapter_3_bullet_lists(doc):
    found_ch3 = False
    for p in doc.paragraphs:
        if 'Chương 3' in p.text and p.style.name.startswith('Heading'):
            found_ch3 = True
        if found_ch3 and 'Chương 4' in p.text and p.style.name.startswith('Heading'):
            break
        if found_ch3 and p.style.name == 'List Bullet':
            return
    pytest.fail("No bullet lists found in Chapter 3")

# Test 38: Config params table has ≥12 rows (including paths)
def test_config_params_count(doc):
    for table in doc.tables:
        headers = [cell.text for cell in table.rows[0].cells]
        if 'Tham số' in headers and 'Giá trị' in headers:
            assert len(table.rows) >= 13, \
                f"Config table needs ≥13 rows (1 header + 12 data), got {len(table.rows)}"
            return
    pytest.fail("Bảng config params không tìm thấy")
```

### Project Structure Notes

- **File sửa**: `src/core/report_generator.py` — thêm ~150-200 dòng (2 methods mới)
- **File sửa**: `tests/test_report_generator.py` — thêm ~100-120 dòng (12 tests mới + 1 helper)
- **Output**: `docs/bao_cao.docx` — giờ chứa 4 chương thay vì 2
- KHÔNG tạo file mới nào
- KHÔNG sửa `requirements.txt` (python-docx đã có)

### References

- [Source: docs/lich-su-thao-luan.md](file:///Users/huynguyen/work/projects/BtlPython/docs/lich-su-thao-luan.md) — §5 (cài đặt, patch Python 3.13), §10 (thuật toán HOG → CNN → Euclidean), §12 (tech stack)
- [Source: config.yaml](file:///Users/huynguyen/work/projects/BtlPython/config.yaml) — Camera, recognition, session parameters (hardcode vào Chương 3.5)
- [Source: requirements.txt](file:///Users/huynguyen/work/projects/BtlPython/requirements.txt) — 9 packages (hardcode vào Chương 3.2)
- [Source: sprint-status.yaml](file:///Users/huynguyen/work/projects/BtlPython/_bmad-output/implementation-artifacts/sprint-status.yaml) — tech stack, threading model
- [Source: 7-1-report-theory-analysis.md](file:///Users/huynguyen/work/projects/BtlPython/_bmad-output/implementation-artifacts/7-1-report-theory-analysis.md) — Previous story patterns, python-docx helpers, testing patterns
- [Lib: python-docx >=1.1.0](https://python-docx.readthedocs.io/) — API documentation

### Previous Story Intelligence (7-1-report-theory-analysis)

**Learnings to apply:**
- Dùng `_add_heading(doc, text, level)` cho tất cả headings — đã xử lý font color black + Times New Roman
- Dùng `_add_body(doc, text)` cho body paragraphs — đã xử lý format + run font
- Dùng `_add_table(doc, headers, rows)` cho bảng — đã xử lý header shading + run font
- Bullet lists: dùng `doc.add_paragraph(text, style='List Bullet')` + `_format_paragraph()` + `_set_run_font()` — ⚠️ PHẢI dùng cho danh sách items, `_add_body()` chỉ cho prose
- Module docstring mô tả scope — cần update "Chương 1 & 2" → "Chương 1-4"
- Test pattern: dùng `doc` fixture (đã load document), check `doc.paragraphs` cho headings, `doc.tables` cho bảng
- 26 tests pass — backward compatibility là MUST (bao gồm cả bảng, không chỉ headings)
- `_add_table()` có ragged row guard (`cols = min(len(row_data), len(headers))`)

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (Thinking)

### Debug Log References

- Test 29 initially failed: Ch1 library table (5 cols) matched before Ch3 table (3 cols). Fixed by adding `len(headers) == 3` filter to distinguish the tables.

### Completion Notes List

- ✅ Extended `report_generator.py` with `_add_chapter_3(doc)` (5 sections: 3.1-3.5) and `_add_chapter_4(doc)` (7 sections: 4.1-4.7)
- ✅ Module docstring updated: "Chương 1 & 2" → "Chương 1-4"
- ✅ `generate()` orchestrator updated: calls `_add_chapter_3(doc)` and `_add_chapter_4(doc)` after `_add_chapter_2(doc)`
- ✅ All content hardcoded — no new imports, no runtime file reads
- ✅ Used only existing helpers: `_add_heading()`, `_add_body()`, `_add_table()`, `_format_paragraph()`, `_set_run_font()`
- ✅ 4 tables added: (1) library installation 9 rows, (2) config params 12 rows, (3) pipeline 5 steps, (4) tech specs 7 rows
- ✅ Bullet lists used in Ch3 (env, data requirements) and Ch4 (landmarks, ResNet features, conditions)
- ✅ 12 new tests (27-38) added with `_text_after_heading()` helper for scoped keyword assertions
- ✅ All 38 tests pass (26 old + 12 new), 0 regressions
- ✅ Report generated: `docs/bao_cao.docx` contains all 4 chapters
- ✅ Sprint status updated: 7-2-report-technique-model → review

### Party-mode Review #2 (2026-05-04 15:55)

**6 findings remediated:**
- F1 — Hardcoded test count in docstring → made generic ("Ch1-4 theory, analysis, technique, model")
- F2 — Test 32 weak `or '128'` assertion → assert both ResNet AND 128 independently
- F3 — Test 33 weak `or 'distance'` assertion → assert Euclidean specifically
- F4 — Missing Ch4 section count test → added test_chapter_4_section_count (7 sections: 4.1-4.7)
- F5 — Missing formula content test → added test_euclidean_formula_content (√Σ notation)
- F7 — Inconsistent `-> None` type hints → added to `_add_chapter_1()` and `_add_chapter_2()`

**Test count: 43 → 45 (all pass, 0 regressions)**

### File List

- `src/core/report_generator.py` — Modified: added `_add_chapter_3()`, `_add_chapter_4()`, updated `generate()` and docstring (~240 lines added), `-> None` type hints standardized
- `tests/test_report_generator.py` — Modified: 45 tests total — strengthened assertions (tests 32-33), added tests 44-45 (Ch4 section count + Euclidean formula)
- `docs/bao_cao.docx` — Generated: now contains Chapters 1-4
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — Updated: E7-S2 status
- `_bmad-output/implementation-artifacts/7-2-report-technique-model.md` — Updated: tasks marked complete, status → done
