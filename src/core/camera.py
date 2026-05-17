import os
import cv2
import threading
import logging
import time

from src.core.events import events, EventType

logger = logging.getLogger(__name__)

class CameraManager:
    def __init__(self):
        self.cap = None
        self._latest_frame = None
        self._is_running = False
        self._thread = None
        self._lock = threading.Lock()
        self._camera_stopped_emitted = False

    def start(self, camera_id=None):
        if self._is_running:
            return

        # Retrieve settings from environment if not explicitly provided
        if camera_id is None:
            camera_id = int(os.environ.get("CAMERA_ID", "0"))

        self._camera_stopped_emitted = False

        try:
            self.cap = cv2.VideoCapture(camera_id)
        except Exception as e:
            logger.error(f"Failed to initialize VideoCapture: {e}")
            events.emit(EventType.ERROR_OCCURRED, str(e))
            return

        if not self.cap or not self.cap.isOpened():
            msg = f"Failed to open camera {camera_id}"
            logger.error(msg)
            events.emit(EventType.ERROR_OCCURRED, msg)
            if self.cap:
                self.cap.release()
                self.cap = None
            return

        self._is_running = True
        self._thread = threading.Thread(target=self._update_frame, daemon=True)
        self._thread.start()

    def stop(self):
        if not self._is_running and not self.cap and not self._thread:
            return
            
        self._is_running = False
        
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
            
        with self._lock:
            if self.cap and (not self._thread or not self._thread.is_alive()):
                self.cap.release()
                self.cap = None
                
            if not self._camera_stopped_emitted:
                events.emit(EventType.CAMERA_STOPPED)
                self._camera_stopped_emitted = True

    def _update_frame(self):
        while self._is_running:
            try:
                ret, frame = self.cap.read()
                if not ret:
                    msg = "Camera connection lost (cap.read() returned False)"
                    logger.error(msg)
                    events.emit(EventType.ERROR_OCCURRED, msg)
                    break
                    
                frame = cv2.flip(frame, 1)  # Mirror (lật ngang)
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                with self._lock:
                    self._latest_frame = rgb_frame
            except Exception as e:
                msg = f"Exception reading from camera: {e}"
                logger.error(msg)
                events.emit(EventType.ERROR_OCCURRED, msg)
                break

            # Throttle ~30fps — tránh CPU 100% do tight loop
            time.sleep(0.03)

        # Graceful cleanup strictly on the thread accessing cv2
        self._is_running = False
        with self._lock:
            if self.cap:
                self.cap.release()
                self.cap = None
            if not self._camera_stopped_emitted:
                events.emit(EventType.CAMERA_STOPPED)
                self._camera_stopped_emitted = True

    def get_frame(self):
        with self._lock:
            if self._latest_frame is not None:
                return self._latest_frame.copy()
            return None

    def is_opened(self):
        """Check if camera is currently running and capturing frames.

        [CR-F7] Thread-safe: acquires _lock to prevent TOCTOU race with
        _update_frame() cleanup path that sets _is_running=False + cap=None.
        """
        with self._lock:
            return self._is_running and self.cap is not None
