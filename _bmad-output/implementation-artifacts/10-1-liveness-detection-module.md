# Story 10.1: Module Liveness Detection (Chống giả mạo khuôn mặt)

Status: done

## Story

Là quản trị viên hệ thống điểm danh,
Tôi muốn hệ thống có khả năng phát hiện khi ai đó dùng ảnh trên điện thoại/tablet/in giấy để giả mạo khuôn mặt,
Để ngăn chặn sinh viên/giảng viên gian lận điểm danh bằng photo spoofing.

## Acceptance Criteria

### AC1: Module `liveness.py` — Class `LivenessDetector`
- Tạo file `src/core/liveness.py`
- Class `LivenessDetector` với constructor đọc config từ `Config()` singleton (cùng pattern với `RecognitionWorker`, `CameraManager`)
- Constructor load tất cả thresholds + weights từ `Config().get('liveness', ...)`, có giá trị default hợp lý nếu config thiếu
- Nếu `Config()` chưa có section `liveness` → dùng toàn bộ defaults, KHÔNG raise exception

### AC2: Check Texture Quality (Laplacian Variance)
- Method `_check_texture_quality(self, face_roi: np.ndarray) -> float`
- Tính Laplacian variance của grayscale face ROI
- Ảnh thật: Laplacian variance cao (texture da, lông mày, mắt... phong phú) → score cao
- Ảnh màn hình/in giấy: Laplacian variance thấp hơn (mất chi tiết, mờ do chụp lại) → score thấp
- Normalize score về khoảng 0.0-1.0
- Implementation:
  ```python
  gray = cv2.cvtColor(face_roi, cv2.COLOR_RGB2GRAY)
  laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
  # Normalize: score = min(1.0, laplacian_var / texture_threshold)
  ```
- Default `texture_threshold`: 80.0 (ảnh có variance >= 80 được coi là sắc nét → score = 1.0)

### AC3: Check Color Distribution (YCrCb Histogram)
- Method `_check_color_distribution(self, face_roi: np.ndarray) -> float`
- Convert sang YCrCb color space
- Phân tích histogram kênh Cr và Cb — da người thật có phân bố đặc trưng trong vùng:
  - Cr: 133-173 (da tự nhiên)
  - Cb: 77-127 (da tự nhiên)
- Tính tỷ lệ pixel nằm trong vùng da tự nhiên / tổng pixel → gọi là `skin_ratio`
- Scoring formula:
  ```python
  skin_ratio = skin_pixels / total_pixels
  score = min(1.0, skin_ratio / color_threshold)
  ```
- `color_threshold` là ngưỡng kỳ vọng tối thiểu của skin_ratio cho khuôn mặt thật
- Ảnh thật: tỷ lệ cao → score cao (≥ 1.0 nếu ratio ≥ threshold)
- Ảnh màn hình: màu bị shift (backlight, color calibration khác) → tỷ lệ thấp → score thấp
- Default `color_threshold`: 0.4
- Return score 0.0-1.0

### AC4: Check Moiré Pattern (FFT Frequency Analysis)
- Method `_check_moire_pattern(self, face_roi: np.ndarray) -> float`
- Dùng FFT (Fast Fourier Transform) để phân tích tần số ảnh
- Màn hình điện thoại/tablet có pattern pixel lặp đi lặp lại → tạo peak ở tần số cao trong FFT
- **Phân vùng tần số** [CR-F11]: Sử dụng inner 1/3 trung tâm của magnitude spectrum làm low-freq region, phần bên ngoài là high-freq region. `high_freq_ratio = high_freq_energy / total_energy`
- Implementation:
  ```python
  gray = cv2.cvtColor(face_roi, cv2.COLOR_RGB2GRAY)
  f_transform = np.fft.fft2(gray)
  f_shift = np.fft.fftshift(f_transform)
  magnitude = np.abs(f_shift)
  rows, cols = magnitude.shape
  crow, ccol = rows // 2, cols // 2
  r = min(rows, cols) // 6  # inner 1/3 radius
  # Low-freq: magnitude[crow-r:crow+r, ccol-r:ccol+r]
  # High-freq: everything else
  total_energy = np.sum(magnitude)
  low_freq_energy = np.sum(magnitude[crow-r:crow+r, ccol-r:ccol+r])
  high_freq_energy = total_energy - low_freq_energy
  high_freq_ratio = high_freq_energy / total_energy if total_energy > 0 else 0.0
  ```
