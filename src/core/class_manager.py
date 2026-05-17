import os
import logging
from src.core.face_utils import _process_and_save_face

class ClassManager:
    def __init__(self, db_manager):
        self.db_manager = db_manager
        
    # --- TEACHER OPERATIONS ---

    def add_teacher(self, name, teacher_code, image_path):
        """
        Adds a new teacher by validating their face, inserting into the DB, and copying the image.
        Implements manual rollback if saving the encoding fails.
        """
        # Validate face and get encoding
        encoding, photo_path = _process_and_save_face(image_path, teacher_code, 'data/teachers')
        
        # Insert teacher record
        teacher_id = self.db_manager.add_teacher(name, teacher_code, photo_path)
        if teacher_id is None: # Database insertion failed
            if os.path.exists(photo_path):
                try:
                    os.remove(photo_path)
                except OSError as e:
                    logging.warning(f"Could not remove orphaned photo {photo_path}: {e}")
            raise ValueError("Không thể lưu thông tin giảng viên vào cơ sở dữ liệu.")
            
        # Insert encoding record
        encoding_id = self.db_manager.add_encoding('teacher', teacher_id, encoding)
        if encoding_id is None: # Encoding insertion failed
            # Manual rollback
            self.db_manager.delete_teacher(teacher_id)
            if os.path.exists(photo_path):
                try:
                    os.remove(photo_path)
                except OSError as e:
                    logging.warning(f"Could not remove orphaned photo {photo_path}: {e}")
            raise ValueError("Không thể lưu dữ liệu khuôn mặt vào cơ sở dữ liệu.")
            
        return self.get_teacher(teacher_id)

    def get_teacher(self, teacher_id):
        return self.db_manager.get_teacher(teacher_id)

    def get_all_teachers(self):
        return self.db_manager.get_all_teachers()

    def remove_teacher(self, teacher_id):
        teacher = self.db_manager.get_teacher(teacher_id)
        if not teacher:
            return False

        photo_path = teacher.get('photo_path')
        
        success = self.db_manager.delete_teacher(teacher_id)
        if success and photo_path and os.path.exists(photo_path):
            try:
                os.remove(photo_path)
            except OSError as e:
                logging.warning(f"Could not remove photo {photo_path}: {e}")
            
        return success

    # --- CLASS OPERATIONS ---

    def add_class(self, class_code, subject, teacher_id):
        class_id = self.db_manager.add_class(class_code, subject, teacher_id)
        if class_id is None:
            raise ValueError("Không thể tạo lớp học phần, có thể do trùng class_code hoặc lỗi kết nối.")
        return self.get_class(class_id)

    def get_class(self, class_id):
        return self.db_manager.get_class(class_id)

    def get_all_classes(self):
        return self.db_manager.get_all_classes()

    def get_classes_by_teacher(self, teacher_id):
        return self.db_manager.get_classes_by_teacher(teacher_id)

    def get_timetable_by_class(self, class_id):
        return self.db_manager.get_timetable_by_class(class_id)

    def delete_class(self, class_id):
        return self.db_manager.delete_class(class_id)

    # --- CLASS ENROLLMENT OPERATIONS ---

    def add_student_to_class(self, class_id, student_id):
        result = self.db_manager.add_student_to_class(class_id, student_id)
        if not result:
            raise ValueError("Không thể thêm sinh viên vào lớp. Lớp/sinh viên không tồn tại hoặc sinh viên đã ở trong lớp.")
        return result

    def remove_student_from_class(self, class_id, student_id):
        result = self.db_manager.remove_student_from_class(class_id, student_id)
        if not result:
            raise ValueError("Không thể xoá sinh viên khỏi lớp. Lớp/sinh viên không tồn tại hoặc sinh viên không thuộc lớp này.")
        return result

    def get_students_in_class(self, class_id):
        return self.db_manager.get_students_in_class(class_id)
