import pytest
import customtkinter as ctk
from unittest.mock import Mock, patch
from src.gui.session_panel import SessionPanel
from src.core.events import events, EventType


@pytest.fixture
def app():
    """Tạo CTk root cho test."""
    _app = ctk.CTk()
    yield _app
    _app.destroy()


@pytest.fixture
def panel(app):
    """Tạo SessionPanel instance default."""
    _panel = SessionPanel(app, scan_time_minutes=60)
    yield _panel


@pytest.fixture(autouse=True)
def cleanup_events():
    """Cleanup event subscriptions sau mỗi test."""
    yield
    # Reset tất cả listeners
    with events._lock:
        events._listeners.clear()


class TestSessionPanelInitialization:
    """Test khởi tạo SessionPanel."""

    def test_panel_is_ctk_frame(self, panel):
        assert isinstance(panel, ctk.CTkFrame)

    def test_default_state_waiting_teacher(self, panel):
        assert panel._state == SessionPanel.WAITING_TEACHER

    def test_default_remaining_seconds_zero(self, panel):
        assert panel._remaining_seconds == 0

    def test_default_timer_id_none(self, panel):
        assert panel._timer_id is None

    def test_scan_time_stored(self, panel):
        assert panel._scan_time_minutes == 60

    def test_has_status_label(self, panel):
        assert hasattr(panel, 'status_label')

    def test_has_info_label(self, panel):
        assert hasattr(panel, 'info_label')

    def test_has_countdown_label(self, panel):
        assert hasattr(panel, 'countdown_label')

    def test_has_confirm_button(self, panel):
        assert hasattr(panel, 'confirm_button')

    def test_has_end_button(self, panel):
        assert hasattr(panel, 'end_button')

    def test_initial_status_text(self, panel):
        # Status label nên hiển thị "CHỜ GIẢNG VIÊN"
        text = panel.status_label.cget("text")
        assert "CHỜ GIẢNG VIÊN" in text


class TestStateTransitions:
    """Test state transitions: WAITING → ACTIVE → ENDED."""

    def test_waiting_to_active(self, panel):
        # Simulate teacher detected first
        panel.on_teacher_detected({
            'person_id': 1,
            'name': 'Nguyễn Văn A',
            'teacher_code': 'GV001',
            'class_info': 'CNTT01 - Lập trình Python',
            'confidence': 95.5,
            'coordinates': {'top': 10, 'right': 100, 'bottom': 110, 'left': 5},
        })
        
        # on_session_started transitions to ACTIVE
        panel.on_session_started({
            'class_id': 1,
            'start_time': '2026-04-28 10:00:00',
        })
        assert panel._state == SessionPanel.ATTENDANCE_ACTIVE

    def test_active_to_ended(self, panel):
        # Go to ACTIVE first
        panel.on_session_started({
            'class_id': 1,
            'start_time': '2026-04-28 10:00:00',
        })
        
        # on_session_ended transitions to ENDED
        panel.on_session_ended({})
        assert panel._state == SessionPanel.SESSION_ENDED

    def test_ended_status_text(self, panel):
        panel.on_session_started({'class_id': 1, 'start_time': ''})
        panel.on_session_ended({})
        text = panel.status_label.cget("text")
        assert "ĐÃ KẾT THÚC" in text


class TestConfirmButton:
    """Test nút Xác nhận behavior."""

    def test_confirm_button_disabled_by_default(self, panel):
        state = panel.confirm_button.cget("state")
        assert state == "disabled"

    def test_confirm_button_enabled_after_teacher_detected(self, panel):
        panel.on_teacher_detected({
            'person_id': 1,
            'name': 'Nguyễn Văn A',
            'teacher_code': 'GV001',
            'class_info': 'CNTT01 - Lập trình Python',
            'confidence': 95.5,
            'coordinates': {'top': 10, 'right': 100, 'bottom': 110, 'left': 5},
        })
        state = panel.confirm_button.cget("state")
        assert state == "normal"


