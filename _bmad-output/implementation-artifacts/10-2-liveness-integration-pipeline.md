# Story 10.2: Tích hợp Anti-Spoofing vào Pipeline + GUI Feedback

Status: done

## Story

Là quản trị viên hệ thống điểm danh,
Tôi muốn module liveness detection (Story 10.1) được tích hợp vào luồng nhận diện khuôn mặt và hiển thị cảnh báo rõ ràng trên giao diện,
Để sinh viên/giảng viên biết khi hệ thống phát hiện ảnh giả và ngăn chặn việc điểm danh gian lận.

## Dependencies
- **Story 10.1** — `src/core/liveness.py` (`LivenessDetector`) đã hoàn thành (status: done)
- **Story 10.1** đã thêm section `liveness` vào `config.yaml` → AC4 chỉ cần VERIFY, KHÔNG tạo mới

## Acceptance Criteria

### AC1: Event Type mới — `SPOOF_DETECTED`
- Thêm `SPOOF_DETECTED = "spoof_detected"` vào `EventType` class trong `src/core/events.py` (L38-53)
- Thêm ngay sau `FACE_UNRECOGNIZED` (L53)

### AC2: Worker Integration — Liveness check trong recognition loop
- Sửa `RecognitionWorker.__init__()` (`src/core/worker.py` L14-42):
  - Import `LivenessDetector` LAZY trong `__init__()` body (chỉ import khi `liveness.enabled=true` — tránh import overhead khi disabled)
  - Trong `__init__()`, khởi tạo `self.liveness_detector`:
    ```python
    # Liveness detection (Story 10.2)
    liveness_enabled = config.get('liveness', 'enabled', default=False)
    if liveness_enabled:
        from src.core.liveness import LivenessDetector
        self.liveness_detector = LivenessDetector()
    else:
        self.liveness_detector = None
    ```
  - ⚠️ Import TRONG `__init__` body (lazy) — tránh import `face_recognition` transitive dependency khi disabled
  - ⚠️ `LivenessDetector()` constructor đọc `Config()` singleton — KHÔNG truyền config dict
- Sửa recognition loop (`run()` L104-154) — thêm liveness check SAU `if location:` (L113) và TRƯỚC `encoding = encode_face()` (L114):
  ```python
  location = detect_faces(frame)

  if location:
      # ★ Story 10.2: Anti-spoofing check TRƯỚC encoding
      if self.liveness_detector is not None:
          liveness = self.liveness_detector.check_liveness(frame, location)
          if not liveness['is_live']:
              events.emit(EventType.SPOOF_DETECTED, {
                  'coordinates': location,
                  'liveness_score': liveness['score'],
                  'details': liveness['details'],
              })
              # Throttle: wait scan_interval trước khi scan tiếp
              if self.stop_event.wait(timeout=self.scan_interval):
                  break
              continue  # Skip encoding — ảnh giả

      encoding = encode_face(frame, location)
      ...
  ```
- ⚠️ `continue` sau emit → KHÔNG gọi `encode_face()`, `find_best_match()`, hay emit `STUDENT_DETECTED`/`TEACHER_DETECTED` khi phát hiện spoof
- ⚠️ `check_liveness()` nhận `FaceDetectionResult` TypedDict (keys: `top`, `right`, `bottom`, `left`) — cùng format với `location` từ `detect_faces()`
- ⚠️ Throttle pattern: dùng `self.stop_event.wait(timeout=self.scan_interval)` — giống pattern ở L152-153, tránh liên tục emit SPOOF_DETECTED

### AC3: Presenter handler — `_on_spoof_detected()`
- Thêm `_on_spoof_detected(self, data)` vào `Presenter` (`src/main.py`)
- Subscribe trong `_setup_events()` (L78-90):
  ```python
  events.subscribe(EventType.SPOOF_DETECTED, self._on_spoof_detected)
  ```
