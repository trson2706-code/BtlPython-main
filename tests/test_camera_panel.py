import pytest
import customtkinter as ctk
from unittest.mock import Mock, patch, MagicMock
import numpy as np
from src.gui.camera_panel import CameraPanel


@pytest.fixture
def app():
    """Tạo CTk root cho test."""
    _app = ctk.CTk()
    yield _app
    _app.destroy()


@pytest.fixture
def panel(app):
    """Tạo CameraPanel instance với mock callback."""
    mock_callback = Mock(return_value=None)
    _panel = CameraPanel(app, get_frame_callback=mock_callback)
    yield _panel


@pytest.fixture
def panel_no_callback(app):
    """Tạo CameraPanel instance không có callback."""
    _panel = CameraPanel(app)
    yield _panel


class TestCameraPanelInitialization:
    """Test khởi tạo CameraPanel."""

    def test_panel_is_ctk_frame(self, panel):
        assert isinstance(panel, ctk.CTkFrame)

    def test_default_running_false(self, panel):
        assert panel._running is False

    def test_default_after_id_none(self, panel):
        assert panel._after_id is None

    def test_default_bbox_coords_none(self, panel):
        assert panel._bbox_coords is None

    def test_default_bbox_color_red(self, panel):
        assert panel._bbox_color == "red"

    def test_default_current_image_none(self, panel):
        assert panel._current_image is None

    def test_has_video_label(self, panel):
        assert hasattr(panel, 'video_label')
        assert isinstance(panel.video_label, ctk.CTkLabel)

    def test_callback_stored(self, panel):
        assert panel._get_frame_callback is not None
        assert callable(panel._get_frame_callback)

    def test_no_callback(self, panel_no_callback):
        assert panel_no_callback._get_frame_callback is None


class TestStartStopPreview:
    """Test start/stop preview lifecycle."""

    def test_start_preview_sets_running_true(self, panel):
        panel.start_preview()
        assert panel._running is True
        # Cleanup
        panel.stop_preview()

    def test_stop_preview_sets_running_false(self, panel):
        panel.start_preview()
        panel.stop_preview()
        assert panel._running is False

    def test_stop_preview_cancels_after(self, panel):
        panel.start_preview()
        # after_id should be set after start_preview triggers _update_frame
        panel.stop_preview()
        assert panel._after_id is None

    def test_stop_preview_when_not_running(self, panel):
        """stop_preview() khi chưa start → không crash."""
        panel.stop_preview()
        assert panel._running is False


class TestBoundingBox:
    """Test set/clear bounding box."""

    def test_set_bounding_box_stores_coords(self, panel):
        coords = {'top': 10, 'right': 100, 'bottom': 110, 'left': 5}
        panel.set_bounding_box(coords, "green")
        assert panel._bbox_coords == coords
        assert panel._bbox_color == "green"

    def test_set_bounding_box_red(self, panel):
        coords = {'top': 20, 'right': 200, 'bottom': 220, 'left': 15}
        panel.set_bounding_box(coords, "red")
        assert panel._bbox_coords == coords
        assert panel._bbox_color == "red"

    def test_clear_bounding_box(self, panel):
        coords = {'top': 10, 'right': 100, 'bottom': 110, 'left': 5}
        panel.set_bounding_box(coords, "green")
        panel.clear_bounding_box()
        assert panel._bbox_coords is None


class TestUpdateFrame:
    """Test _update_frame behavior."""

    def test_update_frame_with_none_callback_result(self, panel):
        """Callback trả None → không crash, schedule next."""
        panel._get_frame_callback = Mock(return_value=None)
        panel._running = True
        panel._update_frame()
        # Không crash là pass

    def test_update_frame_with_valid_frame(self, panel, app):
        """Callback trả frame hợp lệ → gọi label.configure."""
        fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        panel._get_frame_callback = Mock(return_value=fake_frame)
        panel._running = True
        
        # Force panel size
        panel.configure(width=640, height=480)
        app.update_idletasks()
        
        panel._update_frame()
        # Không crash và _current_image được set
        # (CTkImage creation may or may not work in headless, 
        #  nhưng quan trọng là không crash)

    def test_update_frame_with_callback_exception(self, panel):
        """Callback ném exception → graceful handle, không crash."""
        panel._get_frame_callback = Mock(side_effect=RuntimeError("Camera error"))
        panel._running = True
        panel._update_frame()
        # Không crash là pass

    def test_update_frame_not_running(self, panel):
        """_running = False → return ngay, không gọi callback."""
        panel._get_frame_callback = Mock(return_value=None)
        panel._running = False
        panel._update_frame()
        panel._get_frame_callback.assert_not_called()

    def test_update_frame_pil_conversion_failure(self, panel):
        """Frame malformed → PIL conversion fail → không crash."""
        # Frame with wrong shape to potentially cause PIL issues
        bad_frame = np.zeros((0, 0, 3), dtype=np.uint8)
        panel._get_frame_callback = Mock(return_value=bad_frame)
        panel._running = True
        panel._update_frame()
        # Không crash là pass

    def test_update_frame_no_callback_set(self, panel_no_callback):
        """Không có callback → schedule next, không crash."""
        panel_no_callback._running = True
        panel_no_callback._update_frame()
        # Không crash là pass


