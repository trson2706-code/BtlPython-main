import logging
import threading
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, TypedDict

from src.core.events import events, EventType

logger = logging.getLogger(__name__)

class AttendanceRecord(TypedDict):
    student_code: str
    name: str
    is_present: bool
    confidence: float
    image_path: Optional[str]
    mark_time: Optional[datetime]

@dataclass
class SessionState:
    class_id: int
    start_time: datetime
    attendance_records: Dict[int, AttendanceRecord] = field(default_factory=dict)

class AttendanceSession:
    def __init__(self, class_manager):
        self.class_manager = class_manager
        self.state: Optional[SessionState] = None
        self.lock = threading.Lock()

    def check_timetable(self, teacher_id: int, current_time: datetime = None) -> int:
        now = current_time if current_time is not None else datetime.now()
        current_day = now.weekday()
        
        classes = self.class_manager.get_classes_by_teacher(teacher_id)
        if not classes:
            raise ValueError("Không có lớp học nào được phân công.")
            
        closest_future_class = None
        min_future_diff = None
        closest_past_class = None
        min_past_diff = None
        
        for c in classes:
            timetables = self.class_manager.get_timetable_by_class(c['id'])
            for t in timetables:
                if t['day_of_week'] == current_day:
                    start_str = t['start_time']
                    try:
                        time_obj = datetime.strptime(start_str, '%H:%M').time()
                        schedule_time = datetime.combine(now.date(), time_obj)
                        
                        diff_seconds = (schedule_time - now).total_seconds()
                        
                        if abs(diff_seconds) <= 1800:
                            return c['id']
                            
                        # Keep track of the minimum difference to give a better error message
                        if diff_seconds > 0:
                            if min_future_diff is None or diff_seconds < min_future_diff:
                                min_future_diff = diff_seconds
                                closest_future_class = c['id']
                        else:
                            if min_past_diff is None or abs(diff_seconds) < min_past_diff:
                                min_past_diff = abs(diff_seconds)
                                closest_past_class = c['id']
                                
                    except ValueError as e:
                        logger.error(f"Invalid time format in timetable: {start_str}")
                        continue
        
        if closest_future_class is not None:
            raise ValueError("Chưa đến giờ. Chỉ có thể điểm danh trước hoặc sau 30 phút so với giờ học.")
            
        if closest_past_class is not None:
            raise ValueError("Đã quá giờ điểm danh của lớp học hôm nay.")
        
        raise ValueError("Không có lịch trình lớp học nào trong khoảng thời gian này.")

    def start_session(self, class_id: int, current_time: datetime = None):
        now = current_time if current_time is not None else datetime.now()
        with self.lock:
            if self.state is not None:
                raise ValueError("Đã có một phiên điểm danh đang chạy. Vui lòng kết thúc trước khi bắt đầu mới.")
                
            students = self.class_manager.get_students_in_class(class_id)
            records: Dict[int, AttendanceRecord] = {}
            for student in students:
                records[student['id']] = AttendanceRecord(
                    student_code=student['student_code'],
                    name=student['name'],
                    is_present=False,
                    confidence=0.0,
                    image_path=None,
                    mark_time=None
                )
                
            self.state = SessionState(
                class_id=class_id,
                start_time=now,
                attendance_records=records
            )
            logger.info(f"Bắt đầu phiên điểm danh cho lớp {class_id} với {len(records)} sinh viên.")
            events.emit(EventType.SESSION_STARTED, {'class_id': class_id, 'start_time': self.state.start_time})

    def _is_expired(self, current_time: datetime = None) -> bool:
        if self.state is None:
            return True
        now = current_time if current_time is not None else datetime.now()
        return (now - self.state.start_time) >= timedelta(minutes=60)

    def is_expired(self, current_time: datetime = None) -> bool:
        with self.lock:
            return self._is_expired(current_time)

    def mark_present(self, student_id: int, confidence: float, image_path: str = None, current_time: datetime = None) -> bool:
        with self.lock:
            if self.state is None:
                logger.debug("mark_present failed: Không có phiên điểm danh nào đang chạy.")
                return False
                
            if self._is_expired(current_time):
                logger.debug("mark_present failed: Phiên điểm danh đã hết hạn.")
                return False
                
            record = self.state.attendance_records.get(student_id)
            if not record:
                logger.debug(f"mark_present failed: Sinh viên ID {student_id} không thuộc lớp này.")
                return False
                
            if record['is_present']:
                logger.debug(f"mark_present failed: Sinh viên ID {student_id} đã được điểm danh.")
                return False
                
            record['is_present'] = True
            record['confidence'] = confidence
            record['image_path'] = image_path
            record['mark_time'] = current_time if current_time is not None else datetime.now()
            
            events.emit(EventType.STUDENT_DETECTED, {'student_id': student_id, 'class_id': self.state.class_id, 'confidence': confidence})
            logger.debug(f"Đã điểm danh sinh viên {student_id} (độ chính xác {confidence}).")
            
            return True

    def get_absent_students(self) -> list:
        with self.lock:
            if self.state is None:
                return []
                
            absent = []
            for s_id, record in self.state.attendance_records.items():
                if not record['is_present']:
                    absent.append({'id': s_id, **record})
            return absent

    def end_session(self, current_time: datetime = None) -> dict:
        now = current_time if current_time is not None else datetime.now()
        with self.lock:
            if self.state is None:
                raise ValueError("Không có phiên điểm danh nào đang chạy.")
                
            present = []
            absent = []
            
            for s_id, record in self.state.attendance_records.items():
                student_data = {'id': s_id, **record}
                if record['is_present']:
                    present.append(student_data)
                else:
                    absent.append(student_data)
                    
            result = {
                'class_id': self.state.class_id,
                'start_time': self.state.start_time,
                'end_time': now,
                'present': present,
                'absent': absent
            }
            
            logger.info("Đã kết thúc phiên điểm danh và dọn dẹp bộ nhớ RAM.")
            events.emit(EventType.SESSION_ENDED, result)
            
            # Clear state (clean RAM)
            self.state = None
            
            return result
