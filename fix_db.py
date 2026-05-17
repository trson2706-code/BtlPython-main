import re

with open('src/core/database.py', 'r') as f:
    content = f.read()

# Fix __init__ path issue
old_init = """    def __init__(self):
        config = Config()
        self.db_path = config.get('paths', 'db_path', default="data/attendance.db")
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.create_tables()"""

new_init = """    def __init__(self):
        config = Config()
        self.db_path = config.get('paths', 'db_path', default="data/attendance.db")
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self.create_tables()"""

content = content.replace(old_init, new_init)

# Fix add_encoding tobytes issue
old_add_enc = """                        "INSERT INTO face_encodings (person_type, person_id, encoding) VALUES (?, ?, ?)",
                        (person_type, person_id, encoding_array.tobytes())"""
new_add_enc = """                        "INSERT INTO face_encodings (person_type, person_id, encoding) VALUES (?, ?, ?)",
                        (person_type, person_id, np.array(encoding_array).tobytes())"""
content = content.replace(old_add_enc, new_add_enc)

# Fix missing rowcount checks
def replace_delete_rowcount(table, method, delete_stmt):
    old = f"""                    conn.execute("{delete_stmt}")
                return True"""
    new = f"""                    cursor = conn.execute("{delete_stmt}")
                    if cursor.rowcount == 0:
                        return False
                return True"""
    return content.replace(old, new)

content = replace_delete_rowcount("teachers", "delete_teacher", "DELETE FROM teachers WHERE id=?, (teacher_id,)") # Wait, it uses (teacher_id,) string literal inside replace. Let's do it manually.

old_del_teacher = """                    conn.execute("DELETE FROM face_encodings WHERE person_type=? AND person_id=?", ('teacher', teacher_id))
                    conn.execute("DELETE FROM teachers WHERE id=?", (teacher_id,))
                return True"""
new_del_teacher = """                    conn.execute("DELETE FROM face_encodings WHERE person_type=? AND person_id=?", ('teacher', teacher_id))
                    cursor = conn.execute("DELETE FROM teachers WHERE id=?", (teacher_id,))
                    if cursor.rowcount == 0:
                        return False
                return True"""
content = content.replace(old_del_teacher, new_del_teacher)

old_del_student = """                    conn.execute("DELETE FROM face_encodings WHERE person_type=? AND person_id=?", ('student', student_id))
                    conn.execute("DELETE FROM students WHERE id=?", (student_id,))
                return True"""
new_del_student = """                    conn.execute("DELETE FROM face_encodings WHERE person_type=? AND person_id=?", ('student', student_id))
                    cursor = conn.execute("DELETE FROM students WHERE id=?", (student_id,))
                    if cursor.rowcount == 0:
                        return False
                return True"""
content = content.replace(old_del_student, new_del_student)

old_del_class = """                    conn.execute("DELETE FROM classes WHERE id=?", (class_id,))
                return True"""
new_del_class = """                    cursor = conn.execute("DELETE FROM classes WHERE id=?", (class_id,))
                    if cursor.rowcount == 0:
                        return False
                return True"""
content = content.replace(old_del_class, new_del_class)

old_rem_student_class = """                    conn.execute("DELETE FROM class_students WHERE class_id=? AND student_id=?", (class_id, student_id))
                return True"""
new_rem_student_class = """                    cursor = conn.execute("DELETE FROM class_students WHERE class_id=? AND student_id=?", (class_id, student_id))
                    if cursor.rowcount == 0:
                        return False
                return True"""
content = content.replace(old_rem_student_class, new_rem_student_class)

old_del_enc = """                    conn.execute("DELETE FROM face_encodings WHERE person_type=? AND person_id=?", (person_type, person_id))
                return True"""
new_del_enc = """                    cursor = conn.execute("DELETE FROM face_encodings WHERE person_type=? AND person_id=?", (person_type, person_id))
                    if cursor.rowcount == 0:
                        return False
                return True"""
content = content.replace(old_del_enc, new_del_enc)

old_del_timetable = """                    conn.execute("DELETE FROM timetable WHERE id=?", (timetable_id,))
                return True"""
new_del_timetable = """                    cursor = conn.execute("DELETE FROM timetable WHERE id=?", (timetable_id,))
                    if cursor.rowcount == 0:
                        return False
                return True"""
content = content.replace(old_del_timetable, new_del_timetable)

# Now fix the EXCEPT operational errors across all methods
# Pattern we are looking for:
#        except sqlite3.Error as e:
#            logger.error(f"Error {action}: {e}")
# We'll use regex to inject the OperationalError block
# match groups: (indentation)except sqlite3.Error as e:\n(indentation)logger.error(f"Error (.*?): {e}")

pattern = re.compile(
    r'(        )except sqlite3\.Error as e:\n(            )logger\.error\(f"Error (.*?): \{e\}"\)'
)

def inject_operational_error(match):
    indent1 = match.group(1)
    indent2 = match.group(2)
    action = match.group(3)
    return (f'{indent1}except sqlite3.OperationalError as e:\n'
            f'{indent2}logger.error(f"Database Locked or Operational Error during \'{action}\': {{e}}")\n'
            f'{indent1}except sqlite3.Error as e:\n'
            f'{indent2}logger.error(f"Error {action}: {{e}}")')

content = pattern.sub(inject_operational_error, content)

with open('src/core/database.py', 'w') as f:
    f.write(content)

print("Done modification")