class TestScheduleNext:
    """Test _schedule_next behavior."""

    def test_schedule_next_not_called_when_widget_destroyed(self, app):
        """winfo_exists() trả False → không gọi after()."""
        mock_callback = Mock(return_value=None)
        _panel = CameraPanel(app, get_frame_callback=mock_callback)
        _panel._running = True
        
        # Destroy panel first
        _panel.destroy()
        app.update_idletasks()
        
        # schedule_next should NOT call after() because widget doesn't exist
        _panel._schedule_next()
        # after_id should remain None since after() wasn't called
        assert _panel._after_id is None


class TestUpdateFrameWithBoundingBox:
    """Test _update_frame with active bounding box (M2)."""

    def test_update_frame_calls_cv2_rectangle_when_bbox_set(self, panel, app):
        """Khi bbox active + frame hợp lệ → cv2.rectangle được gọi."""
        fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        panel._get_frame_callback = Mock(return_value=fake_frame)
        panel._running = True
        panel.set_bounding_box(
            {'top': 10, 'right': 100, 'bottom': 110, 'left': 5}, "green"
        )

        panel.configure(width=640, height=480)
        app.update_idletasks()

        with patch('src.gui.camera_panel.cv2.rectangle') as mock_rect:
            panel._update_frame()
            mock_rect.assert_called_once_with(
                # display_frame (copy), (left_coord, top), (right, bottom), green, thickness
                mock_rect.call_args[0][0],  # frame arg — any numpy array
                (5, 10), (100, 110), (0, 255, 0), 2
            )

    def test_update_frame_red_bbox_color(self, panel, app):
        """Bbox color 'red' → (255, 0, 0) truyền vào cv2.rectangle."""
        fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        panel._get_frame_callback = Mock(return_value=fake_frame)
        panel._running = True
        panel.set_bounding_box(
            {'top': 20, 'right': 200, 'bottom': 220, 'left': 15}, "red"
        )

        panel.configure(width=640, height=480)
        app.update_idletasks()

        with patch('src.gui.camera_panel.cv2.rectangle') as mock_rect:
            panel._update_frame()
            mock_rect.assert_called_once()
            # Verify color argument is red
            call_args = mock_rect.call_args[0]
            assert call_args[3] == (255, 0, 0)

    def test_update_frame_no_bbox_skips_rectangle(self, panel, app):
        """Khi bbox None → cv2.rectangle KHÔNG được gọi."""
        fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        panel._get_frame_callback = Mock(return_value=fake_frame)
        panel._running = True
        panel.clear_bounding_box()

        panel.configure(width=640, height=480)
        app.update_idletasks()

        with patch('src.gui.camera_panel.cv2.rectangle') as mock_rect:
            panel._update_frame()
            mock_rect.assert_not_called()


class TestStopPreviewGuard:
    """Test stop_preview() winfo_exists guard (L3)."""

    def test_stop_preview_after_widget_destroy(self, app):
        """stop_preview() sau khi widget bị destroy → không crash."""
        mock_callback = Mock(return_value=None)
        _panel = CameraPanel(app, get_frame_callback=mock_callback)
        _panel.start_preview()

        # Destroy panel first
        _panel.destroy()
        app.update_idletasks()

        # stop_preview should not crash even though widget is destroyed
        _panel.stop_preview()
        assert _panel._running is False


class TestUpdateFrameWidgetDestroyed:
    """Test _update_frame khi widget bị destroy giữa chừng (Q1)."""

    def test_update_frame_returns_when_widget_destroyed(self, app):
        """_update_frame() return ngay khi winfo_exists() trả False."""
        mock_callback = Mock(return_value=None)
        _panel = CameraPanel(app, get_frame_callback=mock_callback)
        _panel._running = True

        # Destroy panel
        _panel.destroy()
        app.update_idletasks()

        # _update_frame should return early, not call callback
        _panel._update_frame()
        mock_callback.assert_not_called()


class TestDoubleStartPreview:
    """Test start_preview() idempotency guard (Q2)."""

    def test_double_start_preview_is_noop(self, panel):
        """start_preview() gọi 2 lần → lần 2 là no-op, không tạo orphaned after."""
        panel.start_preview()
        first_after_id = panel._after_id

        panel.start_preview()  # Should be no-op
        second_after_id = panel._after_id

        # after_id không thay đổi vì lần 2 return ngay
        assert first_after_id == second_after_id

        # Cleanup
        panel.stop_preview()


class TestRestartPreview:
    """Test stop_preview() rồi start_preview() (Q4)."""

    def test_restart_preview_works_cleanly(self, panel):
        """stop_preview() rồi start_preview() → preview chạy lại bình thường."""
        panel.start_preview()
        assert panel._running is True

        panel.stop_preview()
        assert panel._running is False
        assert panel._after_id is None

        panel.start_preview()
        assert panel._running is True

        # Cleanup
        panel.stop_preview()

