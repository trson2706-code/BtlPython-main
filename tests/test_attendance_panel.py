import pytest
import customtkinter as ctk
from unittest.mock import Mock, patch
from src.gui.attendance_panel import AttendancePanel
from src.core.events import events, EventType


@pytest.fixture
def app():
    """Tạo CTk root cho test."""
    _app = ctk.CTk()
    yield _app
    _app.destroy()


@pytest.fixture
def panel(app):
    """Tạo AttendancePanel instance."""
    _panel = AttendancePanel(app)
    yield _panel


@pytest.fixture(autouse=True)
def cleanup_events():
    """Cleanup event subscriptions sau mỗi test."""
    yield
    with events._lock:
        events._listeners.clear()


# ── Dữ liệu test ──

SAMPLE_STUDENTS = [
    {'student_id': 1, 'name': 'Nguyễn Văn A', 'student_code': '2024001'},
    {'student_id': 2, 'name': 'Trần Văn B', 'student_code': '2024002'},
    {'student_id': 3, 'name': 'Lê Thị C', 'student_code': '2024003'},
]

SAMPLE_SESSION_DATA = {
    'class_id': 1,
    'students': SAMPLE_STUDENTS,
}

SAMPLE_RECORD = {
    'student_id': 1,
    'name': 'Nguyễn Văn A',
    'student_code': '2024001',
    'confidence': 95.5,
    'mark_time': '14:30:25',
}


class TestAttendancePanelInitialization:
    """Test khởi tạo AttendancePanel default state."""

    def test_panel_is_ctk_frame(self, panel):
        assert isinstance(panel, ctk.CTkFrame)

    def test_default_session_inactive(self, panel):
        assert panel._session_active is False

    def test_default_records_empty(self, panel):
        assert panel._records == {}

    def test_default_total_students_zero(self, panel):
        assert panel._total_students == 0

    def test_default_present_count_zero(self, panel):
        assert panel._present_count == 0

    def test_default_stats_label(self, panel):
        text = panel.stats_label.cget("text")
        assert "0/0" in text

    def test_placeholder_visible_by_default(self, panel):
        """Placeholder \"Chưa có phiên điểm danh\" visible khi mới tạo."""
        text = panel._placeholder_label.cget("text")
        assert "Chưa có phiên điểm danh" in text
        # Placeholder phải đang được pack (visible)
        assert panel._placeholder_label.winfo_manager() == "pack"


class TestOnSessionStarted:
    """Test on_session_started()."""

    def test_renders_student_list_all_absent(self, panel):
        """on_session_started() render tất cả SV với ❌ Vắng."""
        panel.on_session_started(SAMPLE_SESSION_DATA)

        assert len(panel._records) == 3
        assert panel._total_students == 3
        assert panel._session_active is True

        for student_id, record in panel._records.items():
            assert record['is_present'] is False
            assert "Vắng" in record['status_label'].cget("text")

    def test_hides_placeholder(self, panel):
        """on_session_started() ẩn placeholder."""
        panel.on_session_started(SAMPLE_SESSION_DATA)
        # Placeholder phải bị pack_forget (không visible)
        assert panel._placeholder_label.winfo_manager() == ""

    def test_double_call_resets_first(self, panel):
        """on_session_started() gọi lần 2 → reset session cũ trước (no duplicate rows)."""
        panel.on_session_started(SAMPLE_SESSION_DATA)
        assert len(panel._records) == 3

        # Gọi lần 2 với data mới
        new_data = {
            'class_id': 2,
            'students': [
                {'student_id': 10, 'name': 'Phạm Văn D', 'student_code': '2024010'},
            ]
        }
        panel.on_session_started(new_data)

        # Records chỉ chứa data mới
        assert len(panel._records) == 1
        assert 10 in panel._records
        assert 1 not in panel._records

    def test_empty_students_no_crash(self, panel):
        """on_session_started() với empty students list → no crash, stats \"0/0\"."""
        panel.on_session_started({'class_id': 1, 'students': []})

        assert panel._total_students == 0
        assert len(panel._records) == 0
        text = panel.stats_label.cget("text")
        assert "0/0" in text

    def test_stats_after_session_started(self, panel):
        """Stats hiển thị đúng sau session started."""
        panel.on_session_started(SAMPLE_SESSION_DATA)
        text = panel.stats_label.cget("text")
        assert "0/3" in text

    def test_malformed_student_data_skipped(self, panel):
        """L1: on_session_started() skip SV dict thiếu student_id key — no crash."""
        data = {
            'class_id': 1,
            'students': [
                {'name': 'No ID Student', 'student_code': '0000'},  # missing student_id
                {'student_id': 1, 'name': 'Nguyễn Văn A', 'student_code': '2024001'},
            ]
        }
        panel.on_session_started(data)

        # Chỉ render 1 SV hợp lệ, skip malformed
        assert len(panel._records) == 1
        assert 1 in panel._records
        # Architect-1 FIX: _total_students đếm chỉ students hợp lệ (có student_id)
        assert panel._total_students == 1


