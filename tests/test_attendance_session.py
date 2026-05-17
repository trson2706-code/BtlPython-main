import unittest
import threading
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
from src.core.attendance_session import AttendanceSession, SessionState, AttendanceRecord
from src.core.events import EventType

class TestAttendanceSession(unittest.TestCase):
    def setUp(self):
        self.class_manager_mock = MagicMock()
        self.session = AttendanceSession(self.class_manager_mock)

    def test_check_timetable_no_classes(self):
        self.class_manager_mock.get_classes_by_teacher.return_value = []
        with self.assertRaises(ValueError) as context:
            self.session.check_timetable(teacher_id=1)
        self.assertIn("Không có lớp học nào được phân công", str(context.exception))

    def test_check_timetable_no_match_day(self):
        mock_now = datetime(2023, 10, 23, 7, 15)  # Thứ Hai (weekday() = 0)
        self.class_manager_mock.get_classes_by_teacher.return_value = [{'id': 1}]
        self.class_manager_mock.get_timetable_by_class.return_value = [
            {'day_of_week': 1, 'start_time': '07:00'} # Tuesday
        ]
        
        with self.assertRaises(ValueError) as context:
            self.session.check_timetable(teacher_id=1, current_time=mock_now)
        self.assertIn("Không có lịch trình lớp học nào trong khoảng thời gian này", str(context.exception))
        
    def test_check_timetable_invalid_time_format(self):
        mock_now = datetime(2023, 10, 23, 7, 15)
        self.class_manager_mock.get_classes_by_teacher.return_value = [{'id': 1}]
        self.class_manager_mock.get_timetable_by_class.return_value = [
            {'day_of_week': 0, 'start_time': 'invalid-time'}
        ]
        
        with self.assertRaises(ValueError) as context:
            self.session.check_timetable(teacher_id=1, current_time=mock_now)
        self.assertIn("Không có lịch trình lớp học nào", str(context.exception))

    def test_check_timetable_success_boundary(self):
        # 30 mins early
        mock_now = datetime(2023, 10, 23, 6, 30)
        self.class_manager_mock.get_classes_by_teacher.return_value = [{'id': 1}]
        self.class_manager_mock.get_timetable_by_class.return_value = [
            {'day_of_week': 0, 'start_time': '07:00'}
        ]
        class_id = self.session.check_timetable(teacher_id=1, current_time=mock_now)
        self.assertEqual(class_id, 1)

    def test_check_timetable_fail_too_early(self):
        # 30 mins and 1 sec early
        mock_now = datetime(2023, 10, 23, 6, 29, 59)
        self.class_manager_mock.get_classes_by_teacher.return_value = [{'id': 1}]
        self.class_manager_mock.get_timetable_by_class.return_value = [
            {'day_of_week': 0, 'start_time': '07:00'}
        ]
        
        with self.assertRaises(ValueError) as context:
            self.session.check_timetable(teacher_id=1, current_time=mock_now)
        self.assertIn("Chưa đến giờ", str(context.exception))
        
    def test_check_timetable_fail_too_late(self):
        # 30 mins and 1 sec late
        mock_now = datetime(2023, 10, 23, 7, 30, 1)
        self.class_manager_mock.get_classes_by_teacher.return_value = [{'id': 1}]
        self.class_manager_mock.get_timetable_by_class.return_value = [
            {'day_of_week': 0, 'start_time': '07:00'}
        ]
        
        with self.assertRaises(ValueError) as context:
            self.session.check_timetable(teacher_id=1, current_time=mock_now)
        self.assertIn("Đã quá giờ", str(context.exception))

    @patch('src.core.attendance_session.events.emit')
    def test_start_session_success(self, mock_emit):
        student_mock = {'id': 10, 'student_code': 'SV01', 'name': 'Nguyen Van A'}
        self.class_manager_mock.get_students_in_class.return_value = [student_mock]
        
        mock_now = datetime(2023, 10, 23, 7, 15)
        self.session.start_session(class_id=1, current_time=mock_now)
        
        self.assertIsNotNone(self.session.state)
        self.assertEqual(self.session.state.class_id, 1)
        self.assertEqual(self.session.state.start_time, mock_now)
        self.assertIn(10, self.session.state.attendance_records)
        
        record = self.session.state.attendance_records[10]
        self.assertEqual(record['student_code'], 'SV01')
        self.assertFalse(record['is_present'])
        
        mock_emit.assert_called_once_with(EventType.SESSION_STARTED, {'class_id': 1, 'start_time': mock_now})

    def test_start_session_overlap(self):
        self.session.state = SessionState(class_id=1, start_time=datetime.now(), attendance_records={})
        with self.assertRaises(ValueError):
            self.session.start_session(class_id=2)

    @patch('src.core.attendance_session.events.emit')
    def test_mark_present(self, mock_emit):
        student_mock = {'id': 10, 'student_code': 'SV01', 'name': 'Nguyen Van A'}
        self.class_manager_mock.get_students_in_class.return_value = [student_mock]
        start_time = datetime(2023, 10, 23, 7, 0)
        self.session.start_session(class_id=1, current_time=start_time)
        
        mark_time = datetime(2023, 10, 23, 7, 15)
        res = self.session.mark_present(student_id=10, confidence=0.9, current_time=mark_time)
        self.assertTrue(res)
        
        record = self.session.state.attendance_records[10]
        self.assertTrue(record['is_present'])
        self.assertEqual(record['confidence'], 0.9)
        self.assertEqual(record['mark_time'], mark_time)
        mock_emit.assert_called_with(EventType.STUDENT_DETECTED, {'student_id': 10, 'class_id': 1, 'confidence': 0.9})
        
        mock_emit.reset_mock()
        res2 = self.session.mark_present(student_id=10, confidence=0.95, current_time=mark_time)
        self.assertFalse(res2)
        mock_emit.assert_not_called()

    def test_mark_present_edge_cases(self):
        student_mock = {'id': 10, 'student_code': 'SV01', 'name': 'A'}
        self.class_manager_mock.get_students_in_class.return_value = [student_mock]
        
        # Test mark when no session
        self.assertFalse(self.session.mark_present(student_id=10, confidence=0.9))
        
        start_time = datetime(2023, 10, 23, 7, 0)
        self.session.start_session(class_id=1, current_time=start_time)
        
        # Test mark non-existent student
        self.assertFalse(self.session.mark_present(student_id=99, confidence=0.9))
        
        # Test mark when expired (>= 60 mins)
        expire_time = datetime(2023, 10, 23, 8, 0) # exactly 60 minutes
        self.assertFalse(self.session.mark_present(student_id=10, confidence=0.9, current_time=expire_time))
        
        # Test is_expired method boundaries
        self.assertFalse(self.session.is_expired(current_time=datetime(2023, 10, 23, 7, 59)))
        self.assertTrue(self.session.is_expired(current_time=datetime(2023, 10, 23, 8, 00)))

    def test_get_absent_students_error(self):
        self.assertEqual(self.session.get_absent_students(), [])
        
    def test_end_session_error(self):
        with self.assertRaises(ValueError):
            self.session.end_session()

    @patch('src.core.attendance_session.events.emit')
    def test_end_session(self, mock_emit):
        s1 = {'id': 10, 'student_code': 'SV01', 'name': 'A'}
        s2 = {'id': 11, 'student_code': 'SV02', 'name': 'B'}
        self.class_manager_mock.get_students_in_class.return_value = [s1, s2]
        
        start_time = datetime(2023, 10, 23, 7, 0)
        self.session.start_session(class_id=1, current_time=start_time)
        self.session.mark_present(student_id=10, confidence=0.9, current_time=start_time)
        
        absent_list = self.session.get_absent_students()
        self.assertEqual(len(absent_list), 1)
        self.assertEqual(absent_list[0]['id'], 11)
        
        end_time = datetime(2023, 10, 23, 8, 0)
        result = self.session.end_session(current_time=end_time)
        self.assertEqual(result['end_time'], end_time)
        self.assertEqual(len(result['present']), 1)
        self.assertEqual(len(result['absent']), 1)
        
        mock_emit.assert_called_with(EventType.SESSION_ENDED, result)
        self.assertIsNone(self.session.state)

    def test_thread_safety(self):
        student_mock = {'id': 10, 'student_code': 'SV01', 'name': 'A'}
        self.class_manager_mock.get_students_in_class.return_value = [student_mock]
        self.session.start_session(class_id=1)
        
        results = []
        def worker():
            res = self.session.mark_present(student_id=10, confidence=0.9)
            results.append(res)
            
        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
            
        # Only exactly one thread should succeed in marking present
        self.assertEqual(results.count(True), 1)
        self.assertEqual(results.count(False), 9)

if __name__ == '__main__':
    unittest.main()
