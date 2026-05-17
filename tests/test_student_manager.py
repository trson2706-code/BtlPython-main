import unittest
from unittest.mock import MagicMock, patch
from src.core.student_manager import StudentManager

class TestStudentManager(unittest.TestCase):

    def setUp(self):
        self.mock_db = MagicMock()
        self.manager = StudentManager(self.mock_db)

    @patch('src.core.student_manager._process_and_save_face')
    def test_add_student_success(self, mock_process):
        mock_process.return_value = ([0.1, 0.2], 'data/students/SV123.jpg')
        self.mock_db.add_student.return_value = 1
        self.mock_db.add_encoding.return_value = 1
        self.mock_db.get_student.return_value = {'id': 1, 'name': 'Nguyen Van A'}

        result = self.manager.add_student('Nguyen Van A', 'SV123', 'dummy.jpg')
        
        self.assertEqual(result, {'id': 1, 'name': 'Nguyen Van A'})
        mock_process.assert_called_with('dummy.jpg', 'SV123', 'data/students')
        self.mock_db.add_student.assert_called_with('Nguyen Van A', 'SV123', 'data/students/SV123.jpg')
        self.mock_db.add_encoding.assert_called_with('student', 1, [0.1, 0.2])

    @patch('src.core.student_manager.os.remove')
    @patch('src.core.student_manager.os.path.exists')
    @patch('src.core.student_manager._process_and_save_face')
    def test_add_student_rollback_on_student_insert_fail(self, mock_process, mock_exists, mock_remove):
        mock_process.return_value = ([0.1, 0.2], 'data/students/SV123.jpg')
        self.mock_db.add_student.return_value = None # Failure
        mock_exists.return_value = True

        with self.assertRaisesRegex(ValueError, "Không thể lưu thông tin sinh viên vào cơ sở dữ liệu."):
            self.manager.add_student('Nguyen Van A', 'SV123', 'dummy.jpg')
        
        mock_remove.assert_called_with('data/students/SV123.jpg')

    @patch('src.core.student_manager.os.remove')
    @patch('src.core.student_manager.os.path.exists')
    @patch('src.core.student_manager._process_and_save_face')
    def test_add_student_rollback_on_encoding_insert_fail(self, mock_process, mock_exists, mock_remove):
        mock_process.return_value = ([0.1, 0.2], 'data/students/SV123.jpg')
        self.mock_db.add_student.return_value = 1
        self.mock_db.add_encoding.return_value = None # Failure
        mock_exists.return_value = True

        with self.assertRaisesRegex(ValueError, "Không thể lưu dữ liệu khuôn mặt vào cơ sở dữ liệu."):
            self.manager.add_student('Nguyen Van A', 'SV123', 'dummy.jpg')
        
        self.mock_db.delete_student.assert_called_with(1)
        mock_remove.assert_called_with('data/students/SV123.jpg')

    def test_get_student(self):
        self.mock_db.get_student.return_value = {'id': 1, 'name': 'A'}
        result = self.manager.get_student(1)
        self.assertEqual(result, {'id': 1, 'name': 'A'})
        self.mock_db.get_student.assert_called_with(1)

    def test_get_all_students(self):
        self.mock_db.get_all_students.return_value = [{'id': 1, 'name': 'A'}]
        result = self.manager.get_all_students()
        self.assertEqual(result, [{'id': 1, 'name': 'A'}])

    @patch('src.core.student_manager.os.remove')
    @patch('src.core.student_manager.os.path.exists')
    def test_remove_student_success(self, mock_exists, mock_remove):
        self.mock_db.get_student.return_value = {'id': 1, 'photo_path': 'path/to/photo.jpg'}
        self.mock_db.delete_student.return_value = True
        mock_exists.return_value = True

        result = self.manager.remove_student(1)
        
        self.assertTrue(result)
        self.mock_db.delete_student.assert_called_with(1)
        mock_exists.assert_called_with('path/to/photo.jpg')
        mock_remove.assert_called_with('path/to/photo.jpg')

    @patch('src.core.student_manager.os.remove')
    @patch('src.core.student_manager.os.path.exists')
    def test_remove_student_oserror_handled(self, mock_exists, mock_remove):
        self.mock_db.get_student.return_value = {'id': 1, 'photo_path': 'path/to/photo.jpg'}
        self.mock_db.delete_student.return_value = True
        mock_exists.return_value = True
        mock_remove.side_effect = OSError("Physical file missing or permission error")

        # Result should still be True, OSError is caught and passed
        result = self.manager.remove_student(1)
        
        self.assertTrue(result)
        self.mock_db.delete_student.assert_called_with(1)
        mock_remove.assert_called_with('path/to/photo.jpg')

if __name__ == '__main__':
    unittest.main()
