"""Script setup dữ liệu demo — thêm GV, lớp, TKB, SV.

Chạy bằng: .venv/bin/python3 setup_demo.py

⚠️ Sửa các biến bên dưới cho đúng với dữ liệu của bạn.
"""

import sys
from datetime import datetime

from src.core.database import DatabaseManager
from src.core.class_manager import ClassManager
from src.core.student_manager import StudentManager

db = DatabaseManager()
class_mgr = ClassManager(db)
student_mgr = StudentManager(db)


def add_teacher_demo():
    """Thêm giảng viên demo."""
    # ──────────────────────────────────────────────
    # ⚠️ SỬA CÁC GIÁ TRỊ BÊN DƯỚI CHO ĐÚNG
    # ──────────────────────────────────────────────
    TEACHER_NAME = "Nguyễn Đức Huy"         # Tên giảng viên
    TEACHER_CODE = "GV001"                  # Mã giảng viên (unique)
    TEACHER_IMAGE = "data/teachers/Nguyen Duc Huy.jpg"  # Đường dẫn ảnh chân dung
    # ──────────────────────────────────────────────

    try:
        teacher = class_mgr.add_teacher(TEACHER_NAME, TEACHER_CODE, TEACHER_IMAGE)
        print(f"✅ Đã thêm GV: {teacher['name']} (ID={teacher['id']})")
        return teacher['id']
    except ValueError as e:
        print(f"❌ Lỗi thêm GV: {e}")
        # Nếu GV đã tồn tại, tìm ID
        all_teachers = class_mgr.get_all_teachers()
        for t in all_teachers:
            if t['teacher_code'] == TEACHER_CODE:
                print(f"   → GV đã tồn tại: ID={t['id']}")
                return t['id']
        sys.exit(1)


def add_class_and_timetable(teacher_id):
    """Thêm lớp + TKB demo."""
    # ──────────────────────────────────────────────
    # ⚠️ SỬA CÁC GIÁ TRỊ BÊN DƯỚI CHO ĐÚNG
    # ──────────────────────────────────────────────
    CLASS_CODE = "CNTT01"                   # Mã lớp
    SUBJECT = "Computer Vision"             # Tên môn
    # ──────────────────────────────────────────────

    try:
        cls = class_mgr.add_class(CLASS_CODE, SUBJECT, teacher_id)
        print(f"✅ Đã thêm lớp: {cls['class_code']} - {cls['subject']} (ID={cls['id']})")
        class_id = cls['id']
    except ValueError as e:
        print(f"❌ Lỗi thêm lớp: {e}")
        # Tìm lớp đã tồn tại
        all_classes = class_mgr.get_all_classes()
        for c in all_classes:
            if c['class_code'] == CLASS_CODE:
                print(f"   → Lớp đã tồn tại: ID={c['id']}")
                class_id = c['id']
                break
        else:
            sys.exit(1)

    # Thêm TKB — start_time = giờ hiện tại (match ±30 phút check window)
    # day_of_week: 0=Monday..6=Sunday (Python weekday format)
    start_str = datetime.now().strftime('%H:%M')
    days_added = 0
    for day in range(7):
        try:
            db.add_timetable(class_id, day, start_str, '23:59')
            days_added += 1
        except Exception:
            pass  # Có thể đã tồn tại
    if days_added > 0:
        print(f"✅ Đã thêm TKB: {days_added} ngày/tuần, start={start_str} (class_id={class_id})")
    else:
        print("⚠️ TKB có thể đã tồn tại")

    return class_id


def add_students_demo(class_id):
    """Thêm sinh viên demo."""
    # ──────────────────────────────────────────────
    # ⚠️ THÊM SINH VIÊN Ở ĐÂY — mỗi SV cần 1 ảnh chân dung
    # ──────────────────────────────────────────────
    STUDENTS = [
        # (tên, mã SV, đường dẫn ảnh)
        # ("Trần Văn B", "SV001", "data/students/sv001.jpg"),
        # ("Lê Thị C", "SV002", "data/students/sv002.jpg"),
    ]
    # ──────────────────────────────────────────────

    if not STUDENTS:
        print("⚠️ Chưa có SV demo — bỏ qua. Sửa STUDENTS list trong file này để thêm.")
        return

    for name, code, img_path in STUDENTS:
        try:
            student = student_mgr.add_student(name, code, img_path)
            db.add_student_to_class(class_id, student['id'])
            print(f"✅ Đã thêm SV: {name} ({code}) → lớp {class_id}")
        except ValueError as e:
            print(f"❌ Lỗi thêm SV {name}: {e}")


if __name__ == '__main__':
    print("=" * 50)
    print("🔧 SETUP DỮ LIỆU DEMO")
    print("=" * 50)

    teacher_id = add_teacher_demo()
    class_id = add_class_and_timetable(teacher_id)
    add_students_demo(class_id)

    print()
    print("=" * 50)
    print("✅ XONG! Chạy app bằng: .venv/bin/python3 -m src.main")
    print("=" * 50)
