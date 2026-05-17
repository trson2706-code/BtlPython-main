import unittest
import os
import sqlite3
import numpy as np
from src.core.database import DatabaseManager
from src.core.config import Config

class TestDatabaseManager(unittest.TestCase):
    def setUp(self):
        self.config = Config()
        self.db_path = "data/test_attendance.db"
        if 'paths' not in self.config._data:
            self.config._data['paths'] = {}
        self.config._data['paths']['db_path'] = self.db_path
        self.db_manager = DatabaseManager()
        
    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_initialization_and_connection(self):
        self.assertTrue(os.path.exists(os.path.dirname(self.db_path)))
        conn = self.db_manager.get_connection()
        self.assertIsInstance(conn, sqlite3.Connection)
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys")
        fk = cursor.fetchone()[0]
        self.assertEqual(fk, 1)
        conn.close()

    def test_create_tables(self):
        tables = ["teachers", "classes", "students", "class_students", "face_encodings", "timetable"]
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        for table in tables:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (table,))
            self.assertIsNotNone(cursor.fetchone(), f"Table {table} was not created")
        conn.close()

    def test_teachers_crud(self):
        # Add teacher
        teacher_id = self.db_manager.add_teacher("Nguyen Van A", "GV01", "path/to/photo.jpg")
        self.assertIsNotNone(teacher_id)
        
        # Get teacher
        teacher = self.db_manager.get_teacher(teacher_id)
        self.assertIsInstance(teacher, dict)
        self.assertEqual(teacher['teacher_code'], "GV01")

        # Get all teachers
        teachers = self.db_manager.get_all_teachers()
        self.assertEqual(len(teachers), 1)

        # Add face encoding for teacher
        encoding = np.array([0.1]*128, dtype=np.float64)
        self.db_manager.add_encoding('teacher', teacher_id, encoding)

        # Ensure encoding exists
        encodings = self.db_manager.get_encodings_by_person('teacher', teacher_id)
        self.assertEqual(len(encodings), 1)

        # Delete teacher (should also delete face_encodings)
        self.db_manager.delete_teacher(teacher_id)
        self.assertIsNone(self.db_manager.get_teacher(teacher_id))
        
        # Ensure encoding is deleted
        encodings_after = self.db_manager.get_encodings_by_person('teacher', teacher_id)
        self.assertEqual(len(encodings_after), 0)

    def test_students_crud(self):
        student_id = self.db_manager.add_student("Tran B", "SV01", "path/to/student.jpg")
        self.assertIsNotNone(student_id)
        
        student = self.db_manager.get_student(student_id)
        self.assertEqual(student['student_code'], "SV01")

        student_by_code = self.db_manager.get_student_by_code("SV01")
        self.assertEqual(student_by_code['id'], student_id)

        students = self.db_manager.get_all_students()
        self.assertEqual(len(students), 1)

        # Test cascading encoding delete for student
        encoding = np.array([0.5]*128, dtype=np.float64)
        self.db_manager.add_encoding('student', student_id, encoding)
        self.db_manager.delete_student(student_id)
        
        self.assertIsNone(self.db_manager.get_student(student_id))
        self.assertEqual(len(self.db_manager.get_encodings_by_person('student', student_id)), 0)

    def test_classes_and_class_students(self):
        teacher_id = self.db_manager.add_teacher("Nguyen Van A", "GV01", "path/to/photo.jpg")
        class_id = self.db_manager.add_class("IT101", "Computer Vision", teacher_id)
        self.assertIsNotNone(class_id)

        cls = self.db_manager.get_class(class_id)
        self.assertEqual(cls['class_code'], "IT101")

        classes = self.db_manager.get_all_classes()
        self.assertEqual(len(classes), 1)

        classes_by_teacher = self.db_manager.get_classes_by_teacher(teacher_id)
        self.assertEqual(len(classes_by_teacher), 1)

        student_id1 = self.db_manager.add_student("Trinh C", "SV02", "")
        student_id2 = self.db_manager.add_student("Le D", "SV03", "")

        self.db_manager.add_student_to_class(class_id, student_id1)
        self.db_manager.add_student_to_class(class_id, student_id2)

        students_in_class = self.db_manager.get_students_in_class(class_id)
        self.assertEqual(len(students_in_class), 2)

        self.db_manager.remove_student_from_class(class_id, student_id1)
        students_in_class_after = self.db_manager.get_students_in_class(class_id)
        self.assertEqual(len(students_in_class_after), 1)

        # Test delete class deletes class_students due to cascade
        self.db_manager.delete_class(class_id)
        self.assertIsNone(self.db_manager.get_class(class_id))
        self.assertEqual(len(self.db_manager.get_students_in_class(class_id)), 0)

    def test_timetable_crud(self):
        teacher_id = self.db_manager.add_teacher("Nguyen Van A", "GV01", "path/to/photo.jpg")
        class_id = self.db_manager.add_class("IT101", "Computer Vision", teacher_id)
        
        timetable_id = self.db_manager.add_timetable(class_id, 1, "07:00", "09:00")
        self.assertIsNotNone(timetable_id)

        timetables = self.db_manager.get_timetable_by_class(class_id)
        self.assertEqual(len(timetables), 1)
        self.assertEqual(timetables[0]['day_of_week'], 1)

        self.db_manager.delete_timetable(timetable_id)
        self.assertEqual(len(self.db_manager.get_timetable_by_class(class_id)), 0)

    def test_face_encodings_crud(self):
        student_id = self.db_manager.add_student("Nguyen T", "SV04", "")
        base_encoding = np.array([0.25]*128, dtype=np.float64)
        
        encoding_id = self.db_manager.add_encoding('student', student_id, base_encoding)
        self.assertIsNotNone(encoding_id)

        student_encodings = self.db_manager.get_encodings_by_person('student', student_id)
        self.assertEqual(len(student_encodings), 1)
        
        # Test serialization
        retrieved_encoding = student_encodings[0]['encoding']
        self.assertTrue(isinstance(retrieved_encoding, np.ndarray))
        np.testing.assert_array_almost_equal(retrieved_encoding, base_encoding)

        all_student_encodings = self.db_manager.get_encodings_by_type('student')
        self.assertEqual(len(all_student_encodings), 1)

        self.db_manager.delete_encoding_by_person('student', student_id)
        self.assertEqual(len(self.db_manager.get_encodings_by_person('student', student_id)), 0)

    # ──────────────────────────────────────────────────────────
    # ATTENDANCE HISTORY TESTS (E9-S1)
    # ──────────────────────────────────────────────────────────

    def _create_session_fixtures(self):
        """Helper: tạo teacher + class + students + class_students cho test attendance history."""
        from datetime import datetime
        teacher_id = self.db_manager.add_teacher("GV Test", "GV_HIST", "")
        class_id = self.db_manager.add_class("LHP_HIST", "Test Subject", teacher_id)
        s1_id = self.db_manager.add_student("SV A", "SV_A01", "")
        s2_id = self.db_manager.add_student("SV B", "SV_B02", "")
        self.db_manager.add_student_to_class(class_id, s1_id)
        self.db_manager.add_student_to_class(class_id, s2_id)
        return teacher_id, class_id, s1_id, s2_id

    def _make_session_result(self, class_id, s1_id, s2_id, s1_present=True):
        """Helper: tạo session_result dict giống AttendanceSession.end_session()."""
        from datetime import datetime, timedelta
        now = datetime.now()
        result = {
            'class_id': class_id,
            'start_time': now - timedelta(hours=1),
            'end_time': now,
            'present': [],
            'absent': [],
        }
        if s1_present:
            result['present'].append({
                'id': s1_id,
                'student_code': 'SV_A01',
                'name': 'SV A',
                'is_present': True,
                'confidence': 0.85,
                'image_path': '/tmp/sv_a.jpg',
                'mark_time': now - timedelta(minutes=30),
            })
            result['absent'].append({
                'id': s2_id,
                'student_code': 'SV_B02',
                'name': 'SV B',
                'is_present': False,
                'confidence': 0.0,
                'image_path': None,
                'mark_time': None,
            })
        else:
            result['absent'].append({
                'id': s1_id,
                'student_code': 'SV_A01',
                'name': 'SV A',
                'is_present': False,
                'confidence': 0.0,
                'image_path': None,
                'mark_time': None,
            })
            result['absent'].append({
                'id': s2_id,
                'student_code': 'SV_B02',
                'name': 'SV B',
                'is_present': False,
                'confidence': 0.0,
                'image_path': None,
                'mark_time': None,
            })
        return result

    def test_attendance_schema_tables_exist(self):
        """Test 1: Schema — 2 bảng mới tồn tại (attendance_sessions, attendance_records)."""
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        for table in ["attendance_sessions", "attendance_records"]:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (table,))
            self.assertIsNotNone(cursor.fetchone(), f"Table {table} was not created")
        conn.close()

    def test_save_session_success_returns_id(self):
        """Test 2: save_session() — lưu thành công, return session_id."""
        teacher_id, class_id, s1_id, s2_id = self._create_session_fixtures()
        result = self._make_session_result(class_id, s1_id, s2_id)

        session_id = self.db_manager.save_session(result, teacher_id)

        self.assertIsNotNone(session_id)
        self.assertIsInstance(session_id, int)
        self.assertGreater(session_id, 0)

    def test_save_session_data_correct(self):
        """Test 3: save_session() — kiểm tra data lưu đúng (session_date, total_students, present_count)."""
        teacher_id, class_id, s1_id, s2_id = self._create_session_fixtures()
        result = self._make_session_result(class_id, s1_id, s2_id)

        session_id = self.db_manager.save_session(result, teacher_id)

        # Query raw session data
        sessions = self.db_manager.get_sessions()
        self.assertEqual(len(sessions), 1)
        s = sessions[0]
        self.assertEqual(s['class_id'], class_id)
        self.assertEqual(s['teacher_id'], teacher_id)
        self.assertEqual(s['total_students'], 2)
        self.assertEqual(s['present_count'], 1)
        self.assertIn('class_code', s)  # JOIN result
        self.assertEqual(s['class_code'], 'LHP_HIST')
        self.assertEqual(s['teacher_name'], 'GV Test')

    def test_save_session_records_present_and_absent(self):
        """Test 4: save_session() — kiểm tra attendance_records đúng (present + absent đều lưu)."""
        teacher_id, class_id, s1_id, s2_id = self._create_session_fixtures()
        result = self._make_session_result(class_id, s1_id, s2_id)

        session_id = self.db_manager.save_session(result, teacher_id)

        records = self.db_manager.get_session_records(session_id)
        self.assertEqual(len(records), 2)

        # Find present and absent records
        present_records = [r for r in records if r['is_present'] == 1]
        absent_records = [r for r in records if r['is_present'] == 0]
        self.assertEqual(len(present_records), 1)
        self.assertEqual(len(absent_records), 1)

        # Check present record data
        pr = present_records[0]
        self.assertEqual(pr['student_id'], s1_id)
        self.assertAlmostEqual(pr['confidence'], 0.85, places=2)
        self.assertIsNotNone(pr['mark_time'])
        self.assertEqual(pr['image_path'], '/tmp/sv_a.jpg')
        self.assertEqual(pr['student_code'], 'SV_A01')

        # Check absent record data
        ar = absent_records[0]
        self.assertEqual(ar['student_id'], s2_id)
        self.assertAlmostEqual(ar['confidence'], 0.0, places=2)
        self.assertIsNone(ar['mark_time'])
        self.assertIsNone(ar['image_path'])

    def test_get_sessions_all(self):
        """Test 5: get_sessions() — trả về tất cả sessions (no filter)."""
        teacher_id, class_id, s1_id, s2_id = self._create_session_fixtures()
        result = self._make_session_result(class_id, s1_id, s2_id)

        self.db_manager.save_session(result, teacher_id)
        self.db_manager.save_session(result, teacher_id)  # Second session

        sessions = self.db_manager.get_sessions()
        self.assertEqual(len(sessions), 2)

    def test_get_sessions_filter_by_class(self):
        """Test 6: get_sessions(class_id) — filter theo lớp."""
        teacher_id, class_id, s1_id, s2_id = self._create_session_fixtures()
        # Create another class
        class_id2 = self.db_manager.add_class("LHP_OTHER", "Other Subject", teacher_id)
        s3_id = self.db_manager.add_student("SV C", "SV_C03", "")
        self.db_manager.add_student_to_class(class_id2, s3_id)

        result1 = self._make_session_result(class_id, s1_id, s2_id)
        result2 = self._make_session_result(class_id2, s3_id, s3_id, s1_present=False)

        self.db_manager.save_session(result1, teacher_id)
        self.db_manager.save_session(result2, teacher_id)

        # Filter by class_id → only 1 session
        filtered = self.db_manager.get_sessions(class_id=class_id)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]['class_id'], class_id)

        # get_sessions_by_class delegate
        delegate_result = self.db_manager.get_sessions_by_class(class_id)
        self.assertEqual(len(delegate_result), 1)

    def test_get_session_records_join_student(self):
        """Test 7: get_session_records() — trả về records JOIN student info."""
        teacher_id, class_id, s1_id, s2_id = self._create_session_fixtures()
        result = self._make_session_result(class_id, s1_id, s2_id)

        session_id = self.db_manager.save_session(result, teacher_id)

        records = self.db_manager.get_session_records(session_id)
        self.assertEqual(len(records), 2)
        for r in records:
            self.assertIn('name', r)
            self.assertIn('student_code', r)

    def test_get_student_absence_count(self):
        """Test 8: get_student_absence_count() — đếm đúng số lần vắng."""
        teacher_id, class_id, s1_id, s2_id = self._create_session_fixtures()
        result = self._make_session_result(class_id, s1_id, s2_id)

        self.db_manager.save_session(result, teacher_id)

        # s2 was absent
        absence_count = self.db_manager.get_student_absence_count(s2_id)
        self.assertEqual(absence_count, 1)

        # s1 was present
        absence_count_s1 = self.db_manager.get_student_absence_count(s1_id)
        self.assertEqual(absence_count_s1, 0)

        # With class_id filter
        absence_filtered = self.db_manager.get_student_absence_count(s2_id, class_id=class_id)
        self.assertEqual(absence_filtered, 1)

        # With wrong class_id filter → 0
        absence_wrong = self.db_manager.get_student_absence_count(s2_id, class_id=9999)
        self.assertEqual(absence_wrong, 0)

    def test_cascade_delete_class_removes_sessions(self):
        """Test 9: CASCADE delete — xóa class → sessions bị xóa."""
        teacher_id, class_id, s1_id, s2_id = self._create_session_fixtures()
        result = self._make_session_result(class_id, s1_id, s2_id)

        session_id = self.db_manager.save_session(result, teacher_id)
        self.assertIsNotNone(session_id)

        # Verify session exists
        sessions = self.db_manager.get_sessions()
        self.assertEqual(len(sessions), 1)

        # Delete class → CASCADE should delete sessions
        self.db_manager.delete_class(class_id)

        # Sessions should be gone
        # Note: get_sessions uses JOIN → deleted class won't appear anyway
        # But also verify via raw query
        conn = self.db_manager.get_connection()
        cursor = conn.execute("SELECT COUNT(*) FROM attendance_sessions WHERE class_id=?", (class_id,))
        self.assertEqual(cursor.fetchone()[0], 0)
        cursor = conn.execute("SELECT COUNT(*) FROM attendance_records WHERE session_id=?", (session_id,))
        self.assertEqual(cursor.fetchone()[0], 0)
        conn.close()

    def test_save_session_empty_students(self):
        """Test 10: save_session() với session rỗng (0 students) — vẫn lưu session header."""
        teacher_id, class_id, s1_id, s2_id = self._create_session_fixtures()
        from datetime import datetime, timedelta
        now = datetime.now()
        empty_result = {
            'class_id': class_id,
            'start_time': now - timedelta(hours=1),
            'end_time': now,
            'present': [],
            'absent': [],
        }

        session_id = self.db_manager.save_session(empty_result, teacher_id)
        self.assertIsNotNone(session_id)

        sessions = self.db_manager.get_sessions()
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]['total_students'], 0)
        self.assertEqual(sessions[0]['present_count'], 0)

        # No records for empty session
        records = self.db_manager.get_session_records(session_id)
        self.assertEqual(len(records), 0)

if __name__ == '__main__':
    unittest.main()
