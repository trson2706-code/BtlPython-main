# Story 7.1: Chương 1-2: Lý thuyết + Phân tích

Status: done

<!-- Validated: 2026-05-04 — create-story + validation checklist applied -->
<!-- V1-V7 findings remediated inline -->
<!-- Party-mode review: F1-F13 findings remediated 2026-05-04 -->
<!-- Code review: 11 findings remediated 2026-05-04 — tests expanded 15→20 -->
<!-- Party-mode review #2: F1-F12 findings remediated 2026-05-04 — tests expanded 20→26 -->

## Story

As a sinh viên nộp bài tập lớn (student submitting coursework),
I want the system to auto-generate a professional Word report covering Chapter 1 (Computer Vision theory) and Chapter 2 (Problem analysis with flowcharts),
so that the deliverable `docs/bao_cao.docx` is complete, well-structured, and ready for submission without manual Word editing.

## Acceptance Criteria

1. **File tạo mới**: `src/core/report_generator.py` — module stateless, nhận data từ Presenter hoặc CLI, xuất file Word `.docx`.
2. **Thư viện**: Dùng `python-docx` (>=1.1.0) — cần thêm vào `requirements.txt`. ⚠️ **[F7-fix]**: version constraint `>=1.1.0` (linh hoạt, compatible with 1.1.x và 1.2.x).
3. **Entry point**: Có thể chạy standalone: `python -m src.core.report_generator` — tạo `docs/bao_cao.docx` trực tiếp mà không cần GUI hoặc camera.
4. **Cấu trúc báo cáo (Chương 1 — Tổng quan Computer Vision)**:
   - 1.1 Khái niệm Computer Vision — định nghĩa CV, mục tiêu, phân biệt với Image Processing
   - 1.2 Đặc điểm của Computer Vision — real-time processing, multi-modal input, tính ứng dụng cao
   - 1.3 Ứng dụng Computer Vision trong thực tế — nhận diện khuôn mặt (Face ID, Skynet), xe tự lái, y tế, giám sát an ninh
   - 1.4 Các thư viện Computer Vision trên Python — OpenCV, face_recognition, dlib, Pillow, TensorFlow/Keras, MediaPipe (bảng so sánh)
   - 1.5 Tại sao chọn face_recognition + dlib — so sánh với DeepFace (bảng), lý do chọn: tốc độ 0.05s/mặt, độ chính xác 99.38% LFW, nhẹ 300MB vs 1GB+
5. **Cấu trúc báo cáo (Chương 2 — Phân tích bài toán)**:
   - 2.1 Mô tả bài toán — đề tài 15, yêu cầu gốc, quyết định chọn hệ thống điểm danh
   - 2.2 Yêu cầu chức năng — nhận diện GV, tra TKB, điểm danh SV, xuất Excel, quản lý SV/GV/lớp
   - 2.3 Yêu cầu phi chức năng — real-time (30fps preview, 1-2fps recognition), 1 mặt/lúc, tolerance config, auto-capture
   - 2.4 Flowchart luồng hoạt động — sơ đồ 3 bước (Chờ GV → Điểm danh SV → Kết thúc), dùng bảng hoặc text diagram
   - 2.5 Kiến trúc hệ thống — MVP pattern, sơ đồ Model-View-Presenter, event/callback, threading model
   - 2.6 Database Schema — 6 bảng SQLite (theo §14 `lich-su-thao-luan.md`, KHÔNG dùng §9 cũ 7 bảng), sơ đồ quan hệ (bảng). ⚠️ **[F1-fix]**: Schema đã cập nhật bỏ `sessions` + `attendance` — chỉ còn: teachers, classes, students, class_students, face_encodings, timetable.
6. **Định dạng Word**:
   - Font: Times New Roman, cỡ 13pt cho body, 14pt bold cho heading 2, 16pt bold cho heading 1
   - Dãn dòng: 1.5 line spacing
   - Lề: top=2cm, bottom=2cm, left=3cm, right=2cm (chuẩn ĐATN Việt Nam)
   - Căn đều (Justify) cho body text
   - Đánh số trang — footer center
   - Heading có numbering: "Chương 1:", "1.1", "1.2", v.v.