class TestEndButton:
    """Test nút Kết thúc behavior."""

    def test_end_button_disabled_by_default(self, panel):
        state = panel.end_button.cget("state")
        assert state == "disabled"

    def test_end_button_enabled_when_active(self, panel):
        panel.on_session_started({
            'class_id': 1,
            'start_time': '2026-04-28 10:00:00',
        })
        state = panel.end_button.cget("state")
        assert state == "normal"


class TestTeacherDetected:
    """Test on_teacher_detected."""

    def test_teacher_name_displayed(self, panel):
        panel.on_teacher_detected({
            'person_id': 1,
            'name': 'Nguyễn Văn A',
            'teacher_code': 'GV001',
            'class_info': 'CNTT01 - Lập trình Python',
            'confidence': 95.5,
            'coordinates': {'top': 10, 'right': 100, 'bottom': 110, 'left': 5},
        })
        text = panel.info_label.cget("text")
        assert "Nguyễn Văn A" in text


class TestStudentDetected:
    """Test on_student_detected."""

    def test_student_name_displayed(self, panel):
        panel.on_student_detected({
            'person_id': 2,
            'name': 'Trần Văn B',
            'student_code': '2024001',
            'confidence': 92.0,
            'coordinates': {'top': 20, 'right': 200, 'bottom': 220, 'left': 15},
        })
        text = panel.info_label.cget("text")
        assert "Trần Văn B" in text


class TestCountdownTimer:
    """Test countdown timer logic."""

    def test_session_started_begins_timer(self, panel):
        panel.on_session_started({
            'class_id': 1,
            'start_time': '2026-04-28 10:00:00',
        })
        # D2: _start_countdown() hiển thị 60:00 rồi decrement trước khi schedule tick
        assert panel._remaining_seconds == 60 * 60 - 1
        # Timer should be scheduled
        assert panel._timer_id is not None

    def test_countdown_label_format(self, panel):
        panel.on_session_started({
            'class_id': 1,
            'start_time': '2026-04-28 10:00:00',
        })
        text = panel.countdown_label.cget("text")
        assert text == "60:00"

    def test_countdown_timeout_emits_session_end_requested(self, app):
        """Timer hết giờ → emit SESSION_END_REQUESTED."""
        mock_listener = Mock()
        events.subscribe(EventType.SESSION_END_REQUESTED, mock_listener)
        
        _panel = SessionPanel(app, scan_time_minutes=0)
        _panel.on_session_started({
            'class_id': 1,
            'start_time': '2026-04-28 10:00:00',
        })
        
        # scan_time_minutes = 0 → remaining_seconds = 0
        # _tick_countdown sẽ emit SESSION_END_REQUESTED lập tức
        mock_listener.assert_called_once_with({})

    def test_on_session_ended_cancels_timer(self, panel):
        panel.on_session_started({
            'class_id': 1,
            'start_time': '',
        })
        assert panel._timer_id is not None
        
        panel.on_session_ended({})
        assert panel._timer_id is None


class TestReset:
    """Test reset() method."""

    def test_reset_returns_to_waiting(self, panel):
        panel.on_session_started({'class_id': 1, 'start_time': ''})
        panel.reset()
        assert panel._state == SessionPanel.WAITING_TEACHER

    def test_reset_clears_info(self, panel):
        panel.on_teacher_detected({
            'person_id': 1,
            'name': 'Nguyễn Văn A',
            'teacher_code': 'GV001',
            'class_info': 'CNTT01',
            'confidence': 95.0,
            'coordinates': {},
        })
        panel.reset()
        text = panel.info_label.cget("text")
        assert text == ""

    def test_reset_cancels_running_timer(self, panel):
        panel.on_session_started({'class_id': 1, 'start_time': ''})
        assert panel._timer_id is not None
        
        panel.reset()
        assert panel._timer_id is None

    def test_reset_resets_remaining_seconds(self, panel):
        panel.on_session_started({'class_id': 1, 'start_time': ''})
        panel.reset()
        assert panel._remaining_seconds == 0