class TestAddRecord:
    """Test add_record()."""

    def test_updates_student_present(self, panel):
        """add_record() cập nhật dòng SV: ❌ → ✅ + giờ + stats."""
        panel.on_session_started(SAMPLE_SESSION_DATA)
        panel.add_record(SAMPLE_RECORD)

        record = panel._records[1]
        assert record['is_present'] is True
        assert "Có mặt" in record['status_label'].cget("text")
        assert "14:30:25" in record['time_label'].cget("text")

    def test_stats_updated(self, panel):
        """add_record() cập nhật stats."""
        panel.on_session_started(SAMPLE_SESSION_DATA)
        panel.add_record(SAMPLE_RECORD)

        text = panel.stats_label.cget("text")
        assert "1/3" in text

    def test_duplicate_student_id_skip(self, panel):
        """add_record() duplicate student_id → skip (idempotency)."""
        panel.on_session_started(SAMPLE_SESSION_DATA)
        panel.add_record(SAMPLE_RECORD)
        panel.add_record(SAMPLE_RECORD)

        # present_count chỉ tăng 1 lần
        assert panel._present_count == 1

    def test_session_inactive_skip(self, panel):
        """add_record() khi session inactive → skip."""
        panel.on_session_started(SAMPLE_SESSION_DATA)
        panel._session_active = False
        panel.add_record(SAMPLE_RECORD)

        record = panel._records[1]
        assert record['is_present'] is False

    def test_unknown_student_id_skip(self, panel):
        """add_record() student_id không có trong _records → skip (no KeyError)."""
        panel.on_session_started(SAMPLE_SESSION_DATA)

        unknown_record = {
            'student_id': 999,
            'name': 'Unknown',
            'student_code': '0000',
            'confidence': 50.0,
            'mark_time': '15:00:00',
        }
        # Should not raise KeyError
        panel.add_record(unknown_record)
        assert panel._present_count == 0

    def test_widget_destroyed_no_tcl_error(self, app):
        """add_record() khi widget đã bị destroy (winfo_exists guard) → no TclError."""
        _panel = AttendancePanel(app)
        _panel.on_session_started(SAMPLE_SESSION_DATA)

        # Destroy panel
        _panel.destroy()
        app.update_idletasks()

        # Should not crash
        _panel.add_record(SAMPLE_RECORD)

    def test_add_record_after_session_ended_skip(self, panel):
        """T1: add_record() sau on_session_ended() → skip (session inactive)."""
        panel.on_session_started(SAMPLE_SESSION_DATA)
        panel.add_record(SAMPLE_RECORD)
        assert panel._present_count == 1

        panel.on_session_ended({
            'class_id': 1, 'start_time': None, 'end_time': None,
            'present': [], 'absent': [],
        })

        # Thêm record sau khi session ended → skip
        panel.add_record({
            'student_id': 2, 'name': 'Trần Văn B', 'student_code': '2024002',
            'confidence': 90.0, 'mark_time': '15:00:00',
        })
        assert panel._present_count == 1  # Không tăng
        assert panel._records[2]['is_present'] is False


class TestUpdateStats:
    """Test _update_stats()."""

    def test_calculates_correct_percentage(self, panel):
        """_update_stats() tính đúng X/Y/Z%."""
        panel.on_session_started(SAMPLE_SESSION_DATA)
        panel.add_record(SAMPLE_RECORD)
        panel.add_record({
            'student_id': 2, 'name': 'Trần Văn B', 'student_code': '2024002',
            'confidence': 90.0, 'mark_time': '14:31:00',
        })

        text = panel.stats_label.cget("text")
        assert "2/3" in text
        assert "66%" in text

    def test_zero_total_no_division_error(self, panel):
        """_update_stats() khi _total_students == 0 → không ZeroDivisionError."""
        panel._total_students = 0
        panel._update_stats()
        text = panel.stats_label.cget("text")
        assert "0/0" in text


