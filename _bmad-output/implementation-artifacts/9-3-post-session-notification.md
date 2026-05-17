# Story 9.3: Thông báo + mở file sau khi kết thúc session

Status: done

## Story

Là giảng viên,
Tôi muốn thấy popup thông báo khi phiên điểm danh kết thúc và xuất Excel thành công, kèm nút mở file và xem lịch sử,
Để tôi có thể nhanh chóng kiểm tra file kết quả hoặc tra cứu lịch sử ngay lập tức mà không cần thao tác thủ công.

## Acceptance Criteria

### AC1: Popup thông báo sau khi xuất Excel thành công
- Sau khi `ExcelExporter.export_session()` trả về filepath thành công trong `_on_session_end_requested()`:
  - Hiển thị `CTkToplevel` popup (KHÔNG phải `on_error()` trên student_panel — popup rõ ràng hơn)
  - Title: `"✅ Kết thúc phiên điểm danh"`
  - Nội dung:
    - Tóm tắt: `"Có mặt X/Y (Z%)"`
    - Đường dẫn file: `"📄 {filepath}"`
    - 3 nút action (xem AC2, AC3, AC4)
  - Popup PHẢI dùng `transient(self.app)` — tránh bị che bởi main window
  - ⚠️ KHÔNG dùng `grab_set()` — popup non-blocking, cho phép auto-reset timer chạy
  - ⚠️ Popup phải tự đóng khi `_reset_to_teacher_mode()` chạy (5 giây timeout) — nếu user chưa đóng, popup bị auto-destroyed
  - ⚠️ KHÔNG chặn auto-reset timer — popup hiển thị song song, KHÔNG modal-block main flow

### AC2: Nút [📂 Mở file] — mở file Excel bằng ứng dụng mặc định
- Nút `"📂 Mở file"` trong popup:
  - macOS: `subprocess.Popen(['open', filepath])`
  - Windows: `os.startfile(filepath)` (platform check)
  - Linux: `subprocess.Popen(['xdg-open', filepath])` (fallback)
  - Wrap trong `try/except (OSError, FileNotFoundError)` — hiển thị error trên popup nếu fail
- ⚠️ PHẢI import `subprocess` (chỉ cần cho `open` command)
- ⚠️ PHẢI import `platform` hoặc dùng `sys.platform` cho platform detection
- ⚠️ KHÔNG dùng `webbrowser.open()` — hành vi không nhất quán với file local trên macOS

### AC3: Nút [📋 Xem lịch sử] — mở thẳng tab Lịch sử trong Admin
- Nút `"📋 Xem lịch sử"` trong popup:
  - Đóng popup → Mở AdminWindow trực tiếp → Set tab Lịch sử active
  - ⚠️ CRITICAL: KHÔNG dùng `events.emit(EventType.ADMIN_REQUESTED, {})` — mode guard sẽ reject vì `_current_mode = None` (idle)
  - Thay vào đó, gọi `self._open_admin_history()` trực tiếp trong Presenter — bypass mode guard
  - Sequence: `_close_post_session_popup()` → `_open_admin_history()`
  - `_open_admin_history()` tạo AdminWindow với `initial_tab="📋 Lịch sử"` + bind `_on_admin_closed` protocol
  - ⚠️ PHẢI sửa `AdminWindow.__init__()` để nhận optional `initial_tab` parameter và gọi `self.tabview.set(initial_tab)` sau build
  - ⚠️ PHẢI sửa `_on_admin_requested()` trong Presenter để forward `initial_tab` parameter (backward-compatible)

### AC4: Hiển thị tóm tắt trên GUI — Có mặt X/Y (Z%)
- **Thay thế** message `"✅ Đã xuất Excel thành công!"` hiện tại trên `student_panel.on_error()` (line 291-294 main.py)
- Thay bằng message chi tiết hơn: `"✅ Có mặt X/Y (Z%) — Excel đã xuất"`
- Tính từ `result`: `present_count = len(result.get('present', []))`, `total = present_count + len(result.get('absent', []))`
- ⚠️ Message này vẫn hiển thị THÊM trên student_panel (5 giây auto-clear) — ngoài popup (AC1)

### AC5: Xử lý trường hợp xuất Excel thất bại
- Nếu `export_session()` raise `(ValueError, OSError)`:
  - KHÔNG hiển thị popup AC1 (chỉ dùng `on_error()` hiện tại)
  - Giữ nguyên behavior hiện tại: `self.app.student_panel.on_error(str(e))`
