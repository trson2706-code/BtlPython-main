import os
import sqlite3
import logging
import numpy as np
from contextlib import closing
from datetime import datetime
from src.core.config import Config

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self):
        config = Config()
        self.db_path = config.get('paths', 'db_path', default="data/attendance.db")
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self.create_tables()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def create_tables(self):
        schema = """
        CREATE TABLE IF NOT EXISTS teachers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            teacher_code TEXT UNIQUE NOT NULL,
            photo_path TEXT,
            added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS classes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_code TEXT UNIQUE NOT NULL,
            subject TEXT NOT NULL,
            teacher_id INTEGER,
            FOREIGN KEY (teacher_id) REFERENCES teachers (id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            student_code TEXT UNIQUE NOT NULL,
            photo_path TEXT,
            added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS class_students (
            class_id INTEGER,
            student_id INTEGER,
            PRIMARY KEY (class_id, student_id),
            FOREIGN KEY (class_id) REFERENCES classes (id) ON DELETE CASCADE,
            FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS face_encodings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_type TEXT NOT NULL, -- 'student' or 'teacher'
            person_id INTEGER NOT NULL,
            encoding BLOB NOT NULL
        );

        CREATE TABLE IF NOT EXISTS timetable (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_id INTEGER NOT NULL,
            day_of_week INTEGER NOT NULL, -- 0-6 cho Thứ 2 - Chủ Nhật
            start_time TEXT NOT NULL, -- Format 'HH:MM'
            end_time TEXT NOT NULL, -- Format 'HH:MM'
            FOREIGN KEY (class_id) REFERENCES classes (id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS attendance_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_id INTEGER NOT NULL,
            teacher_id INTEGER NOT NULL,
            session_date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            total_students INTEGER NOT NULL DEFAULT 0,
            present_count INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (class_id) REFERENCES classes (id) ON DELETE CASCADE,
            FOREIGN KEY (teacher_id) REFERENCES teachers (id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS attendance_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            is_present INTEGER NOT NULL DEFAULT 0,
            confidence REAL DEFAULT 0.0,
            mark_time TEXT,
            image_path TEXT,
            FOREIGN KEY (session_id) REFERENCES attendance_sessions (id) ON DELETE CASCADE,
            FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE
        );
        """
        try:
            with closing(self.get_connection()) as conn:
                with conn:
                    conn.executescript(schema)
        except sqlite3.OperationalError as e:
            logger.error(f"Database Locked or Operational Error during 'creating tables': {e}")
        except sqlite3.Error as e:
            logger.error(f"Error creating tables: {e}")

    def _row_to_dict(self, row):
        if row is None:
            return None
        d = dict(row)
        if 'encoding' in d and d['encoding']:
            d['encoding'] = np.frombuffer(d['encoding'], dtype=np.float64)
        return d

    def _rows_to_list(self, rows):
        return [self._row_to_dict(r) for r in rows]

    # --- TEACHERS CRUD ---

    def add_teacher(self, name, teacher_code, photo_path):
        try:
            with closing(self.get_connection()) as conn:
                with conn:
                    cursor = conn.execute(
                        "INSERT INTO teachers (name, teacher_code, photo_path) VALUES (?, ?, ?)",
                        (name, teacher_code, photo_path)
                    )
                    return cursor.lastrowid
        except sqlite3.OperationalError as e:
            logger.error(f"Database Locked or Operational Error during 'adding teacher': {e}")
        except sqlite3.Error as e:
            logger.error(f"Error adding teacher: {e}")
            return None

    def get_teacher(self, teacher_id):
        try:
            with closing(self.get_connection()) as conn:
                cursor = conn.execute("SELECT * FROM teachers WHERE id = ?", (teacher_id,))
                return self._row_to_dict(cursor.fetchone())
        except sqlite3.OperationalError as e:
            logger.error(f"Database Locked or Operational Error during 'getting teacher': {e}")
        except sqlite3.Error as e:
            logger.error(f"Error getting teacher: {e}")
            return None

    def get_all_teachers(self):
        try:
            with closing(self.get_connection()) as conn:
                cursor = conn.execute("SELECT * FROM teachers")
                return self._rows_to_list(cursor.fetchall())
        except sqlite3.OperationalError as e:
            logger.error(f"Database Locked or Operational Error during 'getting all teachers': {e}")
        except sqlite3.Error as e:
            logger.error(f"Error getting all teachers: {e}")
            return []

    def delete_teacher(self, teacher_id):
        try:
            with closing(self.get_connection()) as conn:
                with conn:
                    conn.execute("DELETE FROM face_encodings WHERE person_type=? AND person_id=?", ('teacher', teacher_id))
                    cursor = conn.execute("DELETE FROM teachers WHERE id=?", (teacher_id,))
                    if cursor.rowcount == 0:
                        return False
                return True
        except sqlite3.OperationalError as e:
            logger.error(f"Database Locked or Operational Error during 'deleting teacher': {e}")
        except sqlite3.Error as e:
            logger.error(f"Error deleting teacher: {e}")
            return False

    # --- STUDENTS CRUD ---

    def add_student(self, name, student_code, photo_path):
        try:
            with closing(self.get_connection()) as conn:
                with conn:
                    cursor = conn.execute(
                        "INSERT INTO students (name, student_code, photo_path) VALUES (?, ?, ?)",
                        (name, student_code, photo_path)
                    )
                    return cursor.lastrowid
        except sqlite3.OperationalError as e:
            logger.error(f"Database Locked or Operational Error during 'adding student': {e}")
        except sqlite3.Error as e:
            logger.error(f"Error adding student: {e}")
            return None

    def get_student(self, student_id):
        try:
            with closing(self.get_connection()) as conn:
                cursor = conn.execute("SELECT * FROM students WHERE id = ?", (student_id,))
                return self._row_to_dict(cursor.fetchone())
        except sqlite3.OperationalError as e:
            logger.error(f"Database Locked or Operational Error during 'getting student': {e}")
        except sqlite3.Error as e:
            logger.error(f"Error getting student: {e}")
            return None

    def get_student_by_code(self, student_code):
        try:
            with closing(self.get_connection()) as conn:
                cursor = conn.execute("SELECT * FROM students WHERE student_code = ?", (student_code,))
                return self._row_to_dict(cursor.fetchone())
        except sqlite3.OperationalError as e:
            logger.error(f"Database Locked or Operational Error during 'getting student by code': {e}")
        except sqlite3.Error as e:
            logger.error(f"Error getting student by code: {e}")
            return None

    def get_all_students(self):
        try:
            with closing(self.get_connection()) as conn:
                cursor = conn.execute("SELECT * FROM students")
                return self._rows_to_list(cursor.fetchall())
        except sqlite3.OperationalError as e:
            logger.error(f"Database Locked or Operational Error during 'getting all students': {e}")
        except sqlite3.Error as e:
            logger.error(f"Error getting all students: {e}")
            return []

    def delete_student(self, student_id):
        try:
            with closing(self.get_connection()) as conn:
                with conn:
                    conn.execute("DELETE FROM face_encodings WHERE person_type=? AND person_id=?", ('student', student_id))
                    cursor = conn.execute("DELETE FROM students WHERE id=?", (student_id,))
                    if cursor.rowcount == 0:
                        return False
                return True
        except sqlite3.OperationalError as e:
            logger.error(f"Database Locked or Operational Error during 'deleting student': {e}")
        except sqlite3.Error as e:
            logger.error(f"Error deleting student: {e}")
            return False

    # --- CLASSES CRUD ---

    def add_class(self, class_code, subject, teacher_id):
        try:
            with closing(self.get_connection()) as conn:
                with conn:
                    cursor = conn.execute(
                        "INSERT INTO classes (class_code, subject, teacher_id) VALUES (?, ?, ?)",
                        (class_code, subject, teacher_id)
                    )
                    return cursor.lastrowid
        except sqlite3.OperationalError as e:
            logger.error(f"Database Locked or Operational Error during 'adding class': {e}")
        except sqlite3.Error as e:
            logger.error(f"Error adding class: {e}")
            return None

    def get_class(self, class_id):
        try:
            with closing(self.get_connection()) as conn:
                cursor = conn.execute("SELECT * FROM classes WHERE id = ?", (class_id,))
                return self._row_to_dict(cursor.fetchone())
        except sqlite3.OperationalError as e:
            logger.error(f"Database Locked or Operational Error during 'getting class': {e}")
        except sqlite3.Error as e:
            logger.error(f"Error getting class: {e}")
            return None

    def get_all_classes(self):
        try:
            with closing(self.get_connection()) as conn:
                cursor = conn.execute("SELECT * FROM classes")
                return self._rows_to_list(cursor.fetchall())
        except sqlite3.OperationalError as e:
            logger.error(f"Database Locked or Operational Error during 'getting all classes': {e}")
        except sqlite3.Error as e:
            logger.error(f"Error getting all classes: {e}")
            return []

    def get_classes_by_teacher(self, teacher_id):
        try:
            with closing(self.get_connection()) as conn:
                cursor = conn.execute("SELECT * FROM classes WHERE teacher_id = ?", (teacher_id,))
                return self._rows_to_list(cursor.fetchall())
        except sqlite3.OperationalError as e:
            logger.error(f"Database Locked or Operational Error during 'getting classes by teacher': {e}")
        except sqlite3.Error as e:
            logger.error(f"Error getting classes by teacher: {e}")
            return []

    def delete_class(self, class_id):
        try:
            with closing(self.get_connection()) as conn:
                with conn:
                    cursor = conn.execute("DELETE FROM classes WHERE id=?", (class_id,))
                    if cursor.rowcount == 0:
                        return False
                return True
        except sqlite3.OperationalError as e:
            logger.error(f"Database Locked or Operational Error during 'deleting class': {e}")
        except sqlite3.Error as e:
            logger.error(f"Error deleting class: {e}")
            return False

    # --- CLASS_STUDENTS CRUD ---

    def add_student_to_class(self, class_id, student_id):
        try:
            with closing(self.get_connection()) as conn:
                with conn:
                    conn.execute("INSERT OR IGNORE INTO class_students (class_id, student_id) VALUES (?, ?)", (class_id, student_id))
                return True
        except sqlite3.OperationalError as e:
            logger.error(f"Database Locked or Operational Error during 'adding student to class': {e}")
        except sqlite3.Error as e:
            logger.error(f"Error adding student to class: {e}")
            return False

    def remove_student_from_class(self, class_id, student_id):
        try:
            with closing(self.get_connection()) as conn:
                with conn:
                    cursor = conn.execute("DELETE FROM class_students WHERE class_id=? AND student_id=?", (class_id, student_id))
                    if cursor.rowcount == 0:
                        return False
                return True
        except sqlite3.OperationalError as e:
            logger.error(f"Database Locked or Operational Error during 'removing student from class': {e}")
        except sqlite3.Error as e:
            logger.error(f"Error removing student from class: {e}")
            return False

    def get_students_in_class(self, class_id):
        try:
            with closing(self.get_connection()) as conn:
                cursor = conn.execute(
                    "SELECT s.* FROM students s JOIN class_students cs ON s.id = cs.student_id WHERE cs.class_id = ?",
                    (class_id,)
                )
                return self._rows_to_list(cursor.fetchall())
        except sqlite3.OperationalError as e:
            logger.error(f"Database Locked or Operational Error during 'getting students in class': {e}")
        except sqlite3.Error as e:
            logger.error(f"Error getting students in class: {e}")
            return []

    # --- FACE ENCODINGS CRUD ---

    def add_encoding(self, person_type, person_id, encoding_array):
        try:
            with closing(self.get_connection()) as conn:
                with conn:
                    cursor = conn.execute(
                        "INSERT INTO face_encodings (person_type, person_id, encoding) VALUES (?, ?, ?)",
                        (person_type, person_id, np.array(encoding_array).tobytes())
                    )
                    return cursor.lastrowid
        except sqlite3.OperationalError as e:
            logger.error(f"Database Locked or Operational Error during 'adding face encoding': {e}")
        except sqlite3.Error as e:
            logger.error(f"Error adding face encoding: {e}")
            return None

    def get_encodings_by_person(self, person_type, person_id):
        try:
            with closing(self.get_connection()) as conn:
                cursor = conn.execute(
                    "SELECT * FROM face_encodings WHERE person_type=? AND person_id=?",
                    (person_type, person_id)
                )
                return self._rows_to_list(cursor.fetchall())
        except sqlite3.OperationalError as e:
            logger.error(f"Database Locked or Operational Error during 'getting encodings by person': {e}")
        except sqlite3.Error as e:
            logger.error(f"Error getting encodings by person: {e}")
            return []

    def get_encodings_by_type(self, person_type):
        try:
            with closing(self.get_connection()) as conn:
                cursor = conn.execute("SELECT * FROM face_encodings WHERE person_type=?", (person_type,))
                return self._rows_to_list(cursor.fetchall())
        except sqlite3.OperationalError as e:
            logger.error(f"Database Locked or Operational Error during 'getting encodings by type': {e}")
        except sqlite3.Error as e:
            logger.error(f"Error getting encodings by type: {e}")
            return []

    def delete_encoding_by_person(self, person_type, person_id):
        try:
            with closing(self.get_connection()) as conn:
                with conn:
                    cursor = conn.execute("DELETE FROM face_encodings WHERE person_type=? AND person_id=?", (person_type, person_id))
                    if cursor.rowcount == 0:
                        return False
                return True
        except sqlite3.OperationalError as e:
            logger.error(f"Database Locked or Operational Error during 'deleting encoding by person': {e}")
        except sqlite3.Error as e:
            logger.error(f"Error deleting encoding by person: {e}")
            return False

    # --- TIMETABLE CRUD ---

    def add_timetable(self, class_id, day_of_week, start_time, end_time):
        try:
            with closing(self.get_connection()) as conn:
                with conn:
                    cursor = conn.execute(
                        "INSERT INTO timetable (class_id, day_of_week, start_time, end_time) VALUES (?, ?, ?, ?)",
                        (class_id, day_of_week, start_time, end_time)
                    )
                    return cursor.lastrowid
        except sqlite3.OperationalError as e:
            logger.error(f"Database Locked or Operational Error during 'adding timetable': {e}")
        except sqlite3.Error as e:
            logger.error(f"Error adding timetable: {e}")
            return None

    def get_timetable_by_class(self, class_id):
        try:
            with closing(self.get_connection()) as conn:
                cursor = conn.execute("SELECT * FROM timetable WHERE class_id=?", (class_id,))
                return self._rows_to_list(cursor.fetchall())
        except sqlite3.OperationalError as e:
            logger.error(f"Database Locked or Operational Error during 'getting timetable by class': {e}")
        except sqlite3.Error as e:
            logger.error(f"Error getting timetable by class: {e}")
            return []

    def get_all_timetable(self):
        try:
            with closing(self.get_connection()) as conn:
                cursor = conn.execute(
                    "SELECT t.*, c.class_code, c.subject FROM timetable t "
                    "JOIN classes c ON t.class_id = c.id"
                )
                return self._rows_to_list(cursor.fetchall())
        except sqlite3.OperationalError as e:
            logger.error(f"Database Locked or Operational Error during 'getting all timetable': {e}")
        except sqlite3.Error as e:
            logger.error(f"Error getting all timetable: {e}")
            return []

    def update_timetable(self, timetable_id, day_of_week, start_time, end_time):
        """Update an existing timetable entry."""
        try:
            with closing(self.get_connection()) as conn:
                with conn:
                    cursor = conn.execute(
                        "UPDATE timetable SET day_of_week=?, start_time=?, end_time=? WHERE id=?",
                        (day_of_week, start_time, end_time, timetable_id)
                    )
                    if cursor.rowcount == 0:
                        return False
                return True
        except sqlite3.OperationalError as e:
            logger.error(f"Database Locked or Operational Error during 'updating timetable': {e}")
        except sqlite3.Error as e:
            logger.error(f"Error updating timetable: {e}")
            return False

    def delete_timetable(self, timetable_id):
        try:
            with closing(self.get_connection()) as conn:
                with conn:
                    cursor = conn.execute("DELETE FROM timetable WHERE id=?", (timetable_id,))
                    if cursor.rowcount == 0:
                        return False
                return True
        except sqlite3.OperationalError as e:
            logger.error(f"Database Locked or Operational Error during 'deleting timetable': {e}")
        except sqlite3.Error as e:
            logger.error(f"Error deleting timetable: {e}")
            return False

    # --- ATTENDANCE HISTORY CRUD ---

    def save_session(self, session_result, teacher_id):
        """Lưu kết quả session vào DB (atomic transaction).

        Args:
            session_result: dict từ AttendanceSession.end_session()
            teacher_id: ID giảng viên chủ trì phiên

        Returns:
            session_id (int) nếu thành công, None nếu lỗi
        """
        try:
            with closing(self.get_connection()) as conn:
                with conn:  # Auto-commit/rollback
                    # 1. Extract metadata
                    class_id = session_result['class_id']
                    start_time = session_result['start_time']
                    end_time = session_result['end_time']
                    present_list = session_result.get('present') or []
                    absent_list = session_result.get('absent') or []
                    total_students = len(present_list) + len(absent_list)
                    present_count = len(present_list)

                    # datetime → TEXT conversion
                    session_date = start_time.strftime('%Y-%m-%d')
                    start_time_str = start_time.strftime('%Y-%m-%d %H:%M:%S')
                    end_time_str = end_time.strftime('%Y-%m-%d %H:%M:%S')

                    # 2. INSERT session header
                    cursor = conn.execute(
                        "INSERT INTO attendance_sessions "
                        "(class_id, teacher_id, session_date, start_time, end_time, total_students, present_count) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (class_id, teacher_id, session_date, start_time_str, end_time_str, total_students, present_count)
                    )
                    session_id = cursor.lastrowid

                    # 3. BATCH INSERT records (present + absent)
                    all_students = list(present_list) + list(absent_list)
                    records = []
                    for s in all_students:
                        mark_time_val = s.get('mark_time')
                        if mark_time_val and isinstance(mark_time_val, datetime):
                            mark_time_val = mark_time_val.strftime('%Y-%m-%d %H:%M:%S')
                        elif mark_time_val is not None and not isinstance(mark_time_val, str):
                            mark_time_val = str(mark_time_val)
                        records.append((
                            session_id, s['id'],
                            1 if s.get('is_present') else 0,
                            s.get('confidence', 0.0),
                            mark_time_val,
                            s.get('image_path')
                        ))
                    if records:
                        conn.executemany(
                            "INSERT INTO attendance_records "
                            "(session_id, student_id, is_present, confidence, mark_time, image_path) "
                            "VALUES (?, ?, ?, ?, ?, ?)",
                            records
                        )
                    return session_id
        except sqlite3.OperationalError as e:
            logger.error(f"Database Locked or Operational Error during 'saving session': {e}")
            return None
        except sqlite3.Error as e:
            logger.error(f"Error saving session: {e}")
            return None

    def get_sessions(self, class_id=None):
        """Trả về danh sách sessions, JOIN classes + teachers.

        Args:
            class_id: nếu None → tất cả sessions, nếu có → filter theo lớp

        Returns:
            list of dicts
        """
        try:
            with closing(self.get_connection()) as conn:
                sql = (
                    "SELECT s.*, c.class_code, c.subject, t.name as teacher_name "
                    "FROM attendance_sessions s "
                    "JOIN classes c ON s.class_id = c.id "
                    "JOIN teachers t ON s.teacher_id = t.id"
                )
                if class_id is not None:
                    sql += " WHERE s.class_id = ?"
                    sql += " ORDER BY s.session_date DESC, s.start_time DESC"
                    cursor = conn.execute(sql, (class_id,))
                else:
                    sql += " ORDER BY s.session_date DESC, s.start_time DESC"
                    cursor = conn.execute(sql)
                return self._rows_to_list(cursor.fetchall())
        except sqlite3.OperationalError as e:
            logger.error(f"Database Locked or Operational Error during 'getting sessions': {e}")
            return []
        except sqlite3.Error as e:
            logger.error(f"Error getting sessions: {e}")
            return []

    def get_session_records(self, session_id):
        """Trả về danh sách records cho session, JOIN students.

        Args:
            session_id: ID của session

        Returns:
            list of dicts
        """
        try:
            with closing(self.get_connection()) as conn:
                cursor = conn.execute(
                    "SELECT r.*, st.name, st.student_code "
                    "FROM attendance_records r "
                    "JOIN students st ON r.student_id = st.id "
                    "WHERE r.session_id = ? "
                    "ORDER BY st.student_code ASC",
                    (session_id,)
                )
                return self._rows_to_list(cursor.fetchall())
        except sqlite3.OperationalError as e:
            logger.error(f"Database Locked or Operational Error during 'getting session records': {e}")
            return []
        except sqlite3.Error as e:
            logger.error(f"Error getting session records: {e}")
            return []

    def get_student_absence_count(self, student_id, class_id=None):
        """Đếm số lần vắng mặt của sinh viên.

        Args:
            student_id: ID sinh viên
            class_id: nếu có → chỉ đếm trong lớp đó

        Returns:
            int (0 nếu lỗi)
        """
        try:
            with closing(self.get_connection()) as conn:
                sql = (
                    "SELECT COUNT(*) FROM attendance_records r "
                    "JOIN attendance_sessions s ON r.session_id = s.id "
                    "WHERE r.student_id = ? AND r.is_present = 0"
                )
                params = [student_id]
                if class_id is not None:
                    sql += " AND s.class_id = ?"
                    params.append(class_id)
                cursor = conn.execute(sql, params)
                return cursor.fetchone()[0]
        except sqlite3.OperationalError as e:
            logger.error(f"Database Locked or Operational Error during 'getting absence count': {e}")
        except sqlite3.Error as e:
            logger.error(f"Error getting absence count: {e}")
            return 0

    def get_sessions_by_class(self, class_id):
        """Shortcut cho get_sessions(class_id=class_id)."""
        return self.get_sessions(class_id=class_id)
