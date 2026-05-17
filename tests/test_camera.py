import pytest
from unittest.mock import MagicMock, patch
import threading
import time
import numpy as np

from src.core.camera import CameraManager
from src.core.events import events, EventType

@pytest.fixture
def camera_manager():
    return CameraManager()

@patch('src.core.camera.threading.Thread')
@patch('src.core.camera.cv2.VideoCapture')
def test_camera_initialization_failure(mock_videocapture, mock_thread, camera_manager):
    # Mock VideoCapture to raise an exception or fail to open
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = False
    mock_videocapture.return_value = mock_cap
    
    # Subscribe to error event
    error_event_raised = False
    def on_error(data):
        nonlocal error_event_raised
        error_event_raised = True
    
    events.subscribe(EventType.ERROR_OCCURRED, on_error)
    
    # start() should handle failure
    camera_manager.start(camera_id=0)
    
    assert error_event_raised, "Should emit ERROR_OCCURRED when camera fails to open"
    mock_thread.assert_not_called()
    events.unsubscribe(EventType.ERROR_OCCURRED, on_error)

@patch('src.core.camera.threading.Thread')
@patch('src.core.camera.cv2.VideoCapture')
def test_camera_start_success(mock_videocapture, mock_thread, camera_manager):
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    mock_videocapture.return_value = mock_cap
    
    mock_thread_instance = MagicMock()
    mock_thread.return_value = mock_thread_instance
    
    camera_manager.start(camera_id=0)
    
    mock_videocapture.assert_called_once_with(0)
    mock_thread.assert_called_once()
    mock_thread_instance.start.assert_called_once()

@patch('src.core.camera.cv2.VideoCapture')
def test_camera_runtime_disruption(mock_videocapture, camera_manager):
    # This test will run the actual thread but mock VideoCapture
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    
    # read() returns False meaning connection lost. Sleep to simulate i/o
    def mock_read():
        time.sleep(0.01)
        return (False, None)
    mock_cap.read.side_effect = mock_read
    mock_videocapture.return_value = mock_cap
    
    error_event_raised = False
    stopped_event_raised = False
    
    def on_error(data):
        nonlocal error_event_raised
        error_event_raised = True
        
    def on_stopped(data):
        nonlocal stopped_event_raised
        stopped_event_raised = True
        
    events.subscribe(EventType.ERROR_OCCURRED, on_error)
    events.subscribe(EventType.CAMERA_STOPPED, on_stopped)
    
    camera_manager.start(camera_id=0)
    
    # Give the thread some time to run and fail
    time.sleep(0.1)
    
    assert error_event_raised, "Should emit ERROR_OCCURRED on runtime disruption"
    assert stopped_event_raised, "Should emit CAMERA_STOPPED on runtime disruption"
    
    events.unsubscribe(EventType.ERROR_OCCURRED, on_error)
    events.unsubscribe(EventType.CAMERA_STOPPED, on_stopped)

@patch('src.core.camera.cv2.VideoCapture')
@patch('src.core.camera.cv2.cvtColor')
def test_get_frame_thread_safe(mock_cvtcolor, mock_videocapture, camera_manager):
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    
    # Mock a frame
    fake_bgr_frame = np.zeros((100, 100, 3), dtype=np.uint8)
    fake_rgb_frame = np.ones((100, 100, 3), dtype=np.uint8)
    
    # Throttle read speed to avoid 100% CPU lock in test thread
    def mock_read():
        time.sleep(0.01)
        return (True, fake_bgr_frame)
    
    mock_cap.read.side_effect = mock_read
    mock_videocapture.return_value = mock_cap
    mock_cvtcolor.return_value = fake_rgb_frame
    
    camera_manager.start(camera_id=0)
    
    # Give the thread some time to read a frame
    time.sleep(0.1)
    
    # Retrieve frame
    frame = camera_manager.get_frame()
    
    assert frame is not None
    assert np.array_equal(frame, fake_rgb_frame)
    
    camera_manager.stop()
