import pytest
import threading
import customtkinter as ctk
from src.gui.app import App
from src.gui.camera_panel import CameraPanel
from src.gui.session_panel import SessionPanel
from src.gui.attendance_panel import AttendancePanel
from src.gui.student_panel import StudentPanel
from src.core.events import EventType, EventManager, events
from unittest.mock import Mock


# M3 Fix: Dùng pytest fixture để đảm bảo cleanup khi assertion fail
@pytest.fixture
def app():
    """Tạo và cleanup App instance cho mỗi test."""
    _app = App()
    yield _app
    _app.destroy()


def test_app_initialization(app):
    # Title
    assert app.title() == "📚 HỆ THỐNG ĐIỂM DANH SINH VIÊN"
    
    # Geometry and minsize (minsize is a tuple)
    assert app.wm_minsize() == (1200, 800)
    
    # Check theme configuration
    assert ctk.get_appearance_mode() == "Dark"
    
    # Check panels exist: camera_panel (CameraPanel), session_panel (SessionPanel)
    assert hasattr(app, "camera_panel")
    assert isinstance(app.camera_panel, CameraPanel)
    assert hasattr(app, "session_panel")
    assert isinstance(app.session_panel, SessionPanel)
    
    # Check panels exist: attendance_panel (AttendancePanel), student_panel (StudentPanel)
    assert hasattr(app, "attendance_panel")
    assert isinstance(app.attendance_panel, AttendancePanel)
    assert hasattr(app, "student_panel")
    assert isinstance(app.student_panel, StudentPanel)
    
    # Check grid weights: columns 0 and 1
    # left should have weight 6, right 4
    column0_weight = app.grid_columnconfigure(0)["weight"]
    column1_weight = app.grid_columnconfigure(1)["weight"]
    
    assert column0_weight == 6
    assert column1_weight == 4


def test_grid_row_weights(app):
    """Verify row weights đều bằng 1 để chiều dọc co giãn đều."""
    row0_weight = app.grid_rowconfigure(0)["weight"]
    row1_weight = app.grid_rowconfigure(1)["weight"]
    
    assert row0_weight == 1
    assert row1_weight == 1


def test_wm_delete_window_protocol_bound(app):
    """Verify WM_DELETE_WINDOW protocol đã được bind đúng handler."""
    # Tkinter trả về tên registered command cho protocol
    handler = app.wm_protocol("WM_DELETE_WINDOW")
    assert handler, "WM_DELETE_WINDOW protocol chưa được đăng ký"


def test_keyboard_shortcuts_bound(app):
    """Verify cả Command-Q (macOS) và Control-Q (cross-platform) đã bind."""
    # Tkinter bind() trả về list các binding cho sequence
    cmd_q_bindings = app.bind("<Command-q>")
    ctrl_q_bindings = app.bind("<Control-q>")
    
    assert cmd_q_bindings, "Chưa bind <Command-q>"
    assert ctrl_q_bindings, "Chưa bind <Control-q>"


def test_shutdown_event(app):
    mock_listener = Mock()
    events.subscribe(EventType.SHUTDOWN_REQUESTED, mock_listener)
    
    # call on_closing
    app.on_closing()
    
    # M4 Fix: Verify cả argument (data=None) được truyền đúng
    mock_listener.assert_called_once_with(None)
    
    # Teardown
    events.unsubscribe(EventType.SHUTDOWN_REQUESTED, mock_listener)


def test_shutdown_event_only_fires_once(app):
    """M2 Verify: Guard flag ngăn duplicate shutdown events."""
    mock_listener = Mock()
    events.subscribe(EventType.SHUTDOWN_REQUESTED, mock_listener)
    
    # Gọi on_closing hai lần liên tiếp
    app.on_closing()
    app.on_closing()
    
    # Chỉ emit đúng 1 lần
    mock_listener.assert_called_once_with(None)
    
    # Teardown
    events.unsubscribe(EventType.SHUTDOWN_REQUESTED, mock_listener)


def test_event_manager_thread_safety():
    """Verify EventManager không bị race condition khi emit + subscribe đồng thời."""
    em = EventManager()
    call_count = {"value": 0}
    errors = []
    
    def listener(data):
        call_count["value"] += 1
    
    def subscriber_thread():
        """Liên tục subscribe/unsubscribe trong khi emit chạy."""
        try:
            dummy = Mock()
            for _ in range(100):
                em.subscribe("test_event", dummy)
                em.unsubscribe("test_event", dummy)
        except Exception as e:
            errors.append(e)
    
    def emitter_thread():
        """Liên tục emit trong khi subscribe/unsubscribe chạy."""
        try:
            for _ in range(100):
                em.emit("test_event", None)
        except Exception as e:
            errors.append(e)
    
    em.subscribe("test_event", listener)
    
    t1 = threading.Thread(target=subscriber_thread)
    t2 = threading.Thread(target=emitter_thread)
    
    t1.start()
    t2.start()
    t1.join(timeout=5)
    t2.join(timeout=5)
    
    # Không có RuntimeError nào xảy ra
    assert len(errors) == 0, f"Thread-safety errors: {errors}"
    # Listener phải được gọi ít nhất 1 lần
    assert call_count["value"] > 0