- Scoring formula:
  ```python
  # high_freq_ratio cao → khả năng có moiré → score thấp
  # high_freq_ratio thấp → ảnh thật → score cao
  score = max(0.0, 1.0 - (high_freq_ratio / moire_threshold))
  ```
- `moire_threshold` là ngưỡng high_freq_ratio mà khi đạt đến → score = 0.0 (chắc chắn moiré)
- Default `moire_threshold`: 0.3
- Return score 0.0-1.0

### AC5: Check Reflection (Specular Highlights)
- Method `_check_reflection(self, face_roi: np.ndarray) -> float`
- Phát hiện vùng sáng bất thường do phản chiếu ánh sáng trên mặt kính điện thoại
- Convert sang grayscale → threshold ở mức rất cao (>= 250) → tính tỷ lệ pixel "quá sáng"
- Implementation:
  ```python
  gray = cv2.cvtColor(face_roi, cv2.COLOR_RGB2GRAY)
  _, bright_mask = cv2.threshold(gray, 250, 255, cv2.THRESH_BINARY)
  bright_ratio = np.sum(bright_mask > 0) / bright_mask.size
  ```
- Scoring formula:
  ```python
  # bright_ratio cao → reflection → score thấp
  # bright_ratio thấp → ảnh thật → score cao
  score = max(0.0, 1.0 - (bright_ratio / reflection_threshold))
  ```
- `reflection_threshold` là ngưỡng bright_ratio mà khi đạt đến → score = 0.0 (chắc chắn có reflection)
- Default `reflection_threshold`: 0.5
- Return score 0.0-1.0

### AC6: Check Edge Density (Canny)
- Method `_check_edge_density(self, face_roi: np.ndarray) -> float`
- Dùng Canny edge detection → đếm tỷ lệ edge pixels
- Khuôn mặt thật: texture da phong phú, lông mày, tóc, nếp nhăn → edge density cao
- Ảnh từ màn hình/giấy: mất detail → edge density thấp
- Implementation:
  ```python
  gray = cv2.cvtColor(face_roi, cv2.COLOR_RGB2GRAY)
  edges = cv2.Canny(gray, 50, 150)
  edge_ratio = np.sum(edges > 0) / edges.size
  ```
- Scoring formula:
  ```python
  score = min(1.0, edge_ratio / edge_density_threshold)
  ```
- `edge_density_threshold` là ngưỡng edge_ratio kỳ vọng tối thiểu cho khuôn mặt thật
- Default `edge_density_threshold`: 0.15
- Return score 0.0-1.0

### AC7: Pipeline chính — `check_liveness()`
- Method `check_liveness(self, frame: np.ndarray, face_location: FaceDetectionResult) -> dict`
- Import: `from src.core.recognition import FaceDetectionResult` [CR-F1]
- Input: frame gốc (RGB, từ `CameraManager.get_frame()`) + `face_location` là `FaceDetectionResult` TypedDict (keys: `top`, `right`, `bottom`, `left` — xem `recognition.py` L11-15)
- Crop face ROI từ frame (với padding 10% mỗi phía để bắt được viền điện thoại). Clamp là best-effort — padding có thể không đều nếu face gần viền frame [CR-F4]
- Chạy lần lượt 5 checks (AC2-AC6)
- **Score sanitization** [CR-F9]: Sau mỗi check, validate `0.0 <= score <= 1.0`. Nếu score là NaN/Infinity/out-of-range → fallback 0.5
- Tính weighted average score = Σ(weight_i × score_i)
- **Weights validation** [CR-F3]: Constructor validate `abs(sum(weights) - 1.0) <= 0.01`. Nếu không pass → log WARNING + normalize weights (`w_i = w_i / sum(weights)`)
- Trọng số mặc định:
  ```yaml
  texture: 0.30    # Quan trọng nhất — phân biệt rõ ràng nhất
  color: 0.20      # Khá tốt cho màn hình backlit
  moire: 0.20      # Rất hiệu quả cho điện thoại/tablet
  reflection: 0.15 # Phụ trợ — phụ thuộc vào ánh sáng
  edge_density: 0.15  # Phụ trợ — tương tự texture nhưng khác thuật toán
  ```
- Return dict:
  ```python
  {
      'is_live': bool,           # True nếu score >= final_score_threshold
      'score': float,            # 0.0-1.0 weighted average
      'details': {               # Chi tiết từng check (debug)
          'texture': float,
          'color': float,
          'moire': float,
          'reflection': float,
          'edge_density': float,
      }
  }
  ```
