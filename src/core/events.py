import threading


class EventManager:
    """Hệ thống pub/sub thread-safe để tách biệt Controller và GUI.
    
    Sử dụng threading.Lock để đảm bảo an toàn khi subscribe/unsubscribe/emit
    được gọi từ nhiều threads khác nhau (GUI thread + worker thread).
    """
    
    def __init__(self):
        self._listeners = {}
        self._lock = threading.Lock()

    def subscribe(self, event_type: str, listener: callable):
        with self._lock:
            if event_type not in self._listeners:
                self._listeners[event_type] = []
            if listener not in self._listeners[event_type]:
                self._listeners[event_type].append(listener)

    def unsubscribe(self, event_type: str, listener: callable):
        with self._lock:
            if event_type in self._listeners and listener in self._listeners[event_type]:
                self._listeners[event_type].remove(listener)

    def emit(self, event_type: str, data=None):
        # Snapshot copy để tránh RuntimeError khi iterate + concurrent modification
        with self._lock:
            listeners_copy = list(self._listeners.get(event_type, []))
        for listener in listeners_copy:
            listener(data)

# Singleton event manager
events = EventManager()

# Danh sách các Event Constants
class EventType:
    TEACHER_DETECTED = "teacher_detected"
    STUDENT_DETECTED = "student_detected"
    SESSION_STARTED = "session_started"
    SESSION_ENDED = "session_ended"
    CAMERA_STOPPED = "camera_stopped"
    ERROR_OCCURRED = "error_occurred"
    SHUTDOWN_REQUESTED = "shutdown_requested"
    SESSION_CONFIRMED = "session_confirmed"
    SESSION_END_REQUESTED = "session_end_requested"
    STUDENT_ADD_REQUESTED = "student_add_requested"
    STUDENT_REMOVE_REQUESTED = "student_remove_requested"
    EXCEL_EXPORT_REQUESTED = "excel_export_requested"
    ADMIN_REQUESTED = "admin_requested"
    MANUAL_MARK_REQUESTED = "manual_mark_requested"
    FACE_UNRECOGNIZED = "face_unrecognized"
    SPOOF_DETECTED = "spoof_detected"
