import os
import logging
from src.core.face_utils import _process_and_save_face

class StudentManager:
    def __init__(self, db_manager):
        self.db_manager = db_manager
        
    def add_student(self, name, student_code, image_path):
        """
        Adds a new student by validating their face, inserting into the DB, and copying the image.
        Implements manual rollback if saving the encoding fails.
        """
        # Validate face and get encoding
        encoding, photo_path = _process_and_save_face(image_path, student_code, 'data/students')
        
        # Insert student record
        student_id = self.db_manager.add_student(name, student_code, photo_path)
        if student_id is None: # Database insertion failed
            if os.path.exists(photo_path):
                try:
                    os.remove(photo_path)
                except OSError as e:
                    logging.warning(f"Could not remove orphaned photo {photo_path}: {e}")
            raise ValueError("Không thể lưu thông tin sinh viên vào cơ sở dữ liệu.")
            
        # Insert encoding record
        encoding_id = self.db_manager.add_encoding('student', student_id, encoding)
        if encoding_id is None: # Encoding insertion failed
            # Manual rollback
            self.db_manager.delete_student(student_id)
            if os.path.exists(photo_path):
                try:
                    os.remove(photo_path)
                except OSError as e:
                    logging.warning(f"Could not remove orphaned photo {photo_path}: {e}")
            raise ValueError("Không thể lưu dữ liệu khuôn mặt vào cơ sở dữ liệu.")
            
        return self.get_student(student_id)

    def get_student(self, student_id):
        """Retrieves a student's info safely."""
        return self.db_manager.get_student(student_id)

    def get_all_students(self):
        """Retrieves all students."""
        return self.db_manager.get_all_students()

    def remove_student(self, student_id):
        """Deletes a student and cleans up their photo file."""
        student = self.db_manager.get_student(student_id)
        if not student:
            return False

        photo_path = student.get('photo_path')
        
        success = self.db_manager.delete_student(student_id)
        if success and photo_path and os.path.exists(photo_path):
            try:
                os.remove(photo_path)
            except OSError as e:
                logging.warning(f"Could not remove photo {photo_path}: {e}")
            
        return success
