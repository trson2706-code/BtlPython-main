# Story 6.1: Module xuất Excel

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a giảng viên (teacher),
I want the system to automatically export attendance results to a professionally formatted Excel file after each session ends,
so that I have a permanent, portable record of student attendance with all session metadata for grading and reporting purposes.

## Acceptance Criteria

1. **File tạo mới**: `src/core/excel_export.py` chứa class `ExcelExporter` với method `export_session(session_result, class_info, teacher_info) → str` trả về đường dẫn file đã xuất.
2. **Tham số đầu vào**: Nhận `session_result` (dict từ `AttendanceSession.end_session()`), `class_info` (dict từ `DatabaseManager.get_class()`), `teacher_info` (dict từ `DatabaseManager.get_teacher()`). KHÔNG tự query database — Presenter cung cấp data.
3. **Format cột Excel**: STT | MSSV | Họ và tên | Trạng thái | Giờ điểm danh | Độ khớp (%). Cột STT auto-increment từ 1. Trạng thái: "Có mặt" hoặc "Vắng". Giờ điểm danh: format "HH:MM:SS" (rỗng nếu vắng). Độ khớp: format "XX.X%" (rỗng nếu vắng).
4. **Header metadata**: Dòng 1-5 hiển thị thông tin session: Ngày (DD/MM/YYYY), Môn học, Mã lớp, Giảng viên, Thời gian (HH:MM - HH:MM). Dòng 7 là header bảng (bold, background color).
5. **Tên file**: `YYYY-MM-DD_<class_code>.xlsx` — lưu vào `Config().get('paths', 'exports_dir')` (mặc định `data/exports`). Auto tạo thư mục nếu chưa tồn tại (`os.makedirs(exist_ok=True)`).
6. **Styling Excel**: Header metadata bold. Header bảng: font bold + background fill (#4472C4 xanh dương) + font trắng + border. Data rows: border mỏng + alignment center. Cột width tự auto-fit (minimum widths cho từng cột).
7. **Sắp xếp dữ liệu**: Tất cả sinh viên (present + absent) gộp chung, sắp xếp theo MSSV (student_code) tăng dần.
8. **Summary row**: Dòng cuối cùng sau data: "Tổng kết: Có mặt X/Y (Z%)" — bold, merge cells.
9. **Xử lý lỗi**: Raise `ValueError` với message tiếng Việt nếu `session_result` rỗng/None. Raise `OSError` nếu không thể ghi file. Log tất cả operations qua `logging.getLogger(__name__)`.
10. **Library**: Sử dụng `openpyxl` (>=3.1.5, đã có trong requirements.txt). KHÔNG thêm dependency mới.
11. **Xử lý edge cases**: Session không có sinh viên nào → xuất file với header + summary "Có mặt 0/0 (0%)". Tên file trùng → ghi đè (overwrite). `mark_time` là `datetime` object hoặc `None`. Nếu `class_info` hoặc `teacher_info` là `None` → dùng giá trị mặc định ("N/A" cho subject, class_code, teacher name) thay vì crash.
12. **Return value**: Trả về absolute path của file đã xuất thành công (string).

## Tasks / Subtasks

- [x] Tạo `src/core/excel_export.py` (AC: #1, #2, #3, #4, #5, #6, #7, #8, #9, #10, #11, #12)
  - [x] `import logging, os` + `from datetime import datetime` + `from openpyxl import Workbook` + styling imports
  - [x] `from src.core.config import Config`
  - [x] `logger = logging.getLogger(__name__)`
  - [x] Class `ExcelExporter` — stateless, có thể tạo instance mới mỗi lần
  - [x] `__init__(self)` — đọc `exports_dir` từ Config, `os.makedirs(exist_ok=True)`
  - [x] Method `export_session(self, session_result: dict, class_info: dict, teacher_info: dict) -> str`
  - [x] Validate input: `session_result` not None/empty — check `if not session_result` (catches both None and `{}`). Also validate required keys (`present`, `absent`, `start_time`, `class_id`) exist via `.get()` with defaults
  - [x] Tạo Workbook + active sheet, đặt title = "Điểm danh"
  - [x] Ghi header metadata (dòng 1-5): Ngày, Môn, Lớp, GV, Thời gian
  - [x] Ghi header bảng (dòng 7): STT, MSSV, Họ tên, Trạng thái, Giờ, % khớp — styling bold + fill + border
  - [x] Merge present + absent lists → sort by student_code → ghi data rows (dòng 8+)
  - [x] Format mark_time: `datetime.strftime('%H:%M:%S')` nếu not None, else `""`
  - [x] Format confidence: `f"{confidence * 100:.1f}%"` nếu > 0, else `""` — ⚠️ PHẢI nhân 100 (confidence lưu dạng decimal 0.0-1.0)
  - [x] Ghi summary row: merge A-F, bold, `f"Tổng kết: Có mặt {present_count}/{total_count} ({percent:.1f}%)"`  — guard division by zero: `percent = (present_count/total_count * 100) if total_count > 0 else 0`
  - [x] Set column widths (auto-fit minimum: STT=6, MSSV=15, Tên=25, TT=12, Giờ=15, %=12)
  - [x] Save workbook: wrap `wb.save(filepath)` trong `try-except OSError as e` → `logger.error(...)` + `raise OSError(f"Không thể ghi file Excel: {e}")`
  - [x] Return `os.path.abspath(filepath)` — đảm bảo trả về absolute path (AC#12)
  - [x] Helper `_apply_header_style(cell)` — bold font
  - [x] Helper `_apply_table_header_style(cell)` — bold + fill + white font + border
  - [x] Helper `_apply_data_style(cell)` — thin border + center alignment
  - [x] Helper `_apply_summary_style(cell)` — bold font

- [x] Viết tests `tests/test_excel_export.py` (AC: #1-#12)
  - [x] Fixture: tạo mock `session_result`, `class_info`, `teacher_info`
  - [x] Fixture: temp directory cho exports (dùng `tmp_path` pytest fixture)
  - [x] Fixture: patch `Config().get('paths', 'exports_dir')` → trả về `str(tmp_path / 'exports')` — ⚠️ Config là Singleton, PHẢI dùng `unittest.mock.patch.object` hoặc `monkeypatch` để override `exports_dir`
  - [x] Test 1: File được tạo đúng tên `YYYY-MM-DD_<class_code>.xlsx`
  - [x] Test 2: File được lưu đúng thư mục exports
  - [x] Test 3: Header metadata — dòng 1-5 chứa đúng thông tin
  - [x] Test 4: Header bảng — dòng 7 có đúng 6 cột
  - [x] Test 5: Data rows — sinh viên present có đúng trạng thái "Có mặt", giờ, % khớp
  - [x] Test 6: Data rows — sinh viên absent có đúng trạng thái "Vắng", giờ rỗng, % rỗng
  - [x] Test 7: Sắp xếp theo MSSV tăng dần
  - [x] Test 8: Summary row — "Tổng kết: Có mặt X/Y (Z%)"
  - [x] Test 9: Styling — header bảng có bold + fill
  - [x] Test 10: Edge case — session không có SV → file vẫn tạo với header + summary "0/0 (0%)"
  - [x] Test 11: Edge case — `session_result` None → ValueError
  - [x] Test 12: Edge case — present SV có `mark_time=None` → giờ hiển thị rỗng, `confidence=None`/`0.0` → % hiển thị rỗng (defensive)
  - [x] Test 13: Return value là absolute path (`os.path.isabs()`) + file tồn tại
  - [x] Test 14: Auto tạo thư mục exports nếu chưa có
  - [x] Test 15: Tên file trùng → ghi đè thành công (no error)
  - [x] Test 16: Vietnamese diacritics ("Nguyễn Thị Ái") → rendered correctly in Excel
  - [x] Test 17: `class_info` None → sử dụng defaults ("N/A"), không crash
  - [x] Test 18: `teacher_info` None → sử dụng defaults ("N/A"), không crash (AC#11)
  - [x] Test 19: `session_result` empty dict `{}` → raise ValueError (AC#9 "rỗng")
  - [x] Test 20: `wb.save()` raises `PermissionError` → re-raise as `OSError` (AC#9)
  - [x] Test 21: Confidence conversion — `confidence=0.85` → hiển thị "85.0%" (NOT "0.9%")

## Dev Notes

### Architecture Constraints (CRITICAL)

- **MVP Pattern**: `ExcelExporter` thuộc Model layer (`src/core/`). KHÔNG import từ `src/gui/`. KHÔNG tương tác trực tiếp với GUI.
- **Data Flow**: Presenter (story 6-2) sẽ subscribe `EXCEL_EXPORT_REQUESTED` event → query DB lấy `class_info`, `teacher_info` → gọi `exporter.export_session(result, class_info, teacher_info)`. Story này chỉ tạo module export, KHÔNG wire events.
- **Config Singleton**: Dùng `Config()` để đọc `paths.exports_dir`. Pattern giống `DatabaseManager.__init__()`.
- **Logging Pattern**: `logger = logging.getLogger(__name__)` — giống tất cả modules trong `src/core/`.
- **Error Pattern**: `raise ValueError(message_tieng_viet)` — giống `AttendanceSession`.

### Data Contracts (CRITICAL)

```python
# session_result — from AttendanceSession.end_session()
{
    'class_id': int,
    'start_time': datetime,        # datetime object
    'end_time': datetime,          # datetime object
    'present': [
        {
            'id': int,             # student_id
            'student_code': str,   # "2024001"
            'name': str,           # "Nguyễn Văn A"
            'is_present': True,
            'confidence': float,   # 0.0 - 1.0 (NOT percentage yet)
            'image_path': str | None,
            'mark_time': datetime | None,  # datetime object
        },
        ...
    ],
    'absent': [
        {
            'id': int,
            'student_code': str,
            'name': str,
            'is_present': False,
            'confidence': 0.0,
            'image_path': None,
            'mark_time': None,
        },
        ...
    ]
}

# class_info — from DatabaseManager.get_class(class_id)
{
    'id': int,
    'class_code': str,   # "CS101-01"
    'subject': str,      # "Lập trình Python"
    'teacher_id': int,
}

# teacher_info — from DatabaseManager.get_teacher(teacher_id)
{
    'id': int,
    'name': str,          # "TS. Nguyễn Văn X"
    'teacher_code': str,  # "GV001"
    'photo_path': str,
    'added_date': str,
}
```

### ⚠️ CRITICAL: confidence conversion

`AttendanceRecord.confidence` lưu dạng **decimal** (0.0 - 1.0), KHÔNG phải percentage. Khi xuất Excel, phải nhân 100: `confidence * 100` → hiển thị "XX.X%".

Kiểm chứng: `attendance_session.py` line 141 log `confidence` trực tiếp, và `recognition.py` trả về distance-based score 0-1. Story 5-2 `camera_session_panel` hiển thị `confidence` đã nhân 100 cho UI.

### Constructor Signature (Exact)

```python
# excel_export.py
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from src.core.config import Config

class ExcelExporter:
    def __init__(self):
        config = Config()
        self.exports_dir = config.get('paths', 'exports_dir', default='data/exports')
        os.makedirs(self.exports_dir, exist_ok=True)

    def export_session(self, session_result: dict, class_info: dict = None, teacher_info: dict = None) -> str:
        """Xuất kết quả điểm danh ra file Excel.

        Args:
            session_result: Dict từ AttendanceSession.end_session()
            class_info: Dict từ DatabaseManager.get_class() (None → dùng defaults)
            teacher_info: Dict từ DatabaseManager.get_teacher() (None → dùng defaults)

        Returns:
            str: Absolute path của file Excel đã tạo

        Raises:
            ValueError: Nếu session_result rỗng/None/empty dict
            OSError: Nếu không thể ghi file
        """
        # Validate input (F1+F2: catches None, {}, and missing keys)
        if not session_result:
            raise ValueError("Dữ liệu phiên điểm danh không hợp lệ (rỗng hoặc None).")
        
        # F2: Safe key access with defaults
        present_list = session_result.get('present', [])
        absent_list = session_result.get('absent', [])
        start_time = session_result.get('start_time', datetime.now())
        end_time = session_result.get('end_time', datetime.now())
        
        # AC#11: Null-safe defaults
        _class_info = class_info or {}
        _teacher_info = teacher_info or {}
        class_code = _class_info.get('class_code', 'N/A')
        subject = _class_info.get('subject', 'N/A')
        teacher_name = _teacher_info.get('name', 'N/A')
```

### Excel Layout (Exact)

```
Row 1: "Ngày:"          | "15/04/2026"
Row 2: "Môn học:"       | "Lập trình Python"
Row 3: "Mã lớp:"        | "CS101-01"
Row 4: "Giảng viên:"    | "TS. Nguyễn Văn X"
Row 5: "Thời gian:"     | "08:00 - 09:00"
Row 6: (empty)
Row 7: STT | MSSV | Họ và tên | Trạng thái | Giờ điểm danh | Độ khớp (%)
Row 8: 1   | 2024001 | Nguyễn Văn A | Có mặt   | 08:15:30 | 95.5%
Row 9: 2   | 2024002 | Trần Văn B   | Vắng     |          |
...
Row N+1: "Tổng kết: Có mặt 1/2 (50.0%)"  [merged A:F, bold]
```

### Openpyxl Styling Pattern (CRITICAL)

```python
# Header fill color
HEADER_FILL = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
HEADER_FONT = Font(bold=True, color="FFFFFF", size=11)
METADATA_FONT = Font(bold=True, size=11)
THIN_BORDER = Border(
    left=Side(style='thin'),
    right=Side(style='thin'),
    top=Side(style='thin'),
    bottom=Side(style='thin')
)
CENTER_ALIGN = Alignment(horizontal='center', vertical='center')

# Column widths (approximate)
COLUMN_WIDTHS = {'A': 6, 'B': 15, 'C': 25, 'D': 12, 'E': 15, 'F': 12}
```

### Anti-Pattern Prevention

| ❌ SAI | ✅ ĐÚNG |
|--------|---------|
| `from src.core.database import DatabaseManager` trong ExcelExporter | Nhận data qua parameters từ Presenter |
| `confidence` hiển thị trực tiếp (0.85) | `confidence * 100` → "85.0%" |
| `mark_time.strftime()` không check None | `mark_time.strftime('%H:%M:%S') if mark_time else ""` |
| Hardcode path `"data/exports"` | Dùng `Config().get('paths', 'exports_dir')` |
| `wb.save()` không wrap try-except | Wrap `OSError` + log |
| Sort present riêng, absent riêng | Merge cả hai → sort chung theo `student_code` |
| File name dùng `start_time` string | `start_time.strftime('%Y-%m-%d')` (datetime object) |
| Division by zero khi 0 students | Guard: `percent = (present/total * 100) if total > 0 else 0` |
| Import `pandas` hoặc `xlsxwriter` | Chỉ dùng `openpyxl` (đã có trong requirements.txt) |
| Tạo module-level instance | Tạo instance trong Presenter khi cần |

### Project Structure Notes

- **File tạo mới**: `src/core/excel_export.py`, `tests/test_excel_export.py`
- **Files KHÔNG sửa**: Không cần sửa file nào khác. EventType `EXCEL_EXPORT_REQUESTED` đã tồn tại (story 5-3). Wire event sẽ làm ở story 6-2.
- Đường dẫn export: `data/exports/` (đã define trong `config.yaml` → `paths.exports_dir`)
- Thư mục `data/exports/` sẽ tự tạo bởi `os.makedirs(exist_ok=True)` trong `ExcelExporter.__init__()`

### References

- [Source: src/core/attendance_session.py](file:///Users/huynguyen/work/projects/BtlPython/src/core/attendance_session.py) — `end_session()` return format (lines 156-186), `AttendanceRecord` TypedDict (lines 11-17)
- [Source: src/core/database.py](file:///Users/huynguyen/work/projects/BtlPython/src/core/database.py) — `get_class()` return format (line 231-240), `get_teacher()` return format (lines 112-121)
- [Source: src/core/config.py](file:///Users/huynguyen/work/projects/BtlPython/src/core/config.py) — Config Singleton pattern, `get('paths', 'exports_dir')` usage
- [Source: config.yaml](file:///Users/huynguyen/work/projects/BtlPython/config.yaml) — `paths.exports_dir: "data/exports"` (line 23)
- [Source: src/core/events.py](file:///Users/huynguyen/work/projects/BtlPython/src/core/events.py) — `EventType.EXCEL_EXPORT_REQUESTED` already exists (line 50)
- [Source: src/gui/student_panel.py](file:///Users/huynguyen/work/projects/BtlPython/src/gui/student_panel.py) — `_on_export_click()` emits `EXCEL_EXPORT_REQUESTED` (lines 260-263)
- [Source: sprint-status.yaml#E6-S1](file:///Users/huynguyen/work/projects/BtlPython/_bmad-output/implementation-artifacts/sprint-status.yaml) — Story requirements (lines 330-338)
- [Source: requirements.txt](file:///Users/huynguyen/work/projects/BtlPython/requirements.txt) — `openpyxl>=3.1.5`

### Previous Story Intelligence (5-3-attendance-student-panel)

**Learnings to apply:**
- `Config()` Singleton — dùng trực tiếp, không cần truyền config qua constructor
- Logging pattern: `logger = logging.getLogger(__name__)` ở đầu file
- Error messages bằng Tiếng Việt (raise ValueError)
- `os.makedirs(exist_ok=True)` — pattern từ `DatabaseManager.__init__()`
- `EXCEL_EXPORT_REQUESTED` event đã có — story 5-3 đã thêm vào `events.py`
- Data contract từ `AttendanceSession.end_session()` đã ổn định — dùng trực tiếp

### Technology Notes

- **openpyxl 3.1.5+**: Stable API. `Workbook()`, `ws.append()`, `ws.cell()`, `ws.merge_cells()`. Styling via `Font`, `PatternFill`, `Alignment`, `Border`, `Side`. `wb.save(filepath)` ghi file. KHÔNG cần `wb.close()` (auto khi save).
- **openpyxl merge_cells**: `ws.merge_cells('A{n}:F{n}')` — merge dòng summary. Ghi value vào cell đầu tiên của merge range.
- **openpyxl column_dimensions**: `ws.column_dimensions['A'].width = 6` — set width cho cột.
- **openpyxl UTF-8**: openpyxl lưu file dạng XML UTF-8 natively — Vietnamese diacritics (Nguyễn, Trần, etc.) hoạt động tự động. KHÔNG cần thêm encoding logic.

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (Thinking)

### Debug Log References

- Initial run: 3 test failures (filename path issue with `N/A`, openpyxl empty-string-to-None conversion)
- Fix: Sanitized `class_code` in filename (`/` → `-`), adjusted test assertions for openpyxl behavior
- Final run: 21/21 tests passed, 229/229 full regression passed

### Completion Notes List

- ✅ Created `src/core/excel_export.py` (183 lines) — `ExcelExporter` class with `export_session()` method
- ✅ Created `tests/test_excel_export.py` (300 lines) — 21 test cases covering all 12 ACs
- ✅ All styling applied: header metadata bold, table header with blue fill + white font + border, data rows with thin border + center alignment, summary row bold + merged
- ✅ Confidence conversion verified: 0.85 → "85.0%" (not "0.9%")
- ✅ Edge cases: None session_result, empty dict, None class_info/teacher_info, no students, mark_time=None, PermissionError → OSError
- ✅ Filename sanitization: `class_code` with `/` replaced by `-` to prevent path issues
- ✅ Vietnamese diacritics render correctly (openpyxl UTF-8 native)
- ✅ Zero regressions: 229 existing tests continue to pass

### File List

- [NEW] `src/core/excel_export.py`
- [NEW] `tests/test_excel_export.py`

### Change Log

- 2026-05-04: Implemented E6-S1 Excel Export module with 21-test suite. All ACs satisfied.
- 2026-05-04: Adversarial code review — 7 findings (1 HIGH, 2 MEDIUM, 4 LOW). Applied 5 fixes:
  - F1: Guard `start_time`/`end_time` None values via `or datetime.now()`
  - F2: `wb.close()` in `finally` block prevents memory leak on save failure
  - F3: Tests use `tempfile.mkdtemp()` instead of repo-relative dir
  - F4: Explicit `confidence is not None` check instead of truthiness
  - F5: Exception chain preserved with `raise ... from e`
  - Added 2 new tests (T22: start_time=None, T23: confidence=None). Suite: 23/23 passed.
- 2026-05-04: Party-mode multi-agent review — 12 findings (1 HIGH, 4 MEDIUM, 3 LOW, 4 INFO). Applied 7 fixes:
  - F1: `str()` cast in sort key prevents TypeError on None/int student_code
  - F2: `or []` guard for present/absent lists against explicit None values
  - F5: Filter None entries from student lists (defensive)
  - F8: LEFT_ALIGN for name column (col C) for better readability
  - F11: Warning log on validation failure
  - F12: Info log on export start
  - Added 2 new tests (T24: malformed student data, T25: None in student lists). Suite: 25/25 passed.