class TestTickCountdownGuard:
    """Test _tick_countdown winfo_exists guard."""

    def test_tick_countdown_after_destroy(self, app):
        """_tick_countdown() không crash khi winfo_exists() trả False."""
        _panel = SessionPanel(app, scan_time_minutes=1)
        _panel.on_session_started({'class_id': 1, 'start_time': ''})

        # Cancel existing timer first to avoid interference
        _panel._stop_timer()

        # Destroy panel
        _panel.destroy()
        app.update_idletasks()

        # Call _tick_countdown manually — should not crash
        _panel._tick_countdown()


class TestConfirmButtonEmission:
    """Test nút Xác nhận emits SESSION_CONFIRMED (H1)."""

    def test_confirm_click_emits_session_confirmed(self, panel):
        """Click Xác nhận → emit SESSION_CONFIRMED."""
        mock_listener = Mock()
        events.subscribe(EventType.SESSION_CONFIRMED, mock_listener)

        # Enable button first (requires teacher detected)
        panel.on_teacher_detected({
            'person_id': 1,
            'name': 'Nguyễn Văn A',
            'teacher_code': 'GV001',
            'class_info': 'CNTT01 - Lập trình Python',
            'confidence': 95.5,
            'coordinates': {'top': 10, 'right': 100, 'bottom': 110, 'left': 5},
        })

        # Simulate button click
        panel._on_confirm_click()

        # D3: Now emits {} instead of None
        mock_listener.assert_called_once_with({})


class TestEndButtonEmission:
    """Test nút Kết thúc emits SESSION_END_REQUESTED (H2)."""

    def test_end_click_emits_session_end_requested(self, panel):
        """Click Kết thúc → emit SESSION_END_REQUESTED."""
        mock_listener = Mock()
        events.subscribe(EventType.SESSION_END_REQUESTED, mock_listener)

        # Go to ACTIVE state first
        panel.on_session_started({
            'class_id': 1,
            'start_time': '2026-04-28 10:00:00',
        })

        # Simulate button click
        panel._on_end_click()

        # D3: Now emits {} instead of None
        mock_listener.assert_called_once_with({})


class TestEnrichedDataDisplay:
    """Test enriched data fields are displayed correctly (H3)."""

    def test_teacher_code_displayed(self, panel):
        """on_teacher_detected → teacher_code hiển thị."""
        panel.on_teacher_detected({
            'person_id': 1,
            'name': 'Nguyễn Văn A',
            'teacher_code': 'GV001',
            'class_info': 'CNTT01 - Lập trình Python',
            'confidence': 95.5,
            'coordinates': {},
        })
        text = panel.info_label.cget("text")
        assert "GV001" in text

    def test_teacher_class_info_displayed(self, panel):
        """on_teacher_detected → class_info hiển thị."""
        panel.on_teacher_detected({
            'person_id': 1,
            'name': 'Nguyễn Văn A',
            'teacher_code': 'GV001',
            'class_info': 'CNTT01 - Lập trình Python',
            'confidence': 95.5,
            'coordinates': {},
        })
        text = panel.info_label.cget("text")
        assert "CNTT01 - Lập trình Python" in text

    def test_teacher_confidence_displayed(self, panel):
        """on_teacher_detected → confidence % hiển thị."""
        panel.on_teacher_detected({
            'person_id': 1,
            'name': 'Nguyễn Văn A',
            'teacher_code': 'GV001',
            'class_info': 'CNTT01',
            'confidence': 95.5,
            'coordinates': {},
        })
        text = panel.info_label.cget("text")
        assert "95.5%" in text

    def test_student_code_displayed(self, panel):
        """on_student_detected → student_code (MSSV) hiển thị."""
        panel.on_student_detected({
            'person_id': 2,
            'name': 'Trần Văn B',
            'student_code': '2024001',
            'confidence': 92.0,
            'coordinates': {},
        })
        text = panel.info_label.cget("text")
        assert "2024001" in text

    def test_student_present_status_displayed(self, panel):
        """on_student_detected → '✅ Có mặt' hiển thị."""
        panel.on_student_detected({
            'person_id': 2,
            'name': 'Trần Văn B',
            'student_code': '2024001',
            'confidence': 92.0,
            'coordinates': {},
        })
        text = panel.info_label.cget("text")
        assert "✅ Có mặt" in text

    def test_student_confidence_displayed(self, panel):
        """on_student_detected → confidence % hiển thị."""
        panel.on_student_detected({
            'person_id': 2,
            'name': 'Trần Văn B',
            'student_code': '2024001',
            'confidence': 92.0,
            'coordinates': {},
        })
        text = panel.info_label.cget("text")
        assert "92.0%" in text