- ⚠️ Popup chỉ hiện khi export THÀNH CÔNG

### AC6: Unit tests — ≥6 test cases
- Test 1: Popup hiển thị khi export thành công — verify `_post_session_popup` is not None
- Test 2: Summary text computed correctly — present_count/total/percent from result dict
- Test 3: `_open_file()` gọi `subprocess.Popen` với đúng args trên macOS (`sys.platform == 'darwin'`)
- Test 4: `_open_file()` catch OSError gracefully — no exception propagation
- Test 5: `_on_view_history_from_popup()` calls `_open_admin_history()` (NOT event emit) — verify AdminWindow created
- Test 6: Popup không hiện khi export fail — verify `_post_session_popup` remains None
- Test 7: `_close_post_session_popup()` destroys popup safely — verify `_post_session_popup` set to None
- Test 8: AdminWindow nhận `initial_tab` parameter — verify tabview.set() called
- Test 9: `_reset_to_teacher_mode()` skips khi `_admin_window` is not None — verify panels NOT reset
- Baseline: tất cả test hiện có phải pass

## Tasks / Subtasks

- [x] Task 1 (AC: #3): Sửa AdminWindow nhận initial_tab parameter
  - [x] Thêm `initial_tab: str = None` parameter vào `AdminWindow.__init__()`
  - [x] Nếu `initial_tab` có giá trị → gọi `self.tabview.set(initial_tab)` sau khi build tabs
  - [x] Sửa `_on_admin_requested()` trong Presenter: forward `initial_tab` từ event data

- [x] Task 2 (AC: #1, #2, #3, #4, #5): Tạo post-session notification trong Presenter
  - [x] Tạo method `_show_post_session_popup(self, filepath, result)` trong Presenter
  - [x] Build CTkToplevel popup: summary + filepath + 3 nút
  - [x] Implement `_open_file(filepath)` — cross-platform file opener
  - [x] Implement "Xem lịch sử" button — close popup + call `_open_admin_history()` (NOT emit event)
  - [x] Implement "Đóng" button — call `_close_post_session_popup()`
  - [x] Implement `_close_post_session_popup()` — winfo_exists() guard + destroy + set None
  - [x] Implement `_on_view_history_from_popup()` — close popup + call `_open_admin_history()`
  - [x] Lưu popup reference `self._post_session_popup` để cleanup trong `_reset_to_teacher_mode()`

- [x] Task 3 (AC: #4): Cập nhật message trên student_panel
  - [x] Thay `"✅ Đã xuất Excel thành công!"` bằng `"✅ Có mặt X/Y (Z%) — Excel đã xuất"`
  - [x] Tính present_count, total, percent từ result dict

- [x] Task 4 (AC: #1): Cleanup popup trong _reset_to_teacher_mode()
  - [x] Trong `_reset_to_teacher_mode()`: destroy `self._post_session_popup` nếu còn mở
  - [x] Set `self._post_session_popup = None` trong `__init__()` và sau cleanup

- [x] Task 5 (AC: #6): Unit tests
  - [x] Tạo tests trong `tests/test_main.py` (extend existing)
  - [x] Chạy full test suite, verify 0 regressions

## Dev Notes

### Architecture Pattern (MVP)
- **Model**: KHÔNG thay đổi — popup là View concern
- **View**: `AdminWindow` (`src/gui/admin_window.py`) — thêm `initial_tab` parameter
- **Presenter**: `src/main.py` — thêm popup logic vào `_on_session_end_requested()` + cleanup trong `_reset_to_teacher_mode()`
- Popup là `CTkToplevel(self.app)` — tạo bởi Presenter, thuộc main window lifecycle

### ⚠️ CRITICAL: Popup lifecycle vs Auto-Reset timer
```
_on_session_end_requested():
    export_session() → filepath
    → _show_post_session_popup(filepath, result)   ← NON-BLOCKING popup
    → app.after(5000, _reset_to_teacher_mode)       ← 5 giây delay

_reset_to_teacher_mode():
    → popup.destroy() nếu còn mở                    ← CLEANUP
    → reset panels + start_scanning(mode=1)
```
- Popup KHÔNG phải modal (KHÔNG dùng `grab_set()` vì sẽ block auto-reset)
- Thay vào đó dùng `transient(self.app)` only → popup floating trên main window nhưng không block
- Popup có thể bị auto-destroyed khi _reset_to_teacher_mode() chạy → user có 5 giây để interact

### ⚠️ THAY ĐỔI QUYẾT ĐỊNH: Bỏ grab_set() cho popup
- Sprint status mô tả popup thông báo — KHÔNG phải modal dialog
- Popup PHẢI dùng `transient(self.app)` nhưng KHÔNG `grab_set()`
- Lý do: `grab_set()` block tất cả input vào main window → countdown tick (sau session end) bị block, auto-reset không chạy được
- Popup floating: user có thể tương tác với cả popup và main window

### ⚠️ CRITICAL: Mở Admin từ popup — bypass mode guard
- Nút "Xem lịch sử" phải:
  1. Gọi `self._close_post_session_popup()` — destroy popup + set None
  2. Gọi `self._open_admin_history()` — trực tiếp tạo AdminWindow
  3. **KHÔNG** dùng `events.emit(EventType.ADMIN_REQUESTED, {})` — mode guard sẽ reject vì `_current_mode = None`
  - **SOLUTION**: Tạo 2 methods riêng trong Presenter:
    ```python
    def _on_view_history_from_popup(self):
        """Callback: đóng popup + mở Admin tab Lịch sử."""
        self._close_post_session_popup()
        self._open_admin_history()

    def _open_admin_history(self):
        """Mở AdminWindow trực tiếp ở tab Lịch sử — bypass mode guard.
        
        Khác _on_admin_requested(): không check mode, không disable admin_button
        (vì admin_button đã disabled ở SESSION_ENDED state).
        """
        if not self.app.winfo_exists():
            return
        if self._admin_window is not None:
            return
        # pause_scanning() là idempotent — an toàn gọi kể cả khi worker đã paused
        # (session vừa end → worker đã paused; nhưng nếu _reset_to_teacher_mode đã chạy
        # → worker đang scanning mode=1 → cần pause lại)
        self.worker.pause_scanning()
        self._admin_window = AdminWindow(
            self.app, self.class_mgr, self.student_mgr, self.db,
            initial_tab="📋 Lịch sử"
        )
        self._admin_window.protocol("WM_DELETE_WINDOW", self._on_admin_closed)
    ```
  - ⚠️ `_open_admin_history()` KHÔNG disable admin_button — vì session đã ended, button đã disabled bởi `on_session_ended()` (session_panel.py L164)
  - ⚠️ `_open_admin_history()` KHÔNG set `_current_mode = None` — vì mode đã None từ `_on_session_end_requested()` (main.py L270)
  - ⚠️ `_on_admin_closed()` vẫn xử lý đúng — resume scanning + set mode=1 (nếu camera alive)

### ⚠️ Cross-platform file opener
```python
import subprocess
import sys

def _open_file(self, filepath):
    """Mở file bằng ứng dụng mặc định — cross-platform."""
    try:
        if sys.platform == 'darwin':
            subprocess.Popen(['open', filepath])
        elif sys.platform == 'win32':
            os.startfile(filepath)
        else:
            subprocess.Popen(['xdg-open', filepath])
    except (OSError, FileNotFoundError) as e:
        logger.error(f"Không thể mở file: {e}")
```

### ⚠️ Popup widget pattern — Presenter tạo CTkToplevel
```python
def _show_post_session_popup(self, filepath, result):
    """Hiển thị popup thông báo sau session — NON-BLOCKING."""
    import customtkinter as ctk  # Lazy import — main.py không import ctk ở top-level
    
    # Guard: app phải còn sống
    if not self.app.winfo_exists():
        return
    # Guard: tránh duplicate popup
    if self._post_session_popup is not None:
        return
    
    # Tính summary
    present = result.get('present', []) or []
    absent = result.get('absent', []) or []
    present_count = len(present)
    total = present_count + len(absent)
    pct = (present_count / total * 100) if total > 0 else 0
    
    popup = ctk.CTkToplevel(self.app)
    popup.title("✅ Kết thúc phiên điểm danh")
    popup.geometry("480x250")
    popup.transient(self.app)
    # ⚠️ KHÔNG grab_set() — non-blocking popup
    
    # Summary
    ctk.CTkLabel(popup, text=f"Có mặt {present_count}/{total} ({pct:.1f}%)",
                 font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(15, 5))
    
    # Filepath
    ctk.CTkLabel(popup, text=f"📄 {filepath}", wraplength=440,
                 text_color="gray", font=ctk.CTkFont(size=12)).pack(pady=5, padx=20)
    
    # Buttons frame
    bf = ctk.CTkFrame(popup, fg_color="transparent")
    bf.pack(pady=15)
    
    ctk.CTkButton(bf, text="📂 Mở file", width=120,
                  command=lambda: self._open_file(filepath)).pack(side="left", padx=8)
    ctk.CTkButton(bf, text="📋 Xem lịch sử", width=120,
                  command=lambda: self._on_view_history_from_popup()).pack(side="left", padx=8)
    ctk.CTkButton(bf, text="Đóng", width=80,
                  command=lambda: self._close_post_session_popup()).pack(side="left", padx=8)
    
    self._post_session_popup = popup
    # ⚠️ KHÔNG dùng popup.after(30000, ...) — popup sẽ bị destroy bởi _reset_to_teacher_mode() ở 5s
    # Safety net không cần vì popup lifecycle được quản lý bởi Presenter

def _close_post_session_popup(self):
    """Destroy popup nếu còn mở — winfo_exists() guard."""
    if self._post_session_popup is not None:
        try:
            if self._post_session_popup.winfo_exists():
                self._post_session_popup.destroy()
        except Exception:
            pass
        self._post_session_popup = None
```

### ⚠️ Sửa _on_session_end_requested() — thay thế on_error message
```python
# BEFORE (lines 290-294):
self.app.after(
    0, self.app.student_panel.on_error,
    "✅ Đã xuất Excel thành công!", "green"
)

# AFTER:
present_count = len(result.get('present', []))
total = present_count + len(result.get('absent', []))
pct = (present_count / total * 100) if total > 0 else 0
summary_msg = f"✅ Có mặt {present_count}/{total} ({pct:.1f}%) — Excel đã xuất"
self.app.after(0, self.app.student_panel.on_error, summary_msg, "green")
# ★ NEW: Popup thông báo
self.app.after(0, self._show_post_session_popup, filepath, result)
```

### ⚠️ Sửa _reset_to_teacher_mode() — cleanup popup + admin guard
```python
def _reset_to_teacher_mode(self):
    if not self.app.winfo_exists():
        return
    # ★ NEW: Cleanup post-session popup nếu còn mở
    self._close_post_session_popup()
    # ★ NEW [F6/F7/F12-fix]: Skip reset nếu AdminWindow đang mở
    # (user click "Xem lịch sử" từ popup → mở admin → auto-reset timer vẫn pending
    #  → nếu không guard thì reset sẽ corrupt state: start_scanning + mode=1 khi admin open)
    if self._admin_window is not None:
        return
    # ... existing reset code ...
```

### ⚠️ AdminWindow initial_tab parameter
```python
class AdminWindow(ctk.CTkToplevel):
    def __init__(self, parent, class_mgr, student_mgr, db, initial_tab=None):
        # ... existing init code ...
        self._build_history_tab()
        
        # ★ NEW: Set active tab nếu specified
        if initial_tab:
            try:
                self.tabview.set(initial_tab)
            except ValueError:
                pass  # Tab name không tồn tại — ignore
```

### ⚠️ Sửa Presenter._on_admin_requested() — forward initial_tab
```python
def _on_admin_requested(self, data):
    # ... existing guards ...
    initial_tab = data.get('initial_tab') if data else None
    self._admin_window = AdminWindow(
        self.app, self.class_mgr, self.student_mgr, self.db,
        initial_tab=initial_tab
    )
```

### Anti-Patterns to AVOID
- ❌ KHÔNG dùng `grab_set()` cho popup — sẽ block auto-reset timer
- ❌ KHÔNG dùng `events.emit(EventType.ADMIN_REQUESTED)` cho "Xem lịch sử" button — mode guard sẽ reject (mode = None)
- ❌ KHÔNG tạo popup khi export fail — chỉ dùng `on_error()` hiện tại
- ❌ KHÔNG import `customtkinter` trong `main.py` ở top-level — PHẢI lazy import `import customtkinter as ctk` bên trong method `_show_post_session_popup()`
- ❌ KHÔNG quên cleanup popup trong `_reset_to_teacher_mode()` — popup sẽ bị orphaned
- ❌ KHÔNG quên `winfo_exists()` guard trong `_close_post_session_popup()` — popup có thể đã bị destroy
- ❌ KHÔNG dùng `webbrowser.open()` — hành vi không nhất quán trên macOS cho local files
- ❌ KHÔNG dùng `os.startfile()` trên macOS — chỉ có trên Windows
- ❌ KHÔNG sửa `session_panel.py` — popup thuộc Presenter scope
- ❌ KHÔNG sửa `student_panel.py` — chỉ thay message text trong Presenter call
- ❌ KHÔNG sửa `database.py` — không có DB change
- ❌ KHÔNG tạo file GUI mới — popup logic nằm trong Presenter (small enough)
- ❌ KHÔNG quên `self._post_session_popup = None` trong `Presenter.__init__()` — cleanup method sẽ fail
- ❌ KHÔNG quên guard `_admin_window is not None` trong `_reset_to_teacher_mode()` — nếu bỏ sót, auto-reset sẽ corrupt state khi user mở admin từ popup

### Thread Safety
- Popup tạo và destroy trên main thread (GUI thread) — an toàn
- `_show_post_session_popup()` được gọi qua `self.app.after(0, ...)` — đã schedule lên main thread
- `_close_post_session_popup()` cũng chạy trên main thread (from `_reset_to_teacher_mode()`)
- `subprocess.Popen()` non-blocking — không block GUI thread

### Backward Compatibility
- `AdminWindow.__init__()` thêm optional param `initial_tab=None` — tất cả caller cũ không bị ảnh hưởng
- `_on_admin_requested()` thêm `initial_tab` extraction từ event data — `data.get()` return None nếu key không tồn tại → backward-compatible
- Message thay đổi trên `student_panel.on_error()` — chỉ text khác, không ảnh hưởng logic
- Popup tự cleanup — không có state leak

### Project Structure Notes
- `src/main.py` L13-14: Thêm `import subprocess` và `import sys` — SAU `import os` (L13), TRƯỚC `from datetime import datetime` (L14)
- `src/main.py` L63: Thêm `self._post_session_popup = None` SAU `self._admin_window = None` (L63) trong `Presenter.__init__()`
- `src/main.py` L286-297: Thay message + thêm popup call trong `_on_session_end_requested()` (success branch)
- `src/main.py` L307-325: Sửa `_reset_to_teacher_mode()`:
  - Thêm `self._close_post_session_popup()` ở ĐẦU (sau winfo_exists guard, L313)
  - Thêm `if self._admin_window is not None: return` guard SAU cleanup popup
- `src/main.py` sau L540 (cuối `_on_admin_closed`): Thêm 5 methods mới:
  - `_show_post_session_popup(filepath, result)` — tạo CTkToplevel popup (~50 lines)
  - `_open_file(filepath)` — cross-platform file opener (~10 lines)
  - `_close_post_session_popup()` — winfo_exists guard + destroy (~8 lines)
  - `_on_view_history_from_popup()` — close popup + open admin history (~4 lines)
  - `_open_admin_history()` — AdminWindow trực tiếp ở tab Lịch sử (~10 lines)
- `src/main.py` L489: Sửa AdminWindow constructor call trong `_on_admin_requested()` — thêm `initial_tab`
- `src/gui/admin_window.py` L24: Thêm `initial_tab=None` parameter vào constructor signature
- `src/gui/admin_window.py` L52: Thêm `if initial_tab: self.tabview.set(initial_tab)` SAU `self._build_history_tab()` (L52)
- Tests: Thêm ≥9 test cases vào `tests/test_main.py`

### References
- [Source: src/main.py#L249-L305] — `_on_session_end_requested()` — hook point cho popup
- [Source: src/main.py#L307-L325] — `_reset_to_teacher_mode()` — cleanup hook + admin guard
- [Source: src/main.py#L34-L63] — `Presenter.__init__()` — state tracking init
- [Source: src/main.py#L473-L491] — `_on_admin_requested()` — AdminWindow creation pattern
- [Source: src/main.py#L493-L540] — `_on_admin_closed()` — AdminWindow cleanup pattern
- [Source: src/gui/admin_window.py#L23-L53] — `AdminWindow.__init__()` — constructor to modify
- [Source: src/gui/admin_window.py#L39] — Tab names list (cho initial_tab validation)
- [Source: src/gui/student_panel.py#L149-L161] — `on_error()` pattern (auto-clear 5 giây)
- [Source: src/core/events.py#L38-L52] — EventType constants (ADMIN_REQUESTED)
- [Source: src/core/excel_export.py#L54-L68] — `export_session()` return filepath / raise ValueError|OSError

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (Thinking)

### Debug Log References

### Completion Notes List

- Story context engine analysis completed — comprehensive developer guide created
- Validation pass 1 — 10 findings identified and fixed:
  - [F1] CRITICAL: AC1 contradicted Dev Notes (grab_set vs non-blocking popup) → removed grab_set() from AC1
  - [F2] CRITICAL: AC3 used events.emit() but mode guard would reject → changed to _open_admin_history() direct call
  - [F3] MEDIUM: Test 5 description incorrect (emit vs direct call) → updated test descriptions
  - [F4] MEDIUM: _open_admin_history() missing app guard + rationale for skipping admin_button disable → added guards + documented
  - [F5] MEDIUM: popup.after(30000) fires on destroyed popup → removed 30s timer, rely on _reset_to_teacher_mode() cleanup
  - [F6] LOW: 30s timeout unreachable (5s reset runs first) → removed redundant timer
  - [F7] LOW: Missing lazy import documentation → added `import customtkinter as ctk` to code snippet
  - [F8] LOW: _on_view_history_from_popup() never defined → added explicit code snippet
  - [F9] MEDIUM: Import placement unclear → specified exact insertion point (after os, before datetime)
  - [F10] LOW: _close_post_session_popup() missing → added full code snippet with winfo_exists guard
- Adversarial review pass 2 — 8 findings identified and fixed:
  - [F1-R2] CRITICAL: All line number references in Project Structure Notes were stale → corrected to match actual src/main.py (567 lines)
  - [F2-R2] CRITICAL: _post_session_popup init reference "line 62+" → corrected to L63 (after _admin_window)
  - [F3-R2] MEDIUM: Import placement line ref misleading → corrected to "L13-14 (after os, before datetime)"
  - [F5-R2] MEDIUM: pause_scanning() in _open_admin_history() is idempotent but undocumented → added comment
  - [F6-R2] MEDIUM: Race condition — _reset_to_teacher_mode() fires while AdminWindow opened from popup → added _admin_window guard
  - [F7-R2] MEDIUM: Auto-reset timer not cancelled when opening admin from popup → resolved by _admin_window guard in _reset_to_teacher_mode()
  - [F10-R2] MEDIUM: Missing test for auto-reset guard → added Test 9
  - [F12-R2] MEDIUM: Anti-Patterns list missing _admin_window guard warning → added entry
- ✅ Implementation completed — all 5 tasks, all subtasks done:
  - Task 1: AdminWindow.initial_tab parameter added + _on_admin_requested forward
  - Task 2: 5 new methods in Presenter (popup, open_file, close_popup, view_history, open_admin_history)
  - Task 3: Summary message updated with present_count/total/percent
  - Task 4: _reset_to_teacher_mode cleanup + admin guard added
  - Task 5: 9 new unit tests (Tests 41-49), all passing
- Test results: 46 pass in test_main.py (9 new + 37 baseline), 5 pre-existing failures (stale tests for unimplemented features)
- Updated existing Test 30 assertion to include initial_tab=None kwarg
- Zero regressions across full test suite (338 pass, 34 pre-existing failures)

### Change Log

- 2026-05-05: Implemented E9-S3 post-session notification — all 5 tasks complete, 9 new tests
- 2026-05-05: Code review remediation R2 — 5 findings fixed (F1/F2/F4/F5/F6), 3 new tests (Tests 50-52), total 49 pass
- 2026-05-05: Code review remediation R3 — source code verified clean (no bugs), 5 new tests (Tests 53-57) for coverage gaps, total 54 pass

### File List

| File | Action |
|------|--------|
| `src/main.py` | MODIFY — Added imports (subprocess, sys), _post_session_popup init, popup logic + 6 new methods (incl. _compute_attendance_summary), summary message, _reset_to_teacher_mode cleanup + admin guard, _on_admin_requested initial_tab forwarding, _open_file error feedback + AttributeError guard, _open_admin_history mode neutralization |
| `src/gui/admin_window.py` | MODIFY — Added initial_tab=None parameter to __init__ with tabview.set() |
| `tests/test_main.py` | MODIFY — Added 17 test cases (Tests 41-57), updated Tests 30+44 assertions |

