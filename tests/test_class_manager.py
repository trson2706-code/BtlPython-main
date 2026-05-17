import unittest
from unittest.mock import MagicMock, patch
from src.core.class_manager import ClassManager

class TestClassManager(unittest.TestCase):

    def setUp(self):
        self.mock_db = MagicMock()
        self.manager = ClassManager(self.mock_db)

    @patch('src.core.class_manager._process_and_save_face')
    def test_add_teacher_success(self, mock_process):
        mock_process.return_value = ([0.1, 0.2], 'data/teachers/GV123.jpg')
        self.mock_db.add_teacher.return_value = 1
        self.mock_db.add_encoding.return_value = 1
        self.mock_db.get_teacher.return_value = {'id': 1, 'name': 'Nguyen Van A'}

        result = self.manager.add_teacher('Nguyen Van A', 'GV123', 'dummy.jpg')
        
        self.assertEqual(result, {'id': 1, 'name': 'Nguyen Van A'})
        mock_process.assert_called_with('dummy.jpg', 'GV123', 'data/teachers')
        self.mock_db.add_teacher.assert_called_with('Nguyen Van A', 'GV123', 'data/teachers/GV123.jpg')
        self.mock_db.add_encoding.assert_called_with('teacher', 1, [0.1, 0.2])

    @patch('src.core.class_manager.os.remove')
    @patch('src.core.class_manager.os.path.exists')
    @patch('src.core.class_manager._process_and_save_face')
    def test_add_teacher_rollback_on_encoding_fail(self, mock_process, mock_exists, mock_remove):
        mock_process.return_value = ([0.1, 0.2], 'data/teachers/GV123.jpg')
        self.mock_db.add_teacher.return_value = 1
        self.mock_db.add_encoding.return_value = None # Failure
        mock_exists.return_value = True

        with self.assertRaisesRegex(ValueError, "Không thể lưu dữ liệu khuôn mặt vào cơ sở dữ liệu."):
            self.manager.add_teacher('GV', 'GV123', 'dummy.jpg')
        
        self.mock_db.delete_teacher.assert_called_with(1)
        mock_remove.assert_called_with('data/teachers/GV123.jpg')

    @patch('src.core.class_manager.os.remove')
    @patch('src.core.class_manager.os.path.exists')
    def test_remove_teacher_success(self, mock_exists, mock_remove):
        self.mock_db.get_teacher.return_value = {'id': 1, 'photo_path': 'path/to/photo.jpg'}
        self.mock_db.delete_teacher.return_value = True
        mock_exists.return_value = True

        result = self.manager.remove_teacher(1)
        
        self.assertTrue(result)
        self.mock_db.delete_teacher.assert_called_with(1)
        mock_exists.assert_called_with('path/to/photo.jpg')
        mock_remove.assert_called_with('path/to/photo.jpg')

    def test_class_crud(self):
        self.mock_db.add_class.return_value = 1
        self.mock_db.get_class.return_value = {'id': 1}

        self.assertEqual(self.manager.add_class('ML101', 'Machine Learning', 1), {'id': 1})
        self.mock_db.add_class.assert_called_with('ML101', 'Machine Learning', 1)
        
        self.mock_db.get_class.return_value = {'id': 1}
        self.assertEqual(self.manager.get_class(1), {'id': 1})
        
        self.manager.get_all_classes()
        self.mock_db.get_all_classes.assert_called_once()
        
        self.manager.get_classes_by_teacher(2)
        self.mock_db.get_classes_by_teacher.assert_called_with(2)

        self.mock_db.delete_class.return_value = True
        self.assertTrue(self.manager.delete_class(1))
        self.mock_db.delete_class.assert_called_with(1)

    def test_add_class_failure(self):
        self.mock_db.add_class.return_value = None
        with self.assertRaisesRegex(ValueError, "Không thể tạo lớp học phần, có thể do trùng class_code hoặc lỗi kết nối."):
            self.manager.add_class('ML101', 'Machine Learning', 1)
        
    def test_class_enrollment(self):
        self.mock_db.add_student_to_class.return_value = True
        self.mock_db.remove_student_from_class.return_value = True

        self.assertTrue(self.manager.add_student_to_class(1, 2))
        self.mock_db.add_student_to_class.assert_called_with(1, 2)
        
        self.assertTrue(self.manager.remove_student_from_class(1, 2))
        self.mock_db.remove_student_from_class.assert_called_with(1, 2)
        
        self.manager.get_students_in_class(1)
        self.mock_db.get_students_in_class.assert_called_with(1)

    def test_class_enrollment_failure(self):
        self.mock_db.add_student_to_class.return_value = False
        self.mock_db.remove_student_from_class.return_value = False

        with self.assertRaisesRegex(ValueError, "Không thể thêm sinh viên vào lớp. Lớp/sinh viên không tồn tại hoặc sinh viên đã ở trong lớp."):
            self.manager.add_student_to_class(1, 2)

        with self.assertRaisesRegex(ValueError, "Không thể xoá sinh viên khỏi lớp. Lớp/sinh viên không tồn tại hoặc sinh viên không thuộc lớp này."):
            self.manager.remove_student_from_class(1, 2)

if __name__ == '__main__':
    unittest.main()