7. **Bảng biểu**: Dùng `doc.add_table()` với style `Table Grid`, header row bold + background color nhạt.
8. **Hình ảnh flowchart**: Nếu không tạo được hình ảnh trực tiếp, dùng bảng text hoặc ký hiệu ASCII art trong Word (acceptable cho bài tập lớn). ⚠️ KHÔNG import matplotlib hay tạo PNG — giữ dependency nhẹ.
9. **Nội dung**: Content là **STATIC** — hardcode trực tiếp trong code Python. ⚠️ **[F4-fix]**: KHÔNG đọc file `lich-su-thao-luan.md` hay `sprint-status.yaml` tại runtime. Tham khảo các file này khi **viết code** để lấy ý, nhưng nội dung được viết thẳng vào các method `_add_chapter_1()`, `_add_chapter_2()` dưới dạng string literals.
10. **Output path**: `docs/bao_cao.docx` — tạo thư mục `docs/` nếu chưa tồn tại (os.makedirs).
11. **Encoding**: UTF-8 — python-docx hỗ trợ Unicode mặc định, tiếng Việt hiển thị OK.
12. **Idempotent**: Chạy lại sẽ **overwrite** file cũ (không append). Mỗi lần chạy tạo file mới hoàn chỉnh. ⚠️ **[F9-fix]**: Verify bằng cách chạy 2 lần, check file mtime thay đổi và content vẫn đúng.
13. **Test file**: `tests/test_report_generator.py` — tối thiểu 15 test cases, dùng `python-docx` đọc lại file `.docx` đã tạo để verify nội dung. ⚠️ **[F2-fix]**: Bao gồm edge cases, formatting ACs, và cover page.
14. **Trang bìa**: ⚠️ **[F3-fix]**: File báo cáo phải có trang bìa (cover page) với placeholder: tên trường, đề tài, GVHD, sinh viên thực hiện. Nội dung placeholder để user tự điền sau.

## Tasks / Subtasks

