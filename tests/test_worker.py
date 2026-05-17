import pytest
import threading
import time
import numpy as np
import os
from unittest.mock import MagicMock, patch

# Note: src/core/worker.py may not exist yet in Red phase
try:
    from src.core.worker import RecognitionWorker
except ImportError:
    RecognitionWorker = None

from src.core.events import events, EventType
from src.core.config import Config

class MockCameraManager:
    def __init__(self):
        # Create a mock RGB frame
        self.frame = np.zeros((100, 100, 3), dtype=np.uint8)
        
    def get_frame(self):
        return self.frame

@pytest.fixture
def mock_config():
    Config._instance = None
    config = Config()
    config._data = {
        'recognition': {
            'scan_interval': 0.05, # Fast interval for tests
            'tolerance': 0.55
        }
    }
    # Mock get slightly differently if we want exact mocking
    yield config
    Config._instance = None

@pytest.fixture
def mock_camera():
    return MockCameraManager()

def test_worker_initialization(mock_config, mock_camera):
    if RecognitionWorker is None:
        pytest.fail("RecognitionWorker not implemented")
        
    worker = RecognitionWorker(camera_manager=mock_camera)
    assert worker.daemon is True
    assert worker.running is False
    assert worker.paused is True
    assert worker.current_mode is None

@patch('src.core.worker.detect_faces')
def test_worker_mode_1_teacher(mock_detect, mock_config, mock_camera):
    if RecognitionWorker is None:
        pytest.fail("RecognitionWorker not implemented")
        
    # Setup mock returns
    mock_detect.return_value = None # Don't actually try to find a face for now
    
    worker = RecognitionWorker(camera_manager=mock_camera)
    worker.start() # Start thread
    
    # Load teacher encodings
    mock_encoding = np.zeros(128)
    worker.load_encodings([mock_encoding], [{'person_id': 1, 'person_type': 'teacher', 'name': 'John Doe'}])
    
    worker.start_scanning(mode=1)
    assert worker.paused is False
    assert worker.current_mode == 1
    
    time.sleep(0.1) # Let the worker run a couple iterations
    
    worker.stop_scanning()
    worker.join(timeout=1.0)
    assert not worker.is_alive()
    assert mock_detect.called

@patch('src.core.worker.cv2.imwrite')
@patch('src.core.worker.find_best_match')
@patch('src.core.worker.encode_face')
@patch('src.core.worker.detect_faces')
def test_worker_successful_detection(mock_detect, mock_encode, mock_find, mock_imwrite, mock_config, mock_camera):
    if RecognitionWorker is None:
        pytest.fail("RecognitionWorker not implemented")
        
    # Setup mocks to simulate finding a face
    mock_detect.return_value = {'top': 0, 'right': 100, 'bottom': 100, 'left': 0}
    mock_encode.return_value = np.zeros(128)
    mock_find.return_value = {'is_match': True, 'person_id': 2, 'person_type': 'student', 'confidence': 99.0, 'distance': 0.1}
    
    # Capture events
    emitted_events = []
    def event_listener(data):
        emitted_events.append(data)
        
    events.subscribe(EventType.STUDENT_DETECTED, event_listener)
    
    worker = RecognitionWorker(camera_manager=mock_camera)
    worker.load_encodings([np.zeros(128)], [{'person_id': 2, 'person_type': 'student', 'name': 'Alice'}])
    
    worker.start()
    worker.start_scanning(mode=2)
    
    time.sleep(0.15) # Wait enough time for an iteration
    
    worker.stop_scanning()
    worker.join(timeout=1.0)
    
    events.unsubscribe(EventType.STUDENT_DETECTED, event_listener)
    
    # Assert
    assert mock_detect.called
    assert mock_encode.called
    assert mock_find.called
    assert mock_imwrite.called # Ensure snapshot of detection was saved
    
    assert len(emitted_events) > 0
    assert emitted_events[0]['person_id'] == 2


# ──────────────────────────────────────────────────────────
# LIVENESS INTEGRATION TESTS (Story 10.2)
# ──────────────────────────────────────────────────────────

def test_worker_init_liveness_enabled(mock_camera):
    """Test W1: Worker __init__ with liveness.enabled=true → liveness_detector is not None."""
    Config._instance = None
    try:
        config = Config()
        config._data = {
            'recognition': {'scan_interval': 0.05, 'tolerance': 0.55},
            'liveness': {'enabled': True},
        }
        # Patch the lazy import: worker.__init__() does `from src.core.liveness import LivenessDetector`
        # → patches sys.modules so the import resolves to our mock class
        mock_ld_instance = MagicMock()
        mock_liveness_module = MagicMock(
            LivenessDetector=MagicMock(return_value=mock_ld_instance)
        )
        with patch.dict('sys.modules', {'src.core.liveness': mock_liveness_module}):
            worker = RecognitionWorker(camera_manager=mock_camera)
            assert worker.liveness_detector is mock_ld_instance
    finally:
        Config._instance = None