- Handler implementation — đặt trong section `SHUTDOWN + ERROR + CAMERA_STOPPED` (gần `_on_face_unrecognized()` L435-447):
  ```python
  def _on_spoof_detected(self, data):
      """Handler cho SPOOF_DETECTED — hiển thị cảnh báo spoof trên GUI."""
      # Mode guard: bỏ qua nếu idle (không đang nhận diện)
      if self._current_mode is None:
          return
      coords = data.get('coordinates')
      score = data.get('liveness_score', 0.0)
      logger.warning(f"Phát hiện ảnh giả (score={score:.2f}): {data.get('details')}")
      if coords:
          self.app.after(0, self.app.camera_panel.set_bounding_box, coords, 'red')
          self.app.after(2000, self.app.camera_panel.clear_bounding_box)
      self.app.after(
          0, lambda: self.app.session_panel.info_label.configure(
              text="⚠️ Phát hiện ảnh giả — Vui lòng dùng khuôn mặt thật"
          )
      )
  ```
- Pattern giống hệt `_on_face_unrecognized()` (L435-447):
  - Mode guard: `if self._current_mode is None: return`
  - Bounding box đỏ 2 giây: `set_bounding_box(coords, 'red')` + `clear_bounding_box` after 2000ms
  - Text trên `session_panel.info_label.configure(text=...)`
  - Text sẽ bị overwrite bởi detection tiếp theo (không cần clear timer riêng)

### AC4: Config — VERIFY ONLY
- Config `liveness` section đã được thêm bởi Story 10.1 tại `config.yaml` L28-42
- **KHÔNG sửa config.yaml** — chỉ verify section tồn tại
- Nếu section thiếu (edge case) → `LivenessDetector()` dùng defaults (Story 10.1 AC9 đã handle)

### AC5: Toggle on/off
- Khi `liveness.enabled = false` trong `config.yaml`:
  - Worker `__init__()`: `self.liveness_detector = None` (không import `LivenessDetector`)
  - Recognition loop: `if self.liveness_detector is not None:` → skip toàn bộ liveness block
  - Zero import overhead, zero runtime overhead
- Khi `liveness.enabled = true`:
  - Worker import + khởi tạo `LivenessDetector()`
  - Recognition loop thực hiện `check_liveness()` trên mỗi frame có mặt
  - Overhead: ~10-20ms per frame (trên worker thread — KHÔNG block GUI)

### AC6: Unit tests — ≥9 test cases (5 yêu cầu + 4 edge/regression cases)
- **File**: `tests/test_worker.py` cho Worker integration (5 tests) + `tests/test_main.py` cho Presenter (4 tests)

#### Worker tests (thêm vào `tests/test_worker.py`):
- **Test W1**: Worker `__init__` với `liveness.enabled=true` → `self.liveness_detector is not None`
- **Test W2**: Worker `__init__` với `liveness.enabled=false` → `self.liveness_detector is None`
- **Test W3**: Spoof detected → `SPOOF_DETECTED` emitted, `encode_face()` NOT called
- **Test W4**: Live face (positive path) → `encode_face()` IS called, normal flow continues
- **Test W5**: Liveness disabled (`liveness_detector is None`) → `encode_face()` called normally (regression guard)

#### Presenter tests (thêm vào `tests/test_main.py`):
- **Test P1**: `_on_spoof_detected()` khi `_current_mode is None` → bỏ qua (mode guard)
- **Test P2**: `_on_spoof_detected()` khi mode=1 → GUI update (bounding box + text)
- **Test P3**: `_on_spoof_detected()` khi mode=2 → GUI update (same behavior)
- **Test P4**: `SPOOF_DETECTED` nằm trong danh sách events subscribed

#### Baseline regression:
- TOÀN BỘ tests hiện có phải pass (baseline: 28 liveness + 3 worker + 59 presenter + others)
- 6 pre-existing failures (student_add/remove handlers + imwrite mock) → KHÔNG tính là regression

## Tasks / Subtasks

