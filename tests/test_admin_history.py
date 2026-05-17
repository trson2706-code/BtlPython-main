"""Unit tests cho AdminWindow History Tab (E9-S2).

16 test cases covering:
- Test 1: AdminWindow tạo đúng 5 tabs (bao gồm "📋 Lịch sử")
- Test 2: _refresh_history_list() hiển thị sessions từ DB
- Test 3: _refresh_history_list() hiển thị empty label khi không có sessions
- Test 4: Filter theo class_id — chỉ hiển thị sessions của lớp đó
- Test 5: _show_session_detail() gọi get_session_records() với đúng session_id
- Test 6: Date range filter — chỉ hiển thị sessions trong khoảng
- Test 7: _update_stats() tính đúng tỷ lệ trung bình
- Test 8: _reexport_session() gọi ExcelExporter đúng format
- Test 9: [F1-fix] _reexport_session() catches ImportError/KeyError gracefully
- Test 10: [F2-fix] _safe_parse_datetime() handles malformed strings
- Test 11: [F3-fix] _reconstruct_session_result() handles ISO 8601 timestamps
- Test 12: [F5-fix] _update_stats() clamps present > total
- Test 13: [F10-fix] _refresh_history_filters() picks up new classes
- Test 14: [F11-fix] _reconstruct_session_result() includes class_id
- Test 15: [F9-fix] _reexport_session() catches OSError gracefully
- Test 16: [F11-fix] Combined class + date filter works simultaneously
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
import customtkinter as ctk


# ── Shared Fixtures ──

@pytest.fixture
def mock_deps():
    """Create mock dependencies for AdminWindow."""
    parent = ctk.CTk()
    class_mgr = MagicMock()
    student_mgr = MagicMock()
    db = MagicMock()

    # Default: no data so AdminWindow builds without errors
    class_mgr.get_all_teachers.return_value = []
    class_mgr.get_all_classes.return_value = []
    class_mgr.get_students_in_class.return_value = []
    student_mgr.get_all_students.return_value = []
    db.get_all_classes.return_value = []
    db.get_all_timetable.return_value = []
    db.get_sessions.return_value = []
    db.get_session_records.return_value = []

    yield parent, class_mgr, student_mgr, db

    parent.destroy()


@pytest.fixture
def admin_window(mock_deps):
    """Create AdminWindow instance with mocked dependencies."""
    parent, class_mgr, student_mgr, db = mock_deps
    from src.gui.admin_window import AdminWindow
    win = AdminWindow(parent, class_mgr, student_mgr, db)
    yield win
    try:
        win.destroy()
    except Exception:
        pass


# ══════════════════════════════════════════
# TEST 1: AdminWindow tạo đúng 5 tabs
# ══════════════════════════════════════════

def test_admin_window_has_5_tabs(admin_window):
    """AC1: AdminWindow phải có đúng 5 tabs, bao gồm '📋 Lịch sử'."""
    # CTkTabview._tab_dict chứa tên tab → segment button mapping
    tab_names = list(admin_window.tabview._tab_dict.keys())
    assert len(tab_names) == 5
    expected = ["Giảng viên", "Sinh viên", "Lớp học", "Thời khóa biểu", "📋 Lịch sử"]
    assert tab_names == expected


# ══════════════════════════════════════════
# TEST 2: _refresh_history_list() hiển thị sessions
# ══════════════════════════════════════════

def test_refresh_history_list_shows_sessions(mock_deps):
    """AC2: _refresh_history_list() phải hiển thị sessions từ DB."""
    parent, class_mgr, student_mgr, db = mock_deps
    db.get_sessions.return_value = [
        {
            'id': 1, 'class_id': 10, 'teacher_id': 1,
            'session_date': '2026-05-05', 'start_time': '2026-05-05 14:00:00',
            'end_time': '2026-05-05 15:00:00', 'total_students': 30,
            'present_count': 25, 'class_code': 'CS101', 'subject': 'CV',
            'teacher_name': 'GV A',
        },
        {
            'id': 2, 'class_id': 10, 'teacher_id': 1,
            'session_date': '2026-05-04', 'start_time': '2026-05-04 14:00:00',
            'end_time': '2026-05-04 15:00:00', 'total_students': 30,
            'present_count': 28, 'class_code': 'CS101', 'subject': 'CV',
            'teacher_name': 'GV A',
        },
    ]
    from src.gui.admin_window import AdminWindow
    win = AdminWindow(parent, class_mgr, student_mgr, db)

    # 2 session rows should be created
    assert len(win._history_widgets) == 2

    win.destroy()


# ══════════════════════════════════════════
# TEST 3: _refresh_history_list() empty → empty label
# ══════════════════════════════════════════

def test_refresh_history_list_empty_shows_label(admin_window):
    """AC2: Khi không có sessions → hiển thị empty label."""
    admin_window.db.get_sessions.return_value = []
    admin_window._refresh_history_list()

    # Should have 1 widget (the empty label)
    assert len(admin_window._history_widgets) == 1


# ══════════════════════════════════════════
# TEST 4: Filter theo class_id
# ══════════════════════════════════════════

def test_filter_by_class_calls_get_sessions_with_class_id(mock_deps):
    """AC4: Filter theo lớp → gọi get_sessions(class_id=X)."""
    parent, class_mgr, student_mgr, db = mock_deps
    db.get_all_classes.return_value = [
        {'id': 10, 'class_code': 'CS101', 'subject': 'CV'},
    ]
    db.get_sessions.return_value = []

    from src.gui.admin_window import AdminWindow
    win = AdminWindow(parent, class_mgr, student_mgr, db)

    # Reset call tracking after init
    db.get_sessions.reset_mock()

    # Set class filter to "CS101 — CV"
    win._history_class_filter.set("CS101 — CV")
    win._refresh_history_list()

    # get_sessions should be called with class_id=10
    db.get_sessions.assert_called_once_with(class_id=10)

    win.destroy()


# ══════════════════════════════════════════
# TEST 5: _show_session_detail() gọi get_session_records()
# ══════════════════════════════════════════

def test_show_session_detail_calls_get_records(admin_window):
    """AC3: _show_session_detail() gọi get_session_records() đúng session_id."""
    admin_window.db.get_session_records.return_value = [
        {
            'id': 1, 'session_id': 5, 'student_id': 100,
            'is_present': 1, 'confidence': 0.95,
            'mark_time': '2026-05-05 14:30:00', 'image_path': None,
            'name': 'SV 1', 'student_code': 'SV001',
        },
    ]

    session = {
        'id': 5, 'class_id': 10, 'teacher_id': 1,
        'session_date': '2026-05-05', 'start_time': '2026-05-05 14:00:00',
        'end_time': '2026-05-05 15:00:00', 'total_students': 30,
        'present_count': 25, 'class_code': 'CS101', 'subject': 'CV',
        'teacher_name': 'GV A',
    }
    admin_window._show_session_detail(5, session)

    admin_window.db.get_session_records.assert_called_with(5)

    # [F9-fix] Verify dialog was actually created (CTkToplevel child exists)
    children = admin_window.winfo_children()
    toplevels = [w for w in children if isinstance(w, ctk.CTkToplevel)]
    assert len(toplevels) >= 1, "Session detail dialog should have been created"


# ══════════════════════════════════════════
# TEST 6: Date filter
# ══════════════════════════════════════════

def test_date_filter_applies_correctly(mock_deps):
    """AC5: Date range filter chỉ hiển thị sessions trong khoảng."""
    parent, class_mgr, student_mgr, db = mock_deps
    db.get_sessions.return_value = [
        {
            'id': 1, 'class_id': 10, 'teacher_id': 1,
            'session_date': '2026-05-03', 'start_time': '2026-05-03 14:00:00',
            'end_time': '2026-05-03 15:00:00', 'total_students': 30,
            'present_count': 25, 'class_code': 'CS101', 'subject': 'CV',
            'teacher_name': 'GV A',
        },
        {
            'id': 2, 'class_id': 10, 'teacher_id': 1,
            'session_date': '2026-05-05', 'start_time': '2026-05-05 14:00:00',
            'end_time': '2026-05-05 15:00:00', 'total_students': 30,
            'present_count': 28, 'class_code': 'CS101', 'subject': 'CV',
            'teacher_name': 'GV A',
        },
        {
            'id': 3, 'class_id': 10, 'teacher_id': 1,
            'session_date': '2026-05-07', 'start_time': '2026-05-07 14:00:00',
            'end_time': '2026-05-07 15:00:00', 'total_students': 30,
            'present_count': 20, 'class_code': 'CS101', 'subject': 'CV',
            'teacher_name': 'GV A',
        },
    ]
    from src.gui.admin_window import AdminWindow
    win = AdminWindow(parent, class_mgr, student_mgr, db)

    # Set date filters
    win._history_from_date.insert(0, "2026-05-04")
    win._history_to_date.insert(0, "2026-05-06")
    win._refresh_history_list()

    # Only session 2 (2026-05-05) should be visible
    assert len(win._history_widgets) == 1

    win.destroy()


# ══════════════════════════════════════════
# TEST 7: _update_stats() tính đúng tỷ lệ
# ══════════════════════════════════════════

def test_update_stats_correct_calculation(admin_window):
    """AC6: Stats phải tính tỷ lệ đi học trung bình đúng."""
    sessions = [
        {'total_students': 30, 'present_count': 25},
        {'total_students': 30, 'present_count': 28},
    ]
    admin_window._update_stats(sessions)

    label_text = admin_window._history_stats_label.cget("text")
    # avg = (25 + 28) / (30 + 30) * 100 = 88.3%
    assert "88.3%" in label_text
    assert "2 phiên" in label_text


# ══════════════════════════════════════════
# TEST 8: _reexport_session() calls ExcelExporter
# ══════════════════════════════════════════

def test_reexport_session_calls_exporter(admin_window):
    """AC7: _reexport_session() phải reconstruct đúng format và gọi ExcelExporter."""
    admin_window.db.get_session_records.return_value = [
        {
            'id': 1, 'session_id': 5, 'student_id': 100,
            'is_present': 1, 'confidence': 0.95,
            'mark_time': '2026-05-05 14:30:00', 'image_path': None,
            'name': 'SV 1', 'student_code': 'SV001',
        },
        {
            'id': 2, 'session_id': 5, 'student_id': 101,
            'is_present': 0, 'confidence': 0.0,
            'mark_time': None, 'image_path': None,
            'name': 'SV 2', 'student_code': 'SV002',
        },
    ]
    admin_window.db.get_class.return_value = {'class_code': 'CS101', 'subject': 'CV'}
    admin_window.db.get_teacher.return_value = {'name': 'GV A'}

    session = {
        'id': 5, 'class_id': 10, 'teacher_id': 1,
        'session_date': '2026-05-05', 'start_time': '2026-05-05 14:00:00',
        'end_time': '2026-05-05 15:00:00', 'total_students': 30,
        'present_count': 25, 'class_code': 'CS101', 'subject': 'CV',
        'teacher_name': 'GV A',
    }

    # [F8-fix] Single patch at the correct import path (removed redundant outer patch)
    with patch('src.core.excel_export.ExcelExporter') as MockExporter:
        mock_instance = MagicMock()
        MockExporter.return_value = mock_instance
        mock_instance.export_session.return_value = '/path/to/exported.xlsx'

        admin_window._reexport_session(5, session)

        # Verify export was called
        mock_instance.export_session.assert_called_once()
        call_args = mock_instance.export_session.call_args

        # Verify session_result has correct structure
        sr = call_args[0][0]
        assert 'present' in sr
        assert 'absent' in sr
        assert 'start_time' in sr
        assert 'end_time' in sr

        # Verify present/absent split
        assert len(sr['present']) == 1
        assert len(sr['absent']) == 1
        assert sr['present'][0]['student_code'] == 'SV001'
        assert sr['absent'][0]['student_code'] == 'SV002'

        # Verify start_time is datetime (not string)
        from datetime import datetime
        assert isinstance(sr['start_time'], datetime)
        assert isinstance(sr['end_time'], datetime)


# ══════════════════════════════════════════
# TEST 9: [F1-fix] _reexport_session catches unexpected exceptions
# ══════════════════════════════════════════

def test_reexport_session_catches_all_exceptions(admin_window):
    """[F1-fix] _reexport_session must not propagate exceptions to Tk event loop."""
    admin_window.db.get_session_records.return_value = []
    admin_window.db.get_class.return_value = None
    admin_window.db.get_teacher.return_value = None

    session = {
        'id': 5, 'class_id': 10, 'teacher_id': 1,
        'session_date': '2026-05-05', 'start_time': '2026-05-05 14:00:00',
        'end_time': '2026-05-05 15:00:00', 'total_students': 30,
        'present_count': 25, 'class_code': 'CS101', 'subject': 'CV',
        'teacher_name': 'GV A',
    }

    # Simulate ImportError (openpyxl not installed)
    with patch('src.core.excel_export.ExcelExporter', side_effect=ImportError("No module named 'openpyxl'")):
        # Should NOT raise — should show error dialog instead
        admin_window._reexport_session(5, session)
        # If we reach here, the exception was caught ✓


# ══════════════════════════════════════════
# TEST 10: [F2-fix] _safe_parse_datetime handles malformed strings
# ══════════════════════════════════════════

def test_safe_parse_datetime_handles_formats(admin_window):
    """[F2-fix] _safe_parse_datetime must handle multiple datetime formats."""
    from datetime import datetime

    # Standard format
    result = admin_window._safe_parse_datetime('2026-05-05 14:30:00')
    assert result == datetime(2026, 5, 5, 14, 30, 0)

    # ISO 8601 with T separator
    result = admin_window._safe_parse_datetime('2026-05-05T14:30:00')
    assert result == datetime(2026, 5, 5, 14, 30, 0)

    # With microseconds
    result = admin_window._safe_parse_datetime('2026-05-05 14:30:00.123456')
    assert result == datetime(2026, 5, 5, 14, 30, 0, 123456)

    # Completely malformed → fallback
    result = admin_window._safe_parse_datetime('not-a-date', fallback='FALLBACK')
    assert result == 'FALLBACK'

    # None → fallback
    result = admin_window._safe_parse_datetime(None, fallback='FALLBACK')
    assert result == 'FALLBACK'

    # Empty string → fallback
    result = admin_window._safe_parse_datetime('', fallback='FALLBACK')
    assert result == 'FALLBACK'


# ══════════════════════════════════════════
# TEST 11: [F3-fix] _reconstruct_session_result handles ISO timestamps
# ══════════════════════════════════════════

def test_reconstruct_handles_iso_timestamps(admin_window):
    """[F3-fix] _reconstruct_session_result should handle ISO 8601 timestamps."""
    from datetime import datetime

    session = {
        'id': 5, 'class_id': 10,
        'start_time': '2026-05-05T14:00:00',  # ISO 8601 with T
        'end_time': '2026-05-05T15:00:00',
    }
    records = [
        {
            'student_code': 'SV001', 'name': 'SV 1', 'is_present': 1,
            'confidence': 0.9, 'mark_time': '2026-05-05T14:30:00', 'image_path': None,
        },
    ]

    result = admin_window._reconstruct_session_result(session, records)

    # Timestamps should be parsed successfully
    assert isinstance(result['start_time'], datetime)
    assert isinstance(result['end_time'], datetime)
    assert result['present'][0]['mark_time'] == datetime(2026, 5, 5, 14, 30, 0)


# ══════════════════════════════════════════
# TEST 12: [F5-fix] _update_stats clamps present > total
# ══════════════════════════════════════════

def test_update_stats_clamps_corrupted_data(admin_window):
    """[F5-fix] Stats must not show >100% even if present_count > total_students."""
    sessions = [
        {'total_students': 20, 'present_count': 25},  # Corrupted: 25 > 20
    ]
    admin_window._update_stats(sessions)

    label_text = admin_window._history_stats_label.cget("text")
    assert "100.0%" in label_text  # Clamped to 100%


# ══════════════════════════════════════════
# TEST 13: [F10-fix] _refresh_history_filters picks up new classes
# ══════════════════════════════════════════

def test_refresh_history_filters_picks_up_new_classes(admin_window):
    """[F10-fix] Class filter should reflect newly-added classes on refresh."""
    # Initially no classes
    assert admin_window._history_class_filter.cget("values") == ["Tất cả"]

    # Simulate adding a class
    admin_window.db.get_all_classes.return_value = [
        {'id': 10, 'class_code': 'CS101', 'subject': 'CV'},
    ]
    admin_window._refresh_history_filters()

    values = admin_window._history_class_filter.cget("values")
    assert "CS101 — CV" in values
    assert len(values) == 2  # "Tất cả" + "CS101 — CV"


# ══════════════════════════════════════════
# TEST 14: [F11-fix] _reconstruct_session_result includes class_id
# ══════════════════════════════════════════

def test_reconstruct_includes_class_id(admin_window):
    """[F11-fix] Reconstructed session_result must include class_id for consistency."""
    session = {
        'id': 5, 'class_id': 42,
        'start_time': '2026-05-05 14:00:00',
        'end_time': '2026-05-05 15:00:00',
    }
    result = admin_window._reconstruct_session_result(session, [])

    assert 'class_id' in result
    assert result['class_id'] == 42


# ══════════════════════════════════════════
# TEST 15: [F9-fix] _reexport_session catches OSError gracefully
# ══════════════════════════════════════════

def test_reexport_session_catches_os_error(admin_window):
    """[F9-fix] _reexport_session must catch OSError (file write failure) gracefully."""
    admin_window.db.get_session_records.return_value = [
        {
            'id': 1, 'session_id': 5, 'student_id': 100,
            'is_present': 1, 'confidence': 0.95,
            'mark_time': '2026-05-05 14:30:00', 'image_path': None,
            'name': 'SV 1', 'student_code': 'SV001',
        },
    ]
    admin_window.db.get_class.return_value = {'class_code': 'CS101', 'subject': 'CV'}
    admin_window.db.get_teacher.return_value = {'name': 'GV A'}

    session = {
        'id': 5, 'class_id': 10, 'teacher_id': 1,
        'session_date': '2026-05-05', 'start_time': '2026-05-05 14:00:00',
        'end_time': '2026-05-05 15:00:00', 'total_students': 30,
        'present_count': 25, 'class_code': 'CS101', 'subject': 'CV',
        'teacher_name': 'GV A',
    }

    # Simulate OSError from ExcelExporter.export_session()
    with patch('src.core.excel_export.ExcelExporter') as MockExporter:
        mock_instance = MagicMock()
        MockExporter.return_value = mock_instance
        mock_instance.export_session.side_effect = OSError("Permission denied")

        # Should NOT raise — should log and show error dialog
        admin_window._reexport_session(5, session)
        # If we reach here, the exception was caught ✓


# ══════════════════════════════════════════
# TEST 16: [F11-fix] Combined class + date filter
# ══════════════════════════════════════════

def test_combined_class_and_date_filter(mock_deps):
    """[F11-fix] Both class filter and date filter should work simultaneously."""
    parent, class_mgr, student_mgr, db = mock_deps
    db.get_all_classes.return_value = [
        {'id': 10, 'class_code': 'CS101', 'subject': 'CV'},
    ]
    db.get_sessions.return_value = [
        {
            'id': 1, 'class_id': 10, 'teacher_id': 1,
            'session_date': '2026-05-03', 'start_time': '2026-05-03 14:00:00',
            'end_time': '2026-05-03 15:00:00', 'total_students': 30,
            'present_count': 25, 'class_code': 'CS101', 'subject': 'CV',
            'teacher_name': 'GV A',
        },
        {
            'id': 2, 'class_id': 10, 'teacher_id': 1,
            'session_date': '2026-05-05', 'start_time': '2026-05-05 14:00:00',
            'end_time': '2026-05-05 15:00:00', 'total_students': 30,
            'present_count': 28, 'class_code': 'CS101', 'subject': 'CV',
            'teacher_name': 'GV A',
        },
    ]
    from src.gui.admin_window import AdminWindow
    win = AdminWindow(parent, class_mgr, student_mgr, db)

    # Reset call tracking after init
    db.get_sessions.reset_mock()

    # Set BOTH class filter AND date filter
    win._history_class_filter.set("CS101 — CV")
    win._history_from_date.insert(0, "2026-05-04")
    win._history_to_date.insert(0, "2026-05-06")
    win._refresh_history_list()

    # get_sessions should be called with class_id=10
    db.get_sessions.assert_called_once_with(class_id=10)
    # Only session 2 (2026-05-05) should pass date filter
    assert len(win._history_widgets) == 1

    win.destroy()