def test_worker_init_liveness_disabled(mock_camera):
    """Test W2: Worker __init__ with liveness.enabled=false → liveness_detector is None."""
    Config._instance = None
    try:
        config = Config()
        config._data = {
            'recognition': {'scan_interval': 0.05, 'tolerance': 0.55},
            'liveness': {'enabled': False},
        }
        worker = RecognitionWorker(camera_manager=mock_camera)
        assert worker.liveness_detector is None
    finally:
        Config._instance = None


@patch('src.core.worker.encode_face')
@patch('src.core.worker.detect_faces')
def test_worker_spoof_detected_emits_event_skips_encode(mock_detect, mock_encode, mock_config, mock_camera):
    """Test W3: Spoof detected → SPOOF_DETECTED emitted, encode_face() NOT called."""
    if RecognitionWorker is None:
        pytest.fail("RecognitionWorker not implemented")

    mock_detect.return_value = {'top': 0, 'right': 100, 'bottom': 100, 'left': 0}
    mock_encode.return_value = np.zeros(128)

    # Create worker + inject mock liveness detector
    worker = RecognitionWorker(camera_manager=mock_camera)
    mock_ld = MagicMock()
    mock_ld.check_liveness.return_value = {'is_live': False, 'score': 0.3, 'details': {'texture': 0.1}}
    worker.liveness_detector = mock_ld

    # Capture SPOOF_DETECTED events
    spoof_events = []
    def on_spoof(data):
        spoof_events.append(data)
        worker.stop_scanning()  # Stop after first event

    events.subscribe(EventType.SPOOF_DETECTED, on_spoof)

    # Load fake encodings
    worker.load_encodings([np.zeros(128)], [{'person_id': 1, 'person_type': 'teacher'}])

    worker.start()
    worker.start_scanning(mode=1)
    time.sleep(0.3)
    worker.stop_scanning()
    worker.join(timeout=2.0)

    events.unsubscribe(EventType.SPOOF_DETECTED, on_spoof)

    # Assert SPOOF_DETECTED emitted
    assert len(spoof_events) > 0
    assert 'liveness_score' in spoof_events[0]
    assert spoof_events[0]['liveness_score'] == 0.3

    # encode_face should NOT have been called (spoof branch skips encoding)
    mock_ld.check_liveness.assert_called()
    mock_encode.assert_not_called()


@patch('src.core.worker.encode_face')
@patch('src.core.worker.detect_faces')
def test_worker_live_face_continues_normal_flow(mock_detect, mock_encode, mock_config, mock_camera):
    """Test W4: Live face → encode_face() IS called, SPOOF_DETECTED NOT emitted."""
    if RecognitionWorker is None:
        pytest.fail("RecognitionWorker not implemented")

    mock_detect.return_value = {'top': 0, 'right': 100, 'bottom': 100, 'left': 0}
    mock_encode.return_value = np.zeros(128)

    worker = RecognitionWorker(camera_manager=mock_camera)
    mock_ld = MagicMock()
    mock_ld.check_liveness.return_value = {'is_live': True, 'score': 0.85, 'details': {}}
    worker.liveness_detector = mock_ld

    # Track SPOOF_DETECTED events
    spoof_events = []
    def on_spoof_track(d):
        spoof_events.append(d)
    events.subscribe(EventType.SPOOF_DETECTED, on_spoof_track)

    worker.load_encodings([np.zeros(128)], [{'person_id': 1, 'person_type': 'teacher'}])
    worker.start()
    worker.start_scanning(mode=1)
    time.sleep(0.15)
    worker.stop_scanning()
    worker.join(timeout=2.0)

    events.unsubscribe(EventType.SPOOF_DETECTED, on_spoof_track)

    # encode_face MUST be called (normal flow)
    assert mock_encode.called
    # SPOOF_DETECTED should NOT be emitted
    assert len(spoof_events) == 0


@patch('src.core.worker.encode_face')
@patch('src.core.worker.detect_faces')
def test_worker_liveness_disabled_bypass(mock_detect, mock_encode, mock_config, mock_camera):
    """Test W5: Liveness disabled (liveness_detector is None) → encode_face() called normally (regression guard)."""
    if RecognitionWorker is None:
        pytest.fail("RecognitionWorker not implemented")

    mock_detect.return_value = {'top': 0, 'right': 100, 'bottom': 100, 'left': 0}
    mock_encode.return_value = np.zeros(128)

    worker = RecognitionWorker(camera_manager=mock_camera)
    # Ensure liveness disabled
    worker.liveness_detector = None

    worker.load_encodings([np.zeros(128)], [{'person_id': 1, 'person_type': 'teacher'}])
    worker.start()
    worker.start_scanning(mode=1)
    time.sleep(0.15)
    worker.stop_scanning()
    worker.join(timeout=2.0)

    # encode_face MUST be called (bypass — liveness check skipped entirely)
    assert mock_encode.called
