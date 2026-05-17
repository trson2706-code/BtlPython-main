import cv2
import face_recognition
import numpy as np
import math
from typing import TypedDict, List, Optional, Any
import logging
from src.core.config import Config

logger = logging.getLogger(__name__)

class FaceDetectionResult(TypedDict):
    top: int
    right: int
    bottom: int
    left: int

class MatchResult(TypedDict):
    is_match: bool
    person_id: Optional[int]
    person_type: Optional[str]
    confidence: float
    distance: float

def detect_faces(image: np.ndarray) -> Optional[FaceDetectionResult]:
    if image is None or not isinstance(image, np.ndarray) or image.size == 0:
        return None
        
    try:
        if image.ndim == 2:
            rgb_frame = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
        elif image.ndim == 3 and image.shape[2] == 3:
            rgb_frame = image
        elif image.ndim == 3 and image.shape[2] == 4:
            rgb_frame = cv2.cvtColor(image, cv2.COLOR_BGRA2RGB)
        else:
            logger.error(f"Unsupported image format/shape: {image.shape}")
            return None
        
        # Resize to 1/4 for faster face detection
        rgb_small_frame = cv2.resize(rgb_frame, (0, 0), fx=0.25, fy=0.25)
        
        # Find all faces using hog model (optimized for macOS/CPU)
        face_locations = face_recognition.face_locations(rgb_small_frame, model="hog")
        
        if not face_locations:
            return None
            
        # Find largest face by area
        largest_face = None
        max_area = 0
        
        for (top, right, bottom, left) in face_locations:
            area = (bottom - top) * (right - left)
            if area > max_area:
                max_area = area
                largest_face = (top, right, bottom, left)
                
        if not largest_face:
            return None
            
        # Scale back up face locations since the frame we detected in was scaled to 1/4 size
        top, right, bottom, left = largest_face
        return FaceDetectionResult(
            top=top * 4,
            right=right * 4,
            bottom=bottom * 4,
            left=left * 4
        )
    except Exception as e:
        logger.error(f"Error in detect_faces: {e}", exc_info=True)
        return None

def encode_face(image: np.ndarray, location: FaceDetectionResult) -> Optional[np.ndarray]:
    if image is None or not isinstance(image, np.ndarray) or image.size == 0:
        return None
        
    try:
        if image.ndim == 2:
            rgb_frame = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
        elif image.ndim == 3 and image.shape[2] == 3:
            rgb_frame = image
        elif image.ndim == 3 and image.shape[2] == 4:
            rgb_frame = cv2.cvtColor(image, cv2.COLOR_BGRA2RGB)
        else:
            logger.error(f"Unsupported image format/shape in encode_face: {image.shape}")
            return None
        
        # Location needs to be a tuple of (top, right, bottom, left)
        loc_tuple = (location['top'], location['right'], location['bottom'], location['left'])
        
        encodings = face_recognition.face_encodings(rgb_frame, [loc_tuple])
        
        if encodings and len(encodings) > 0:
            return encodings[0]
            
        return None
    except Exception as e:
        logger.error(f"Error in encode_face: {e}", exc_info=True)
        return None

def compare_faces(unknown: np.ndarray, known_list: List[np.ndarray], tolerance: float) -> List[bool]:
    if not known_list:
        return []
    distances = face_recognition.face_distance(known_list, unknown)
    return list(distances <= tolerance)

def find_best_match(encoding: np.ndarray, known_encodings: List[np.ndarray], known_metadata: List[dict], tolerance: float) -> MatchResult:
    if not known_encodings or not known_metadata:
        return MatchResult(is_match=False, person_id=None, person_type=None, confidence=0.0, distance=1.0)
        
    distances = face_recognition.face_distance(known_encodings, encoding)
    best_match_index = np.argmin(distances)
    min_distance = distances[best_match_index]
    
    if min_distance <= tolerance:
        metadata = known_metadata[best_match_index]
        confidence = calculate_confidence(min_distance, tolerance)
        return MatchResult(
            is_match=True,
            person_id=metadata.get('person_id'),
            person_type=metadata.get('person_type'),
            confidence=confidence,
            distance=float(min_distance)
        )
        
    return MatchResult(
        is_match=False,
        person_id=None,
        person_type=None,
        confidence=calculate_confidence(min_distance, tolerance),
        distance=float(min_distance)
    )

def calculate_confidence(face_distance: float, face_match_threshold: float = 0.6) -> float:
    # Scale confidence 0-100%
    if face_distance > face_match_threshold:
        # 0.6 -> 0.0 distance means 50 -> 100 confidence
        # threshold -> 1.0 means 50 -> 0 confidence
        interval = 1.0 - face_match_threshold
        if interval <= 0:
            return 0.0
        val = ((1.0 - face_distance) / interval) * 50.0
    else:
        if face_match_threshold <= 0:
            return 100.0
        val = ((face_match_threshold - face_distance) / face_match_threshold) * 50.0 + 50.0
        
    return float(max(0.0, min(100.0, round(val, 2))))