- Default `final_score_threshold`: 0.6

### AC8: Guard cases
- `check_liveness()` với `frame=None` → return `{'is_live': False, 'score': 0.0, 'details': {}}`
- `check_liveness()` với `face_location=None` → return `{'is_live': False, 'score': 0.0, 'details': {}}`
- `check_liveness()` với face ROI quá nhỏ → return `{'is_live': False, 'score': 0.0, 'details': {}}`
  - **Định nghĩa "quá nhỏ"** [CR-F7]: `width < min_face_size OR height < min_face_size` (cả hai chiều đều phải ≥ threshold)
  - Bao gồm cả ROI 0×0 (top==bottom hoặc left==right) [CR-F8]
  - `min_face_size` đọc từ config, default = 30 [CR-F2]
- **Grayscale input guard** [CR-F6]: Mỗi check con kiểm tra `face_roi.ndim`. Nếu đã là grayscale (ndim==2) → skip `cvtColor`, dùng trực tiếp. Nếu ndim không hợp lệ → fallback score 0.5
- Mỗi check con xử lý exception riêng → nếu 1 check fail, các check khác vẫn chạy, check fail trả score 0.5 (neutral)
- Logging: log WARNING khi phát hiện spoof kèm score details

### AC9: Config integration
- `LivenessDetector` đọc config từ `Config()` singleton (KHÔNG nhận config dict parameter):
  ```yaml
  liveness:
    enabled: true
    min_face_size: 30          # [CR-F2] Configurable thay vì hard-code
    texture_threshold: 80.0
    color_threshold: 0.4
    moire_threshold: 0.3
    reflection_threshold: 0.5
    edge_density_threshold: 0.15
    final_score_threshold: 0.6
    weights:
      texture: 0.30
      color: 0.20
      moire: 0.20
      reflection: 0.15
      edge_density: 0.15
  ```
- Nếu `liveness.enabled = false` → `check_liveness()` luôn return `{'is_live': True, 'score': 1.0, 'details': {}}` (bypass)
- [CR-F5] Khi `enabled=false`, constructor log INFO **1 lần**: "Liveness detection disabled via config" (không log mỗi frame)

### AC10: Unit tests — ≥12 test cases (recommended: 15+) [CR-F15]
- Test 1: `LivenessDetector` khởi tạo với config mặc định
- Test 2: `LivenessDetector` khởi tạo với config custom (mock `Config()`)
- Test 3: `_check_texture_quality` — ảnh sắc nét → score cao
- Test 4: `_check_texture_quality` — ảnh mờ (gaussian blur) → score thấp
- Test 5: `_check_color_distribution` — ảnh da thường → score hợp lý
- Test 6: `_check_moire_pattern` — ảnh bình thường vs ảnh có pattern → phân biệt được
- Test 7: `_check_reflection` — ảnh không có glare vs ảnh có vùng sáng quá
- Test 8: `_check_edge_density` — ảnh chi tiết vs ảnh phẳng
- Test 9: `check_liveness()` — full pipeline với ảnh tổng hợp
- Test 10: `check_liveness()` — guard cases: None frame, None location, quá nhỏ, ROI 0×0 [CR-F8]
- Test 11: `liveness.enabled = false` → luôn return is_live=True, score=1.0
- Test 12: Exception trong 1 check → fallback score 0.5, pipeline vẫn chạy
- Test 13: [CR-F6] Grayscale input (2D array) → mỗi check xử lý gracefully
- Test 14: [CR-F3] Weights tổng ≠ 1.0 → auto-normalize + WARNING log
- Test 15: [CR-F9] Check trả NaN/Infinity → sanitize thành 0.5
- Baseline: tất cả test hiện có phải pass

## Tasks / Subtasks

