import threading
import logging
import cv2
import os
from datetime import datetime

from src.core.config import Config
from src.core.events import events, EventType
from src.core.recognition import detect_faces, encode_face, find_best_match

logger = logging.getLogger(__name__)

class RecognitionWorker(threading.Thread):
    def __init__(self, camera_manager):
        super().__init__()
        self.daemon = True
        self.camera_manager = camera_manager
        
        # State management
        self.running = False
        self.paused = True
        self.current_mode = None
        
        # Concurrency primitives
        self._lock = threading.Lock()
        self.stop_event = threading.Event()
        self.wake_event = threading.Event()
        
        # Load configuration
        config = Config()
        self.scan_interval = config.get('recognition', 'scan_interval', default=1.0)
        self.tolerance = config.get('recognition', 'tolerance', default=0.6)
        self.faces_per_frame = config.get('recognition', 'faces_per_frame', default=1)
        
        # Liveness detection (Story 10.2)
        liveness_enabled = config.get('liveness', 'enabled', default=False)
        if liveness_enabled:
            from src.core.liveness import LivenessDetector
            self.liveness_detector = LivenessDetector()
        else:
            self.liveness_detector = None
        
        # Data loaded into RAM for fast scanning
        self._known_encodings = []
        self._known_metadata = []
        
        # Prepare detections directory
        self.detections_dir = "data/detections"
        if not os.path.exists(self.detections_dir):
            os.makedirs(self.detections_dir, exist_ok=True)

    def load_encodings(self, encodings, metadata):
        """
        Loads the target face encodings into RAM.
        Expected lists of numpy arrays (encodings) and dicts (metadata)
        """
        with self._lock:
            self._known_encodings = encodings
            self._known_metadata = metadata

    def start_scanning(self, mode: int):
        """
        Start/Resume the scanning process in a specific mode.
        Mode 1: Teacher Authentication
        Mode 2: Student Attendance
        """
        with self._lock:
            self.current_mode = mode
            self.paused = False
        self.wake_event.set()

    def pause_scanning(self):
        """Pause the scanning temporarily."""
        with self._lock:
            self.paused = True
            self.wake_event.clear()

    def stop_scanning(self):
        """Gracefully stop the worker thread completely."""
        self.running = False
        self.stop_event.set()
        self.wake_event.set()

    def run(self):
        self.running = True
        
        while self.running:
            with self._lock:
                paused = self.paused
                mode = self.current_mode
                known_encodings_copy = list(self._known_encodings)
                known_metadata_copy = list(self._known_metadata)
                
            if paused or not self.camera_manager:
                # Wait for wake event or stop event without tight looping
                self.wake_event.wait(timeout=0.2)
                if self.stop_event.is_set():
                    break
                continue
                
            # Prevent race condition: do not process if the loaded DB does not match the mode
            if mode == 1 and any(m.get('person_type') != 'teacher' for m in known_metadata_copy):
                self.stop_event.wait(timeout=0.1)
                continue
            if mode == 2 and any(m.get('person_type') != 'student' for m in known_metadata_copy):
                self.stop_event.wait(timeout=0.1)
                continue
                
            # Clear wake event so that after processing, it blocks again if paused
            self.wake_event.clear()
            
            try:
                frame = self.camera_manager.get_frame()
                if frame is None:
                    continue
                    
                # Detect the largest face
                # Story specifies faces_per_frame: 1, which the current `detect_faces` supports
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
                    if encoding is not None:
                        # Compare
                        match_result = find_best_match(
                            encoding, 
                            known_encodings_copy, 
                            known_metadata_copy, 
                            self.tolerance
                        )
                        
                        if match_result and match_result.get('is_match'):
                            person_type = match_result.get('person_type')
                            
                            # Additional check depending on mode could be placed here if needed
                            
                            # Prepare result to emit
                            result_data = {
                                'person_id': match_result.get('person_id'),
                                'confidence': match_result.get('confidence'),
                                'coordinates': location
                            }
                            
                            
                            # Emit events without invoking GUI directly
                            if mode == 1:
                                events.emit(EventType.TEACHER_DETECTED, result_data)
                            elif mode == 2:
                                events.emit(EventType.STUDENT_DETECTED, result_data)
                        else:
                            # Face detected but no match → notify GUI
                            events.emit(EventType.FACE_UNRECOGNIZED, {
                                'coordinates': location
                            })
                                
            except Exception as e:
                logger.error(f"Error in recognition worker thread: {e}")
                
            # Throttle processing: wait scan_interval, but break early if stop_event is set
            if not self.paused:
                if self.stop_event.wait(timeout=self.scan_interval):
                    break
                
        logger.info("RecognitionWorker stopped cleanly.")