class TestOnSessionEnded:
    """Test on_session_ended()."""

    def test_sets_session_inactive(self, panel):
        """on_session_ended() sets _session_active = False."""
        panel.on_session_started(SAMPLE_SESSION_DATA)
        panel.add_record(SAMPLE_RECORD)

        panel.on_session_ended({
            'class_id': 1, 'start_time': None, 'end_time': None,
            'present': [], 'absent': [],
        })
        assert panel._session_active is False

    def test_updates_stats_label_with_ended(self, panel):
        """on_session_ended() có thể update stats label."""
        panel.on_session_started(SAMPLE_SESSION_DATA)
        panel.add_record(SAMPLE_RECORD)

        panel.on_session_ended({
            'class_id': 1, 'start_time': None, 'end_time': None,
            'present': [], 'absent': [],
        })
        text = panel.stats_label.cget("text")
        assert "KẾT THÚC" in text
        assert "1/3" in text


class TestFullLifecycle:
    """T1: Test full session lifecycle flow."""

    def test_full_session_lifecycle(self, panel):
        """T1: start → add records → end → verify frozen state."""
        # 1. Start session
        panel.on_session_started(SAMPLE_SESSION_DATA)
        assert panel._session_active is True
        assert panel._total_students == 3
        assert panel._present_count == 0

        # 2. Add attendance records
        panel.add_record(SAMPLE_RECORD)
        assert panel._present_count == 1
        assert "1/3" in panel.stats_label.cget("text")

        panel.add_record({
            'student_id': 2, 'name': 'Trần Văn B', 'student_code': '2024002',
            'confidence': 90.0, 'mark_time': '14:35:00',
        })
        assert panel._present_count == 2
        assert "2/3" in panel.stats_label.cget("text")

        # 3. End session
        panel.on_session_ended({
            'class_id': 1, 'start_time': None, 'end_time': None,
            'present': [], 'absent': [],
        })
        assert panel._session_active is False
        assert "KẾT THÚC" in panel.stats_label.cget("text")
        assert "2/3" in panel.stats_label.cget("text")

        # 4. Verify add_record after end is skipped
        panel.add_record({
            'student_id': 3, 'name': 'Lê Thị C', 'student_code': '2024003',
            'confidence': 85.0, 'mark_time': '14:40:00',
        })
        assert panel._present_count == 2  # Không tăng
        assert panel._records[3]['is_present'] is False

    def test_new_session_after_ended(self, panel):
        """T1: Start new session after previous ended → clean slate."""
        # First session
        panel.on_session_started(SAMPLE_SESSION_DATA)
        panel.add_record(SAMPLE_RECORD)
        panel.on_session_ended({
            'class_id': 1, 'start_time': None, 'end_time': None,
            'present': [], 'absent': [],
        })

        # New session
        new_data = {
            'class_id': 2,
            'students': [
                {'student_id': 10, 'name': 'Phạm Văn D', 'student_code': '2024010'},
            ]
        }
        panel.on_session_started(new_data)

        # Clean slate
        assert panel._session_active is True
        assert panel._total_students == 1
        assert panel._present_count == 0
        assert 10 in panel._records
        assert 1 not in panel._records


class TestReset:
    """Test reset()."""

    def test_clears_records_and_stats(self, panel):
        """reset() xóa toàn bộ + reset stats."""
        panel.on_session_started(SAMPLE_SESSION_DATA)
        panel.add_record(SAMPLE_RECORD)

        panel.reset()

        assert panel._records == {}
        assert panel._total_students == 0
        assert panel._present_count == 0
        assert panel._session_active is False

    def test_destroys_row_widgets(self, panel):
        """reset() gọi destroy() cho mỗi row widget (tránh memory leak)."""
        panel.on_session_started(SAMPLE_SESSION_DATA)

        # Capture row frame refs trước khi reset
        row_frames = [rec['row_frame'] for rec in panel._records.values()]

        panel.reset()

        # Verify widgets đã bị destroy
        for row in row_frames:
            assert not row.winfo_exists()

    def test_shows_placeholder(self, panel):
        """reset() hiển thị lại placeholder."""
        panel.on_session_started(SAMPLE_SESSION_DATA)
        panel.reset()

        assert panel._placeholder_label.winfo_manager() == "pack"

    def test_stats_reset_to_zero(self, panel):
        """reset() reset stats label."""
        panel.on_session_started(SAMPLE_SESSION_DATA)
        panel.add_record(SAMPLE_RECORD)
        panel.reset()

        text = panel.stats_label.cget("text")
        assert "0/0" in text

    def test_reset_mid_session(self, panel):
        """reset() giữa session → clear records."""
        panel.on_session_started(SAMPLE_SESSION_DATA)
        panel.add_record(SAMPLE_RECORD)
        assert panel._present_count == 1

        panel.reset()

        assert panel._present_count == 0
        assert len(panel._records) == 0

