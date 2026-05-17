import unittest
from unittest.mock import patch, MagicMock
import os
from src.core.face_utils import _process_and_save_face

class TestFaceUtils(unittest.TestCase):

    @patch('src.core.face_utils.face_recognition')
    @patch('src.core.face_utils.shutil.copy')
    @patch('src.core.face_utils.os.makedirs')
    def test_process_and_save_face_success(self, mock_makedirs, mock_copy, mock_fr):
        # Setup mock for 1 face
        mock_image = MagicMock()
        mock_fr.load_image_file.return_value = mock_image
        mock_fr.face_locations.return_value = [(0, 10, 10, 0)]
        import numpy as np
        mock_enc = np.array([0.1, 0.2])
        mock_fr.face_encodings.return_value = [mock_enc]

        encoding, photo_path = _process_and_save_face('dummy/path/file.jpg', 'SV001', 'data/students')

        np.testing.assert_array_equal(encoding, mock_enc)
        self.assertEqual(photo_path, 'data/students/SV001.jpg')
        mock_makedirs.assert_called_with('data/students', exist_ok=True)
        mock_copy.assert_called_with('dummy/path/file.jpg', 'data/students/SV001.jpg')

    @patch('src.core.face_utils.face_recognition')
    def test_process_and_save_face_no_face(self, mock_fr):
        mock_fr.load_image_file.return_value = MagicMock()
        mock_fr.face_locations.return_value = []

        with self.assertRaisesRegex(ValueError, "Không nhận diện được khuôn mặt trong ảnh."):
            _process_and_save_face('dummy/path.jpg', 'SV001', 'data/students')

    @patch('src.core.face_utils.face_recognition')
    def test_process_and_save_face_multiple_faces(self, mock_fr):
        mock_fr.load_image_file.return_value = MagicMock()
        mock_fr.face_locations.return_value = [(0, 10, 10, 0), (20, 30, 30, 20)]

        with self.assertRaisesRegex(ValueError, "Phát hiện nhiều khuôn mặt, vui lòng chọn ảnh chân dung duy nhất."):
            _process_and_save_face('dummy/path.jpg', 'SV001', 'data/students')

    @patch('src.core.face_utils.face_recognition')
    def test_process_and_save_face_corrupted_image(self, mock_fr):
        mock_fr.load_image_file.side_effect = Exception("Corrupted")

        with self.assertRaisesRegex(ValueError, "Định dạng file ảnh không hợp lệ hoặc bị hỏng."):
            _process_and_save_face('dummy/path.jpg', 'SV001', 'data/students')

if __name__ == '__main__':
    unittest.main()