- [x] Task 1 (AC: #1): Thêm `SPOOF_DETECTED` vào `EventType`
  - [x] Sửa `src/core/events.py` L53 — thêm 1 dòng

- [x] Task 2 (AC: #2, #5): Tích hợp `LivenessDetector` vào `RecognitionWorker`
  - [x] Sửa `__init__()` — thêm `liveness_enabled` config check + lazy import + init
  - [x] Sửa `run()` L113-114 — thêm liveness check block giữa `if location:` và `encoding = encode_face()`
  - [x] Throttle sau spoof: `self.stop_event.wait(timeout=self.scan_interval)` + `continue`

- [x] Task 3 (AC: #3): Thêm `_on_spoof_detected()` vào Presenter
  - [x] Subscribe `EventType.SPOOF_DETECTED` trong `_setup_events()` (L90)
  - [x] Implement handler — mode guard + bounding box đỏ + text cảnh báo + logging
  - [x] Đặt gần `_on_face_unrecognized()` (cùng pattern)

- [x] Task 4 (AC: #4): VERIFY `config.yaml` có section `liveness` (đọc, KHÔNG sửa)

- [x] Task 5 (AC: #6): Unit tests
  - [x] Thêm 5 tests vào `tests/test_worker.py` (W1-W5)
  - [x] Thêm 4 tests vào `tests/test_main.py` (P1-P4)
  - [x] Run full test suite — verify 0 new regressions

## Dev Notes

### Architecture Pattern (MVP)
- **Model**: `RecognitionWorker` (`src/core/worker.py`) — thêm `LivenessDetector` init + liveness check vào recognition loop
- **View**: KHÔNG thay đổi — dùng lại:
  - `camera_panel.set_bounding_box(coords, color)` (L84-92) — nhận dict `{'top','right','bottom','left'}` + color string
  - `camera_panel.clear_bounding_box()` (L94-96)
  - `session_panel.info_label.configure(text=...)` (CTkLabel, L53-59)
- **Presenter**: `src/main.py` — thêm handler `_on_spoof_detected()` + subscribe event

### Integration Point — CHÍNH XÁC
Worker recognition loop (`src/core/worker.py` L104-154):
```
L104: try:
L105:   frame = self.camera_manager.get_frame()
L111:   location = detect_faces(frame)
L113:   if location:
      → ★ INSERT HERE: liveness check (AC2)
L114:     encoding = encode_face(frame, location)
L117:     match_result = find_best_match(...)
L138:     if mode == 1: events.emit(TEACHER_DETECTED, ...)
L140:     elif mode == 2: events.emit(STUDENT_DETECTED, ...)
L142:     else: events.emit(FACE_UNRECOGNIZED, ...)
L151:   # Throttle
L153:   if self.stop_event.wait(timeout=self.scan_interval): break
```

### Presenter Event Handler Pattern — COPY EXACTLY
`_on_face_unrecognized()` (`src/main.py` L435-447):
```python
def _on_face_unrecognized(self, data):
    if self._current_mode is None:
        return
    coords = data.get('coordinates')
    if coords:
        self.app.after(0, self.app.camera_panel.set_bounding_box, coords, 'red')
        self.app.after(2000, self.app.camera_panel.clear_bounding_box)
    self.app.after(
        0, lambda: self.app.session_panel.info_label.configure(
            text="❌ Không nhận diện được"
        )
    )
```
→ `_on_spoof_detected()` dùng CÙNG pattern, chỉ đổi text + thêm logger.warning

### Test Patterns — REUSE EXACTLY
- Worker tests: xem `tests/test_worker.py` L1-120 cho mock pattern (`MockCameraManager`, `mock_config`, `@patch`)
- Presenter tests: xem `tests/test_main.py` L12-78 cho mock pattern (`setUp()` patches tất cả dependencies)
- Mock `Config()` singleton: `Config._instance = None` rồi set `config._data = {...}`
- ⚠️ test_main.py dùng `unittest.TestCase` (KHÔNG dùng pytest fixtures)

### Anti-Patterns to AVOID
- ❌ KHÔNG sửa `src/core/recognition.py` — liveness là concern riêng, thuộc `worker.py`
- ❌ KHÔNG sửa `src/core/liveness.py` — Story 10.1 đã hoàn thành, KHÔNG modify
- ❌ KHÔNG block main thread — liveness check PHẢI chạy trên worker thread
- ❌ KHÔNG emit SPOOF_DETECTED khi `self.liveness_detector is None` (disabled)
- ❌ KHÔNG import `LivenessDetector` ở top-level `worker.py` — dùng lazy import trong `__init__()` body
- ❌ KHÔNG quên mode guard trong `_on_spoof_detected()` — phải check `_current_mode is None`
- ❌ KHÔNG tạo handler mới trong GUI panels — dùng lại `set_bounding_box()` + `info_label.configure()`
- ❌ KHÔNG update `src/core/__init__.py` — project dùng full import path
- ❌ KHÔNG sửa `config.yaml` — section `liveness` đã có từ Story 10.1

### Previous Story Intelligence (10.1)
- `LivenessDetector` là stateless per call — thread-safe, an toàn gọi từ worker thread
- `check_liveness(frame, face_location)`:
  - `frame`: RGB numpy array (từ `CameraManager.get_frame()`)
  - `face_location`: `FaceDetectionResult` TypedDict `{'top', 'right', 'bottom', 'left'}`
  - Returns: `{'is_live': bool, 'score': float, 'details': dict}`
  - Guard cases đã handle: None frame, None location, ROI quá nhỏ → return `{'is_live': False, 'score': 0.0, 'details': {}}`
  - Disabled bypass: return `{'is_live': True, 'score': 1.0, 'details': {}}`
- Config singleton pattern: `LivenessDetector()` tự đọc `Config()` — KHÔNG truyền parameter
- 28 unit tests đã pass trong `tests/test_liveness.py`
- Code review v5 đã hoàn thành — module stable
- Performance: ~10-20ms overhead per frame (acceptable trên worker thread với scan_interval=0.3s)

### Project Structure Notes
- Không tạo file mới — chỉ sửa 3 file hiện có
- Import path: `from src.core.liveness import LivenessDetector` (full path, không dùng relative)
- Event constants: string-based (`"spoof_detected"`) — cùng pattern với tất cả EventType khác

### References
- [Source: src/core/worker.py#L104-L154] — Recognition loop (integration point)
- [Source: src/core/worker.py#L14-L42] — Worker __init__ (add liveness_detector)
- [Source: src/core/worker.py#L30-L33] — Config pattern (reuse cho liveness config)
- [Source: src/core/events.py#L38-L53] — EventType class (add SPOOF_DETECTED)
- [Source: src/main.py#L78-L90] — _setup_events() (add subscribe)
- [Source: src/main.py#L435-L447] — _on_face_unrecognized() (copy pattern for _on_spoof_detected)
- [Source: src/core/liveness.py#L151-L281] — check_liveness() API (called by worker)
- [Source: src/gui/camera_panel.py#L84-L96] — set_bounding_box() + clear_bounding_box() API
- [Source: src/gui/session_panel.py#L53-L59] — info_label widget
- [Source: config.yaml#L28-L42] — liveness config section (verify only)
- [Source: tests/test_worker.py] — Worker test patterns
- [Source: tests/test_main.py#L12-L78] — Presenter test patterns (setUp/tearDown)

---

## Dev Agent Record

### Agent Model Used
Claude Opus 4.6 (Thinking)

### Debug Log References
- No debug issues encountered.

### Completion Notes
- ✅ Task 1: Added `SPOOF_DETECTED = "spoof_detected"` to `EventType` in `src/core/events.py` (1 line)
- ✅ Task 2: Integrated `LivenessDetector` into `RecognitionWorker`:
  - Lazy import in `__init__()` — only when `liveness.enabled=true`
  - Anti-spoofing check block in `run()` between `if location:` and `encode_face()` — emits `SPOOF_DETECTED`, skips encoding on spoof
  - Throttle via `self.stop_event.wait(timeout=self.scan_interval)` + `continue`
- ✅ Task 3: Added `_on_spoof_detected()` handler in `Presenter`:
  - Subscribed `EventType.SPOOF_DETECTED` in `_setup_events()`
  - Handler follows exact same pattern as `_on_face_unrecognized()`: mode guard → red bounding box 2s → warning text on `info_label`
  - Added `logger.warning()` with liveness score and details
- ✅ Task 4: Verified `config.yaml` has `liveness` section (L28-42) — NO changes made
- ✅ Task 5: Added 9 unit tests (5 Worker + 4 Presenter), all pass
  - W1: liveness enabled → detector not None
  - W2: liveness disabled → detector None
  - W3: spoof → SPOOF_DETECTED emitted, encode skipped
  - W4: live face → encode_face called, no SPOOF_DETECTED
  - W5: disabled bypass → encode_face called normally
  - P1: mode guard (idle → ignored)
  - P2: mode=1 → GUI update (bbox + text)
  - P3: mode=2 → GUI update (same)
  - P4: SPOOF_DETECTED in subscribed events list
- 0 new regressions — all 5 remaining failures are pre-existing (student_add/remove handlers + imwrite mock)

### Change Log
- 2026-05-06 (party-mode-v2): Solo-mode adversarial review — 6 findings (1 HIGH, 3 MEDIUM, 2 LOW), 4 fixed:
  - PM-F1/F5 [HIGH]: Removed dead-code outer `with patch(...)` in W1 test, simplified lazy import mock
  - PM-F6 [MEDIUM]: Fixed mock constructor semantics — `lambda: instance` → `MagicMock(return_value=instance)` for clearer intent
  - PM-F1 [MEDIUM]: Added try/finally for Config singleton cleanup in W1 — prevents state leakage on test failure
  - PM-F2 [MEDIUM]: Added try/finally for Config singleton cleanup in W2 — same as W1
  - PM-F3 [LOW]: Documented — `time.sleep(0.3)` in W3 acceptable for integration-style thread tests
  - PM-F4 [MEDIUM]: Documented — lambda stale-text race in `_on_spoof_detected()` consistent with `_on_face_unrecognized()` pattern
- 2026-05-06 (code-review): Adversarial code review — 8 findings (1 HIGH, 5 MEDIUM, 2 LOW), 6 fixed:
  - F1/F3 [HIGH]: Fixed stale expected_events list in test_presenter_init_components_created — removed STUDENT_ADD/REMOVE_REQUESTED (handlers deleted), added FACE_UNRECOGNIZED + MANUAL_MARK_REQUESTED + SPOOF_DETECTED. Test now passes (pre-existing failures: 6 → 5)
  - F4 [MEDIUM]: Fixed lambda-based unsubscribe no-op in test_worker_live_face_continues_normal_flow — replaced with named function for proper cleanup
  - F5 [MEDIUM]: Fixed eager f-string evaluation in logger.warning — switched to lazy % formatting in _on_spoof_detected()
  - F8 [LOW]: Added explicit mock_encode.assert_not_called() in test W3 for stronger encode_face skip assertion
  - F2 [MEDIUM]: Documented — worker tests W1/W2 manually create Config without mock_config fixture (fragile but functional)
  - F6 [MEDIUM]: Documented — rapid consecutive bbox clear_bounding_box race (consistent with existing _on_face_unrecognized pattern)
  - F7 [LOW]: Documented — defensive coords guard is unreachable in practice
- 2026-05-06 (dev): Implementation complete — 3 source files modified, 2 test files updated, 9 new tests (all pass)
- 2026-05-06 (v3): Party-mode roundtable review — 3 findings fixed:
  - PM-F1 [MEDIUM]: Fixed AC2 intro text contradiction — "TOP-LEVEL" → "LAZY trong __init__()" to match code snippet + anti-patterns
  - PM-F2 [MEDIUM]: Added W4 (positive path) + W5 (disabled bypass) tests — ≥7 → ≥9, covers regression risk
  - PM-F3 [LOW]: Corrected baseline counts — 120 worker → 3, ~40 presenter → 59 (verified via grep)
- 2026-05-06 (v2): Validation + remediation — 14 findings fixed
- 2026-05-06 (v1): Initial story creation from sprint-status.yaml E10-S2

### File List

| File | Action |
|------|--------|
| `src/core/events.py` | MODIFY — Added `SPOOF_DETECTED = "spoof_detected"` to EventType (1 line) |
| `src/core/worker.py` | MODIFY — Added LivenessDetector lazy import + init in __init__() (~8 lines) + liveness check in run() loop (~14 lines) |
| `src/main.py` | MODIFY — Added `_on_spoof_detected()` handler (~16 lines) + subscribe in _setup_events() (1 line) |
| `config.yaml` | VERIFY ONLY — Confirmed liveness section exists (NO changes) |
| `tests/test_worker.py` | MODIFY — Added 5 tests (W1-W5) for liveness integration (~130 lines) |
| `tests/test_main.py` | MODIFY — Added 4 tests (P1-P4) for spoof detected handler (~70 lines) |
