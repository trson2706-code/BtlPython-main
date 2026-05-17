import unittest
from unittest.mock import patch, MagicMock
import numpy as np
from src.core.recognition import (
    FaceDetectionResult, 
    MatchResult, 
    detect_faces, 
    encode_face, 
    compare_faces,
    find_best_match,
    calculate_confidence
)

class TestRecognition(unittest.TestCase):
    def test_imports_and_types(self):
        det_result = FaceDetectionResult(top=10, right=20, bottom=30, left=10)
        self.assertEqual(det_result['top'], 10)
        
        match_result = MatchResult(is_match=True, person_id=1, person_type="student", confidence=99.5, distance=0.1)
        self.assertEqual(match_result['is_match'], True)

    def test_detect_faces_none_or_empty(self):
        self.assertIsNone(detect_faces(None))
        self.assertIsNone(detect_faces(np.array([])))
        
    @patch('src.core.recognition.face_recognition.face_locations')
    @patch('src.core.recognition.cv2.resize')
    def test_detect_faces_grayscale_support(self, mock_resize, mock_face_locations):
        # Grayscale image (100, 100)
        dummy_img = np.zeros((100, 100), dtype=np.uint8)
        mock_resize.return_value = np.zeros((25, 25, 3), dtype=np.uint8)
        mock_face_locations.return_value = [(10, 20, 20, 10)]
        result = detect_faces(dummy_img)
        self.assertIsNotNone(result)
        
    @patch('src.core.recognition.face_recognition.face_locations')
    @patch('src.core.recognition.cv2.resize')
    def test_detect_faces_scales_up_and_converts_rgb(self, mock_resize, mock_face_locations):
        # Create a dummy image
        dummy_img = np.zeros((100, 100, 3), dtype=np.uint8)
        
        # Mock resize to return the same shape to avoid issues, or a mock array
        mock_resize_output = np.zeros((25, 25, 3), dtype=np.uint8)
        mock_resize.return_value = mock_resize_output
        
        # Return a face location from the "resized" image
        # (top, right, bottom, left)
        mock_face_locations.return_value = [(10, 20, 20, 10)]
        
        result = detect_faces(dummy_img)
        
        self.assertIsNotNone(result)
        # Should scale up by 4
        self.assertEqual(result['top'], 40)
        self.assertEqual(result['right'], 80)
        self.assertEqual(result['bottom'], 80)
        self.assertEqual(result['left'], 40)
        
        # Check call args of face_locations
        # Should use model="hog"
        mock_face_locations.assert_called_once()
        _, kwargs = mock_face_locations.call_args
        self.assertEqual(kwargs.get('model'), 'hog')

    @patch('src.core.recognition.face_recognition.face_locations')
    @patch('src.core.recognition.cv2.resize')
    def test_detect_faces_largest_face(self, mock_resize, mock_face_locations):
        dummy_img = np.zeros((100, 100, 3), dtype=np.uint8)
        mock_resize.return_value = dummy_img
        
        # Return two faces: one small, one large
        # Area 1: (20-10) * (20-10) = 100
        # Area 2: (40-10) * (40-10) = 900
        mock_face_locations.return_value = [(10, 20, 20, 10), (10, 40, 40, 10)]
        
        result = detect_faces(dummy_img)
        self.assertIsNotNone(result)
        # Assuming it takes the largest face (the second one) and scales by 4
        self.assertEqual(result['top'], 40)
        self.assertEqual(result['right'], 160)
        self.assertEqual(result['bottom'], 160)
        self.assertEqual(result['left'], 40)

    @patch('src.core.recognition.face_recognition.face_encodings')
    def test_encode_face_success(self, mock_encodings):
        dummy_img = np.zeros((100, 100, 3), dtype=np.uint8)
        location = FaceDetectionResult(top=40, right=160, bottom=160, left=40)
        
        mock_enc = np.array([0.1, 0.2])
        mock_encodings.return_value = [mock_enc]
        
        result = encode_face(dummy_img, location)
        np.testing.assert_array_equal(result, mock_enc)

    @patch('src.core.recognition.face_recognition.face_encodings')
    def test_encode_face_empty(self, mock_encodings):
        dummy_img = np.zeros((100, 100, 3), dtype=np.uint8)
        location = FaceDetectionResult(top=40, right=160, bottom=160, left=40)
        
        mock_encodings.return_value = []
        result = encode_face(dummy_img, location)
        self.assertIsNone(result)

    @patch('src.core.recognition.face_recognition.face_distance')
    def test_compare_faces(self, mock_distance):
        mock_distance.return_value = np.array([0.4, 0.7])
        unknown = np.array([0.1])
        known = [np.array([0.2]), np.array([0.3])]
        
        result = compare_faces(unknown, known, 0.5)
        self.assertEqual(result, [True, False])

    def test_calculate_confidence(self):
        # 1. Exact threshold -> 50.0
        self.assertEqual(calculate_confidence(0.6, 0.6), 50.0)
        
        # 2. Perfect match (distance 0) -> 100.0
        self.assertEqual(calculate_confidence(0.0, 0.6), 100.0)
        
        # 3. Mid-range match below threshold (distance 0.3, threshold 0.6) -> 75.0
        self.assertEqual(calculate_confidence(0.3, 0.6), 75.0)
        
        # 4. Out of bounds match (distance 0.7, threshold 0.6) -> 37.5
        self.assertEqual(calculate_confidence(0.7, 0.6), 37.5)
        
        # 5. Complete mismatch (distance 1.0, threshold 0.6) -> 0.0
        self.assertEqual(calculate_confidence(1.0, 0.6), 0.0)

    @patch('src.core.recognition.compare_faces')
    @patch('src.core.recognition.face_recognition.face_distance')
    def test_find_best_match(self, mock_distance, mock_compare):
        unknown = np.array([0.1])
        known_encs = [np.array([0.2]), np.array([0.3])]
        known_meta = [{'person_id': 1, 'person_type': 'student'}, {'person_id': 2, 'person_type': 'teacher'}]
        
        mock_distance.return_value = np.array([0.65, 0.4])
        mock_compare.return_value = [False, True]
        
        result = find_best_match(unknown, known_encs, known_meta, 0.5)
        self.assertTrue(result['is_match'])
        self.assertEqual(result['person_id'], 2)
        self.assertEqual(result['person_type'], 'teacher')

    @patch('src.core.recognition.compare_faces')
    @patch('src.core.recognition.face_recognition.face_distance')
    def test_find_best_match_no_match(self, mock_distance, mock_compare):
        unknown = np.array([0.1])
        known_encs = [np.array([0.2]), np.array([0.3])]
        known_meta = [{'person_id': 1, 'person_type': 'student'}, {'person_id': 2, 'person_type': 'teacher'}]
        
        mock_distance.return_value = np.array([0.65, 0.7])
        mock_compare.return_value = [False, False]
        
        result = find_best_match(unknown, known_encs, known_meta, 0.5)
        self.assertFalse(result['is_match'])
        self.assertIsNone(result['person_id'])

if __name__ == '__main__':
    unittest.main()