- [x] Task 1 (AC: #1, #9): Tạo `src/core/liveness.py` — class skeleton + constructor
  - [x] Import cv2, numpy, logging, Config, FaceDetectionResult [CR-F1]
  - [x] Class `LivenessDetector` với constructor đọc `Config()` singleton
  - [x] Tất cả thresholds có default values (bao gồm `min_face_size: 30`) [CR-F2]
  - [x] Weights validation: normalize nếu tổng ≠ 1.0 [CR-F3]
  - [x] Log INFO khi `enabled=false` [CR-F5]
  - [x] Thêm section `liveness` vào `config.yaml`

- [x] Task 2 (AC: #2): Implement `_check_texture_quality()`
  - [x] Laplacian variance computation
  - [x] Normalize score 0.0-1.0 dùng `min(1.0, laplacian_var / texture_threshold)`

- [x] Task 3 (AC: #3): Implement `_check_color_distribution()`
  - [x] YCrCb conversion + histogram analysis
  - [x] Skin color range detection (Cr: 133-173, Cb: 77-127)
  - [x] Score = `min(1.0, skin_ratio / color_threshold)`

- [x] Task 4 (AC: #4): Implement `_check_moire_pattern()`
  - [x] FFT analysis với inner 1/3 trung tâm làm low-freq boundary [CR-F11]
  - [x] High-freq vs low-freq ratio
  - [x] Score = `max(0.0, 1.0 - (high_freq_ratio / moire_threshold))`

- [x] Task 5 (AC: #5): Implement `_check_reflection()`
  - [x] Specular highlight detection
  - [x] Bright pixel ratio
  - [x] Score = `max(0.0, 1.0 - (bright_ratio / reflection_threshold))`

- [x] Task 6 (AC: #6): Implement `_check_edge_density()`
  - [x] Canny edge detection
  - [x] Edge pixel ratio
  - [x] Score = `min(1.0, edge_ratio / edge_density_threshold)`

- [x] Task 7 (AC: #7, #8): Implement `check_liveness()` pipeline
  - [x] Face ROI cropping with 10% padding + clamp to frame bounds
  - [x] Run all 5 checks with individual try/except
  - [x] Grayscale input guard per check (ndim==2 → skip cvtColor) [CR-F6]
  - [x] Score sanitization: validate 0.0-1.0 range, NaN/Inf → 0.5 [CR-F9]
  - [x] Weighted average scoring
  - [x] Guard cases (None frame, None location, ROI 0×0, too small → consistent return dict) [CR-F7, CR-F8]

- [x] Task 8 (AC: #10): Unit tests
  - [x] Tạo `tests/test_liveness.py`
  - [x] ≥15 test cases (minimum 12, recommended 15+) [CR-F15] → 21 test cases
  - [x] Mock `Config()` singleton for custom config tests
  - [x] Tests for grayscale input, weights normalization, NaN sanitization [CR-F6, F3, F9]
  - [x] Verify 0 regressions trên TOÀN BỘ test files (34 pre-existing GUI failures, 0 new)

## Dev Notes

### Architecture Pattern (MVP)
- **Model**: `LivenessDetector` (`src/core/liveness.py`) — module mới, phụ thuộc `config.py` + import `FaceDetectionResult` type từ `recognition.py` [CR-F1]
- **View**: KHÔNG thay đổi trong story này (GUI integration ở Story 10.2)
- **Presenter**: KHÔNG thay đổi trong story này (wiring ở Story 10.2)
- **Thread-safety** [CR-F10]: `LivenessDetector` là stateless per `check_liveness()` call — thread-safe by design. Constructor đọc config 1 lần, không có mutable state

### Key Design Decisions
- **Pure OpenCV** — không thêm dependency mới (không cần tensorflow, pytorch, onnx)
- **Config() singleton** — cùng pattern với `RecognitionWorker` (worker.py L30-33), `CameraManager`
- **Weighted scoring** — linh hoạt hơn hard-threshold, cho phép tune từng check độc lập
- **Fail-open per check** — nếu 1 check lỗi, trả score 0.5 (neutral), pipeline vẫn chạy
- **Config-driven** — tất cả thresholds có thể tune qua config.yaml mà không cần sửa code

### ⚠️ Lưu ý về Face ROI
- `face_location` là `FaceDetectionResult` TypedDict (từ `recognition.py` L11-15) với keys `top`, `right`, `bottom`, `left`
- ROI crop: `face_roi = frame[top:bottom, left:right]`
- Frame format: RGB (đã convert bởi `CameraManager._update_frame()` dùng `cv2.COLOR_BGR2RGB`)
- Padding 10%: mở rộng ROI để bắt được viền điện thoại (nếu có)
- Clamp coordinates để không vượt quá frame bounds: `max(0, ...)`, `min(frame.shape[...], ...)`

### Performance
- Tất cả operations dùng OpenCV/NumPy optimized — ~10-20ms overhead per frame
- **Target** [CR-F16]: < 30ms trên ROI 200×200px. Measure thực tế bằng logging, tune nếu cần
- Chỉ chạy trên face ROI (nhỏ, ~100×100 px sau resize) — KHÔNG trên full frame
- **Lưu ý** [CR-F12]: Các thresholds mặc định được tune cho ROI ~100×100px trở lên. ROI nhỏ (30-50px) có thể cho kết quả không chính xác — giới hạn chấp nhận được cho MVP
- Worker thread đã throttle ở `scan_interval` (0.3s theo config.yaml) — thêm 10-20ms không đáng kể

### Skin Color Range Note [CR-F13]
- Cr: 133-173, Cb: 77-127 phù hợp nhiều tông da nhưng có thể miss tông da rất sáng/rất tối
- Range này là heuristic MVP — có thể chuyển thành config params trong tương lai nếu cần mở rộng

### Anti-Patterns to AVOID
- ❌ KHÔNG dùng deep learning model (giữ cho project nhẹ, không cần GPU)
- ❌ KHÔNG sửa `recognition.py`, `worker.py`, `main.py` trong story này — chỉ tạo module mới
- ❌ KHÔNG hard-code thresholds — tất cả phải đọc từ Config() singleton
- ❌ KHÔNG block khi 1 check fail — mỗi check phải try/except riêng
- ❌ KHÔNG modify frame gốc — chỉ đọc, KHÔNG ghi
- ❌ KHÔNG nhận config dict parameter trong constructor — dùng Config() singleton
- ❌ KHÔNG cần update `src/core/__init__.py` — project dùng full import path [CR-F14]

### References
- [Source: src/core/recognition.py#L11-L15] — FaceDetectionResult TypedDict (top, right, bottom, left)
- [Source: src/core/recognition.py#L24-L71] — detect_faces() flow
- [Source: src/core/worker.py#L104-L154] — Worker recognition loop (integration point cho Story 10.2)
- [Source: src/core/config.py] — Config singleton pattern
- [Source: config.yaml] — Config file format
- [Source: src/core/camera.py#L79] — Frame format: RGB (COLOR_BGR2RGB conversion)

---

## Dev Agent Record

### Agent Model Used
Claude Opus 4.6 (Thinking)

### Debug Log References
- Moiré test initially failed (0.0 not greater than 0.0) — block pattern also created sharp edges in FFT. Fixed by using smooth gradient image as "normal" baseline.
- System Python (3.9) does not have face_recognition — must use .venv Python 3.13 for tests.

### Completion Notes List
- ✅ Created `src/core/liveness.py` — LivenessDetector class with all 5 anti-spoofing checks
- ✅ All thresholds config-driven via Config() singleton with sensible defaults
- ✅ Weights validation with auto-normalize + WARNING log
- ✅ Guard cases: None frame, None location, ROI 0×0, ROI too small, 1D frame, non-array frame
- ✅ Grayscale input guard on all 5 checks (ndim==2 → skip cvtColor)
- ✅ Score sanitization: NaN/Inf/out-of-range → 0.5
- ✅ Each check wrapped in individual try/except (fail-open: score=0.5)
- ✅ Disabled mode bypass: return is_live=True, score=1.0
- ✅ Config.yaml updated with full liveness section
- ✅ 28 unit tests — all passing (21 original + 7 code review v5 additions)
- ✅ 0 new regressions (34 pre-existing GUI test failures unchanged)

### Change Log
- 2026-05-06 (v5): Party Mode (Solo) Code Review — 9 findings, 7 fixed (2 LOW no-change):
  - F1 [HIGH]: Added `_final_score_threshold` validation (> 0 and ≤ 1.0) — prevents security bypass
  - F3 [MEDIUM]: Config parsing wrapped in `_safe_float()` / `_safe_int()` — non-numeric values fallback to default + WARNING
  - F5 [HIGH]: Added `frame.ndim < 2` and `isinstance(frame, np.ndarray)` guards — prevents IndexError on 1D/non-array input
  - F6 [MEDIUM]: `final_score` clamped to [0.0, 1.0] before return — defensive output guarantee
  - F7 [MEDIUM]: Added documentation comment on ROI arithmetic safety (clamp already sufficient)
  - F2 [MEDIUM]: Added Test 21 — boundary test: score == threshold → is_live=True
  - F3-test: Added Test 22 — non-numeric config value ('abc') → fallback to default
  - F5-test: Added Test 23/23b — 1D array + non-array frame → safe return
  - F9 [MEDIUM]: Added Test 24 — partial weights config → auto-normalize
  - F1-test: Added Test 25/25b — final_score_threshold ≤ 0 and > 1.0 → revert to default
  - F4 [LOW]: Test DRY refactor deferred (no functional impact)
  - F8 [LOW]: Redundant float() cast kept (defensive coding)
- 2026-05-06 (v4): Code Review — 10 findings identified, all HIGH/MEDIUM fixed:
  - H1: Added Test 16 — grayscale 2D frame through full check_liveness() pipeline
  - H2: Test 16 also validates color check returns 0.5 neutral for grayscale in pipeline context
  - H3: Added threshold validation (> 0) in constructor — negative/zero values revert to defaults + WARNING log
  - M1: Added Test 17 — zero weights edge case (all weights = 0 → fallback to defaults)
  - M2: Added Test 18 — empty ROI after crop guard validation
  - M3: Changed FaceDetectionResult to TYPE_CHECKING import — avoids unnecessary face_recognition dependency at import time
  - M4: Added defensive copy comment for _DEFAULT_WEIGHTS (already using dict() copy)
  - L1: Refactored test_guard_cases with subTest() for individual failure identification
  - L2: Verified config.yaml already has trailing newline (non-issue)
  - L3: Added Test 20 — disabled mode INFO log verification [CR-F5]
  - Added Test 19 — negative threshold guard validation
- 2026-05-06 (v3): Implementation complete — all 8 tasks done:
  - Created src/core/liveness.py (290 lines) — full LivenessDetector implementation
  - Added liveness section to config.yaml with all thresholds + weights
  - Created tests/test_liveness.py with 16 test cases covering all ACs + CR findings
  - All 16 tests pass, 0 regressions
- 2026-05-06 (v2): Party Mode (Solo) code review — 16 findings remediated:
  - CR-F1: Added explicit import path `from src.core.recognition import FaceDetectionResult`
  - CR-F2: `min_face_size` moved from hard-coded 30 to config parameter
  - CR-F3: Weights validation — auto-normalize if sum ≠ 1.0, log WARNING
  - CR-F4: ROI clamp documented as best-effort (padding may be uneven near frame edges)
  - CR-F5: Added logging when liveness disabled (INFO, once at init)
  - CR-F6: Grayscale input guard — each check handles ndim==2 gracefully
  - CR-F7: ROI "too small" clarified: `width < min_face_size OR height < min_face_size`
  - CR-F8: ROI 0×0 (top==bottom, left==right) included in guard cases
  - CR-F9: Score sanitization — NaN/Infinity/out-of-range → fallback 0.5
  - CR-F10: Thread-safety confirmed — stateless per call, documented
  - CR-F11: FFT high/low freq boundary defined: inner 1/3 center = low-freq
  - CR-F12: Small ROI threshold accuracy limitation documented
  - CR-F13: Skin color range limitation documented, noted as tunable future config
  - CR-F14: Confirmed `__init__.py` does not need update
  - CR-F15: Test count updated to ≥12 minimum, recommended 15+, 3 new test cases added
  - CR-F16: Performance target added: < 30ms on 200×200px ROI
- 2026-05-06 (v1): Story validation — 10 findings identified and remediated:
  - F1: Constructor pattern unified to Config() singleton (was ambiguous: "nhận config dict" vs "đọc Config()")
  - F2: Added explicit scoring formulas for AC3 (color), AC4 (moiré), AC5 (reflection), AC6 (edge) — previously only AC2 had formula
  - F3: Guard case return dicts made consistent across all 3 cases (None frame, None location, too-small ROI)
  - F4: Added `face_location=None` guard case (was missing)
  - F5: Fixed worker.py line reference: L104-L146 → L104-L154
  - F6: Fixed recognition.py line reference: L11-L16 → L11-L15
  - F7: Updated AC7 signature to use `FaceDetectionResult` TypedDict (was plain `dict`)
  - F8: Added frame format note (RGB from CameraManager)
  - F9: Adjusted performance estimate: ~5-10ms → ~10-20ms (FFT adds overhead)
  - F10: Added 12th test case for exception fallback behavior
  - F11: Bypass return updated: added `score: 1.0` for liveness.enabled=false (was missing score)

### File List

| File | Action |
|------|--------|
| `src/core/liveness.py` | NEW → MODIFY — LivenessDetector class with 5 anti-spoofing checks (~430 lines) |
| `config.yaml` | MODIFY — Add `liveness` section with thresholds + weights |
| `tests/test_liveness.py` | NEW → MODIFY — 28 unit tests for LivenessDetector |