- [x] Thêm `python-docx` vào `requirements.txt` (AC: #2)
  - [x] Append `python-docx>=1.1.0` sau dòng `pyyaml>=6.0.2` (hiện có 8 packages, thêm thành 9) — ⚠️ **[F7-fix]**: dùng `>=1.1.0` không lock cứng version
  - [x] ⚠️ requirements.txt hiện CHƯA có python-docx — phải thêm mới

- [x] Tạo `src/core/report_generator.py` (AC: #1, #3, #14)
  - [x] Import: `from docx import Document`, `from docx.shared import Pt, Cm, RGBColor`, `from docx.enum.text import WD_ALIGN_PARAGRAPH`, `from docx.oxml.ns import qn`, `from docx.oxml import OxmlElement` ⚠️ **[F11-fix]**: thêm `OxmlElement` (cần cho page numbering + table shading). **[V7-fix]**: KHÔNG import `Inches` (không dùng) và `WD_ORIENT` (không cần landscape)
  - [x] Class `ReportGenerator` — stateless, methods nhận config dict
  - [x] `__init__(self, output_path='docs/bao_cao.docx')` — lưu output path, ⚠️ **[V4-fix]**: gọi `os.makedirs(os.path.dirname(output_path), exist_ok=True)` trong `generate()` TRƯỚC `doc.save()`
  - [x] `generate()` — orchestrator chính, gọi các private methods theo thứ tự, kết thúc bằng `doc.save(self.output_path)`
  - [x] `_setup_document(doc)` — font, margins, line spacing (⚠️ **[F8-fix]**: set 1.5 spacing cho CẢ Normal, Heading 1, Heading 2 styles), ⚠️ **[V2-fix]**: page numbering footer (AC#6)
  - [x] `_add_cover_page(doc)` — ⚠️ **[F3-fix]** AC#14: trang bìa với placeholder: tên trường = "TRƯỜNG ĐẠI HỌC ...", đề tài = "Đề tài 15: Tìm hiểu về Computer Vision", GVHD + SV name = placeholder text (user sẽ điền sau)
  - [x] `_add_chapter_1(doc)` — Tổng quan Computer Vision (AC#4). ⚠️ **[F4-fix]**: nội dung hardcode trong code, KHÔNG đọc file runtime
  - [x] `_add_chapter_2(doc)` — Phân tích bài toán (AC#5). ⚠️ **[F1-fix]**: dùng schema 6 bảng từ §14, KHÔNG dùng §9
  - [x] `_add_table(doc, headers, rows, style='Table Grid')` — helper tạo bảng có format (AC#7)
  - [x] `_format_paragraph(paragraph, font_size=13, bold=False, alignment=WD_ALIGN_PARAGRAPH.JUSTIFY)` — ⚠️ **[F6-fix]**: renamed from `_set_paragraph_format` để tránh nhầm với `_set_run_font`. Dùng cho paragraph-level formatting (alignment, spacing)
  - [x] `_set_run_font(run, name='Times New Roman', size=Pt(13), bold=False)` — ⚠️ **[F6-fix]**: dùng cho run-level formatting (font name, size, bold, East Asian font). Pattern từ Dev Notes.
  - [x] `if __name__ == '__main__':` block — ⚠️ **[F13-fix]**: `ReportGenerator().generate(); print('✅ Đã tạo docs/bao_cao.docx')`

- [x] Implement Chương 1 content (AC: #4, #9)
  - [x] Section 1.1: Khái niệm CV — 2-3 đoạn văn
  - [x] Section 1.2: Đặc điểm CV — bullet list hoặc bảng
  - [x] Section 1.3: Ứng dụng thực tế — 4-5 ví dụ + mô tả ngắn
  - [x] Section 1.4: Thư viện Python — bảng so sánh 6-8 thư viện (tên, version, vai trò, ưu/nhược)
  - [x] Section 1.5: So sánh face_recognition vs DeepFace — bảng 7 tiêu chí từ `lich-su-thao-luan.md` mục 4

- [x] Implement Chương 2 content (AC: #5, #9)
  - [x] Section 2.1: Mô tả bài toán — ⚠️ **[F12-fix]**: trích dẫn đề bài gốc §1 `lich-su-thao-luan.md` ("Đề tài 15: Tìm hiểu về Computer Vision...") + lý do chuyển sang điểm danh (§6)
  - [x] Section 2.2: Yêu cầu chức năng — 6-8 items dạng bullet
  - [x] Section 2.3: Yêu cầu phi chức năng — performance metrics, config constraints
  - [x] Section 2.4: Flowchart — bảng 3 bước (Chờ GV / Điểm danh SV / Kết thúc) với actions
  - [x] Section 2.5: Kiến trúc — MVP diagram (bảng 3 cột: Model/View/Presenter) + event/callback + threading
  - [x] Section 2.6: Database — ⚠️ **[F1-fix]**: bảng 6 rows (teachers, classes, students, class_students, face_encodings, timetable) — theo §14 `lich-su-thao-luan.md`, KHÔNG dùng §9 (7 bảng cũ, đã bỏ sessions/attendance)

- [x] Tạo `tests/test_report_generator.py` (AC: #13, #14) — ⚠️ **[F2-fix]**: 15 test cases minimum
  - [x] Test 1: generate tạo file `.docx` thành công (file exists + size > 0)
  - [x] Test 2: file chứa "Chương 1" heading (style = Heading 1)
  - [x] Test 3: file chứa "Chương 2" heading (style = Heading 1)
  - [x] Test 4: bảng so sánh thư viện có đúng số cột (≥3) và dòng (≥6)
  - [x] Test 5: bảng so sánh face_recognition vs DeepFace tồn tại (≥7 tiêu chí)
  - [x] Test 6: document margins đúng (left=3cm, right=2cm, top=2cm, bottom=2cm)
  - [x] Test 7: body text font size = 13pt (Normal style)
  - [x] Test 8: flowchart section tồn tại ("2.4" hoặc "Flowchart" trong headings)
  - [x] Test 9: database schema table có 6 rows data (không tính header)
  - [x] Test 10: file overwrite khi chạy lại — ⚠️ **[F9-fix]**: chạy generate() 2 lần, verify file tồn tại + mtime thay đổi
  - [x] Test 11: ⚠️ **[F5-fix]** trang bìa (cover page) chứa "Đề tài 15" và "TRƯỜNG ĐẠI HỌC"
  - [x] Test 12: ⚠️ **[F5-fix]** page numbering — footer paragraphs không rỗng (có PAGE field)
  - [x] Test 13: ⚠️ **[F5-fix]** line spacing = 1.5 (Normal style `paragraph_format.line_spacing`)
  - [x] Test 14: ⚠️ **[F5-fix]** heading font = Times New Roman (không phải Calibri mặc định)
  - [x] Test 15: ⚠️ **[F5-fix]** Vietnamese text rendering — verify "khuôn mặt", "điểm danh" có trong document text

## Dev Notes

### Architecture Constraints (CRITICAL)

- **MVP Pattern**: `src/core/report_generator.py` thuộc **Model layer** (`src/core/`). Nó KHÔNG import GUI modules. Nó chỉ đọc data từ file hoặc nhận dict từ caller.
- **Stateless**: `ReportGenerator` không giữ state giữa các lần gọi. Mỗi `generate()` tạo file mới từ đầu.
- **Standalone**: Module có `if __name__ == '__main__':` block → chạy trực tiếp `python -m src.core.report_generator` mà không cần khởi tạo DB, camera, hay GUI.
- **Không depend on runtime**: Nội dung chương 1-2 là **static content** (lý thuyết + phân tích). Không cần data từ DB hoặc session results (chương 5-6 mới cần).

### python-docx Patterns (CRITICAL)

```python
import os
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

doc = Document()

# ── Page setup — margins ──
for section in doc.sections:
    section.top_margin = Cm(2)
    section.bottom_margin = Cm(2)
    section.left_margin = Cm(3)
    section.right_margin = Cm(2)

# ── Default font — Normal style ──
style = doc.styles['Normal']
font = style.font
font.name = 'Times New Roman'
font.size = Pt(13)
# ⚠️ [V3-fix] Set East Asian font cho tiếng Việt
style.element.rPr.rFonts.set(qn('w:eastAsia'), 'Times New Roman')

# ⚠️ [F8-fix] Line spacing cho Normal style
para_format = style.paragraph_format
para_format.line_spacing = 1.5
para_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

# ── Heading styles — MUST override font ──
# ⚠️ [V3-fix] Heading 1, 2 dùng Calibri mặc định → PHẢI override
for level, size in [('Heading 1', Pt(16)), ('Heading 2', Pt(14))]:
    h_style = doc.styles[level]
    h_style.font.name = 'Times New Roman'
    h_style.font.size = size
    h_style.font.bold = True
    h_style.element.rPr.rFonts.set(qn('w:eastAsia'), 'Times New Roman')
    # ⚠️ [F8-fix] Heading cũng cần 1.5 line spacing
    h_style.paragraph_format.line_spacing = 1.5

# ── Paragraph formatting ──
para_format = style.paragraph_format
para_format.line_spacing = 1.5
para_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

# ── [V2-fix] Page numbering — footer center ──
for section in doc.sections:
    footer = section.footer
    footer.is_linked_to_previous = False
    p = footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run()
    fld_char_begin = OxmlElement('w:fldChar')
    fld_char_begin.set(qn('w:fldCharType'), 'begin')
    run._element.append(fld_char_begin)
    instr_text = OxmlElement('w:instrText')
    instr_text.set(qn('xml:space'), 'preserve')
    instr_text.text = ' PAGE '
    run._element.append(instr_text)
    fld_char_end = OxmlElement('w:fldChar')
    fld_char_end.set(qn('w:fldCharType'), 'end')
    run._element.append(fld_char_end)
    run.font.name = 'Times New Roman'
    run.font.size = Pt(12)

# ── Add heading ──
doc.add_heading('Chương 1: TỔNG QUAN VỀ COMPUTER VISION', level=1)
doc.add_heading('1.1 Khái niệm Computer Vision', level=2)

# ── Add paragraph ──
p = doc.add_paragraph('Nội dung...')

# ── Add table with header shading [V5-fix] ──
table = doc.add_table(rows=1, cols=3, style='Table Grid')
hdr_cells = table.rows[0].cells
for cell in hdr_cells:
    # Bold header text
    for paragraph in cell.paragraphs:
        for run in paragraph.runs:
            run.bold = True
    # Light gray background [V5-fix]
    shading = OxmlElement('w:shd')
    shading.set(qn('w:fill'), 'D9E2F3')  # Light blue-gray
    shading.set(qn('w:val'), 'clear')
    cell._element.get_or_add_tcPr().append(shading)

hdr_cells[0].text = 'Thư viện'
hdr_cells[1].text = 'Version'
hdr_cells[2].text = 'Vai trò'
row = table.add_row().cells
row[0].text = 'OpenCV'
row[1].text = '4.13.0'
row[2].text = 'Xử lý ảnh, camera'

# ── [V4-fix] Create output directory + save ──
os.makedirs(os.path.dirname('docs/bao_cao.docx'), exist_ok=True)
doc.save('docs/bao_cao.docx')
```

### ⚠️ python-docx Font Gotcha (CRITICAL)

python-docx yêu cầu set font cho **CẢ** style lẫn individual runs. Khi dùng `doc.add_paragraph()`, text được wrap trong Run objects. Set `style.font.name` ảnh hưởng toàn cục nhưng heading styles có font riêng.

**⚠️ [F6-fix] Hai helpers riêng biệt — KHÔNG NHẦM LẪN:**

| Helper | Level | Khi nào dùng |
|--------|-------|-------------|
| `_format_paragraph()` | Paragraph | Set alignment, spacing cho đoạn văn |
| `_set_run_font()` | Run | Set font name, size, bold cho text runs |

```python
def _format_paragraph(self, paragraph, alignment=WD_ALIGN_PARAGRAPH.JUSTIFY):
    """Format paragraph-level properties. Dùng cho body text paragraphs."""
    paragraph.paragraph_format.alignment = alignment
    paragraph.paragraph_format.line_spacing = 1.5

def _set_run_font(self, run, name='Times New Roman', size=Pt(13), bold=False):
    """Set font cho 1 Run object. Dùng cho cả body text lẫn table cells."""
    run.font.name = name
    run.font.size = size
    run.bold = bold
    # ⚠️ CRITICAL: Đặt East Asian font name — nếu thiếu, Word có thể fallback sang font khác cho tiếng Việt
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.get_or_add_rFonts()
    rFonts.set(qn('w:eastAsia'), name)
```

⚠️ Import `qn` ở đầu file: `from docx.oxml.ns import qn`
⚠️ Import `OxmlElement` cho page numbering + table shading: `from docx.oxml import OxmlElement`

### ⚠️ Table Header Shading Pattern [V5-fix]

```python
def _add_table(self, doc, headers, rows):
    """Tạo bảng với header bold + shading."""
    table = doc.add_table(rows=1, cols=len(headers), style='Table Grid')
    hdr_cells = table.rows[0].cells
    for i, header in enumerate(headers):
        hdr_cells[i].text = header
        # Bold + font
        for p in hdr_cells[i].paragraphs:
            for run in p.runs:
                self._set_run_font(run, bold=True)
        # Shading
        shading = OxmlElement('w:shd')
        shading.set(qn('w:fill'), 'D9E2F3')
        shading.set(qn('w:val'), 'clear')
        hdr_cells[i]._element.get_or_add_tcPr().append(shading)
    for row_data in rows:
        row_cells = table.add_row().cells
        for i, cell_text in enumerate(row_data):
            row_cells[i].text = str(cell_text)
            for p in row_cells[i].paragraphs:
                for run in p.runs:
                    self._set_run_font(run)
    return table
```

### Content Sources (CRITICAL)

| Nội dung | Source file | Section tham khảo |
|----------|------------|-------------------|
| Khái niệm CV | `docs/lich-su-thao-luan.md` | Mục 1 (đề bài gốc) |
| Thư viện Python | `docs/lich-su-thao-luan.md` | Mục 2 (3 tầng) |
| So sánh face_recognition vs DeepFace | `docs/lich-su-thao-luan.md` | Mục 4 (bảng 7 tiêu chí) |
| Cài đặt môi trường | `docs/lich-su-thao-luan.md` | Mục 5 |
| Chuyển đổi đề tài | `docs/lich-su-thao-luan.md` | Mục 6 |
| Thiết kế hệ thống | `docs/lich-su-thao-luan.md` | Mục 7, 8, 9 |
| Thuật toán nhận diện | `docs/lich-su-thao-luan.md` | Mục 10 |
| Database schema | `sprint-status.yaml` | database.tables |
| Flow hoạt động | `sprint-status.yaml` | flow section |
| Tech stack | `sprint-status.yaml` | technical_decisions.tech_stack |
| Config thông số | `config.yaml` | recognition, session, camera |

### Anti-Pattern Prevention

| ❌ SAI | ✅ ĐÚNG |
|--------|---------|
| Import `matplotlib` hoặc `Pillow` để tạo flowchart image | Dùng bảng Word hoặc text diagram |
| Đọc trực tiếp từ DB để lấy nội dung | Content là static — hardcode trong code hoặc đọc từ file text |
| Tạo file `.doc` (old format) | Tạo `.docx` (Open XML) qua python-docx |
| Gọi `doc.save()` nhiều lần trong quá trình generate | Gọi `doc.save()` 1 lần duy nhất cuối cùng |
| Dùng `doc.add_heading()` rồi không set font | Set font cho heading runs: `heading.runs[0].font.name = 'Times New Roman'` |
| Copy-paste toàn bộ nội dung từ `lich-su-thao-luan.md` nguyên bản | Viết lại nội dung theo phong cách báo cáo học thuật, trích dẫn ý chính |
| Tạo module phụ thuộc runtime (cần camera, DB, session) | Module standalone, import tối thiểu |
| Không set line spacing | `paragraph_format.line_spacing = 1.5` cho EVERY paragraph |
| Dùng default Calibri font | Force `Times New Roman` cho cả Normal, Heading 1, Heading 2 styles |
| Bỏ qua encoding tiếng Việt | python-docx dùng UTF-8 mặc định — OK, nhưng test verify tiếng Việt content |

### Project Structure Notes

- **File tạo mới**: `src/core/report_generator.py`, `tests/test_report_generator.py`
- **File sửa**: `requirements.txt` — thêm `python-docx>=1.1.0`
- **Output**: `docs/bao_cao.docx` — nằm trong `docs/` (đã có `docs/lich-su-thao-luan.md`)
- Alignment: `src/core/report_generator.py` nằm đúng trong `src/core/` (Model layer)
- KHÔNG tạo file nào trong `src/gui/`
- ⚠️ **[F10-fix]**: Khi implement xong, thêm `src/core/report_generator.py` vào `project_structure` trong `sprint-status.yaml`

### Testing Strategy

```python
# tests/test_report_generator.py
import os
import pytest
from docx import Document
from src.core.report_generator import ReportGenerator

@pytest.fixture
def report_path(tmp_path):
    """Tạo report trong thư mục tạm."""
    path = str(tmp_path / 'bao_cao.docx')
    gen = ReportGenerator(output_path=path)
    gen.generate()
    return path

def test_file_created(report_path):
    assert os.path.exists(report_path)

def test_chapter_1_heading(report_path):
    doc = Document(report_path)
    headings = [p.text for p in doc.paragraphs if p.style.name.startswith('Heading')]
    assert any('Chương 1' in h for h in headings)

def test_chapter_2_heading(report_path):
    doc = Document(report_path)
    headings = [p.text for p in doc.paragraphs if p.style.name.startswith('Heading')]
    assert any('Chương 2' in h for h in headings)
```

### References

- [Source: docs/lich-su-thao-luan.md](file:///Users/huynguyen/work/projects/BtlPython/docs/lich-su-thao-luan.md) — ⚠️ **[F12-fix]**: §1 (đề bài gốc Đề tài 15), §4 (so sánh face_recognition vs DeepFace), §6 (chuyển đề tài), §14 (schema 6 bảng — DÙNG CÁI NÀY, KHÔNG DÙNG §9)
- [Source: sprint-status.yaml](file:///Users/huynguyen/work/projects/BtlPython/_bmad-output/implementation-artifacts/sprint-status.yaml) — Database schema (lines 111-124), flow (lines 82-106), tech stack (lines 37-44). ⚠️ **[F4-fix]**: Chỉ tham khảo khi viết code, KHÔNG đọc tại runtime
- [Source: config.yaml](file:///Users/huynguyen/work/projects/BtlPython/config.yaml) — Camera, recognition, session parameters. ⚠️ **[F4-fix]**: Tham khảo để hardcode thông số, KHÔNG đọc tại runtime
- [Source: 6-2-integration-main.md](file:///Users/huynguyen/work/projects/BtlPython/_bmad-output/implementation-artifacts/6-2-integration-main.md) — Previous story patterns: logging, Config singleton, testing
- [Lib: python-docx >=1.1.0](https://python-docx.readthedocs.io/) — API documentation ⚠️ **[F7-fix]**: updated version reference
- [Lib: python-docx PyPI](https://pypi.org/project/python-docx/) — Latest version info

### Previous Story Intelligence (6-2-integration-main)

**Learnings to apply:**
- `Config()` Singleton — dùng trực tiếp nếu cần đọc config (story này KHÔNG cần Config — content static)
- Logging pattern: `logger = logging.getLogger(__name__)` ở đầu file
- Error messages bằng Tiếng Việt
- Testing pattern: dùng `pytest` + fixtures, mock khi cần thiết
- Entry point: ⚠️ **[F13-fix]**: `if __name__ == '__main__': ReportGenerator().generate(); print('✅ Đã tạo docs/bao_cao.docx')`
- File mới PHẢI có docstring module-level

### Technology Notes

- **python-docx 1.2.0**: Stable, widely used. Supports paragraphs, headings, tables, images, styles. No external dependencies beyond `lxml` and `typing_extensions`.
- **Heading styles**: python-docx có built-in styles `Heading 1`, `Heading 2`, etc. Có thể customize font/size sau khi add.
- **Table styles**: `Table Grid` là style cơ bản nhất, có borders. Có thể thêm shading cho header row bằng `cell._element` XML manipulation.
- **Line spacing**: Set via `paragraph_format.line_spacing = 1.5` (float) hoặc `paragraph_format.line_spacing_rule = WD_LINE_SPACING.MULTIPLE`.
- **Vietnamese text**: python-docx handles UTF-8 natively. No special encoding needed. Test by verifying `'Chương'`, `'điểm danh'`, `'khuôn mặt'` in output.

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (Thinking)

### Debug Log References

### Completion Notes List

- ✅ Added `python-docx>=1.1.0` to requirements.txt (installed v1.2.0)
- ✅ Created `src/core/report_generator.py` — stateless ReportGenerator class
- ✅ Cover page with placeholders (TRƯỜNG ĐẠI HỌC, Đề tài 15, GVHD, SV)
- ✅ Chapter 1: 5 sections (1.1-1.5) with 2 comparison tables
- ✅ Chapter 2: 6 sections (2.1-2.6) with 4 tables (NFR, flowchart, MVP, DB schema)
- ✅ Database schema uses 6-table layout from §14 (NOT §9 7-table)
- ✅ All content hardcoded — no runtime file reads
- ✅ Word formatting: Times New Roman, 13pt body, 1.5 spacing, page numbering
- ✅ Standalone entry point: `python -m src.core.report_generator`
- ✅ Party-mode review #2: F1 ragged row guard, F2 heading black color on runs, F3 None path guard, F7 bullet spacing, F11 logging
- ✅ 26/26 tests pass, 290/290 full regression pass

### File List

- `requirements.txt` — added python-docx>=1.1.0
- `src/core/report_generator.py` — Word report generator module (hardened)
- `tests/test_report_generator.py` — 26 test cases
- `docs/bao_cao.docx` — OUTPUT: generated Word report