class TestTickCountdownStateGuard:
    """Test _tick_countdown state guard (M4)."""

    def test_tick_countdown_skips_when_session_ended(self, panel):
        """_tick_countdown() không emit khi state != ATTENDANCE_ACTIVE."""
        mock_listener = Mock()
        events.subscribe(EventType.SESSION_END_REQUESTED, mock_listener)

        # Start session then end it
        panel.on_session_started({'class_id': 1, 'start_time': ''})
        panel.on_session_ended({})

        # Manually set remaining_seconds to 0 and call tick
        panel._remaining_seconds = 0
        panel._tick_countdown()

        # Should NOT emit because state is SESSION_ENDED
        mock_listener.assert_not_called()

    def test_tick_countdown_skips_when_waiting(self, panel):
        """_tick_countdown() không chạy khi state = WAITING_TEACHER."""
        mock_listener = Mock()
        events.subscribe(EventType.SESSION_END_REQUESTED, mock_listener)

        panel._remaining_seconds = 0
        panel._tick_countdown()

        # Should NOT emit because state is WAITING_TEACHER
        mock_listener.assert_not_called()


class TestNegativeScanTime:
    """Test negative scan_time_minutes validation (L2)."""

    def test_negative_scan_time_clamped_to_zero(self, app):
        """scan_time_minutes = -5 → _scan_time_minutes = 0."""
        _panel = SessionPanel(app, scan_time_minutes=-5)
        assert _panel._scan_time_minutes == 0

    def test_zero_scan_time_accepted(self, app):
        """scan_time_minutes = 0 → _scan_time_minutes = 0."""
        _panel = SessionPanel(app, scan_time_minutes=0)
        assert _panel._scan_time_minutes == 0

    def test_positive_scan_time_unchanged(self, app):
        """scan_time_minutes = 30 → _scan_time_minutes = 30."""
        _panel = SessionPanel(app, scan_time_minutes=30)
        assert _panel._scan_time_minutes == 30


class TestDoubleSessionStarted:
    """Test on_session_started() idempotency guard (Q3)."""

    def test_double_session_started_is_noop(self, panel):
        """on_session_started() gọi 2 lần → lần 2 là no-op, không tạo orphaned timer."""
        panel.on_session_started({'class_id': 1, 'start_time': ''})
        first_timer_id = panel._timer_id
        first_remaining = panel._remaining_seconds

        panel.on_session_started({'class_id': 2, 'start_time': ''})
        second_timer_id = panel._timer_id
        second_remaining = panel._remaining_seconds

        # Timer ID không thay đổi vì lần 2 return ngay
        assert first_timer_id == second_timer_id
        assert first_remaining == second_remaining

    def test_session_started_allowed_after_reset(self, panel):
        """on_session_started() sau reset() → chấp nhận bình thường."""
        panel.on_session_started({'class_id': 1, 'start_time': ''})
        panel.reset()
        assert panel._state == SessionPanel.WAITING_TEACHER

        # Should work again after reset
        panel.on_session_started({'class_id': 2, 'start_time': ''})
        assert panel._state == SessionPanel.ATTENDANCE_ACTIVE
        assert panel._timer_id is not None

