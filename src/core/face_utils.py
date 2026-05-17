import os
import shutil
import face_recognition

def _process_and_save_face(image_path, person_code, output_dir):
    """
    Process an image to validate the face and extract the 128d encoding.
    Saves the image physically to the output directory if validation passes.

    Args:
        image_path (str): Path to the source image file.
        person_code (str): Unique code of the person (student_code or teacher_code).
        output_dir (str): Destination directory for the validated image.

    Returns:
        tuple: (encoding: list, photo_path: str)
    """
    try:
        image = face_recognition.load_image_file(image_path)
    except Exception as e:
        raise ValueError("Định dạng file ảnh không hợp lệ hoặc bị hỏng.") from e

    face_locations = face_recognition.face_locations(image)
    if len(face_locations) == 0:
        raise ValueError("Không nhận diện được khuôn mặt trong ảnh.")
    if len(face_locations) > 1:
        raise ValueError("Phát hiện nhiều khuôn mặt, vui lòng chọn ảnh chân dung duy nhất.")

    # Extract encoding
    encodings = face_recognition.face_encodings(image, known_face_locations=face_locations)
    encoding = encodings[0]

    # Save to physical directory
    os.makedirs(output_dir, exist_ok=True)
    # Sanitize person_code to prevent path traversal
    safe_code = "".join(c for c in person_code if c.isalnum() or c in ('_', '-'))
    if not safe_code:
        raise ValueError("Mã định danh không hợp lệ.")
    filename = f"{safe_code}.jpg"
    photo_path = os.path.join(output_dir, filename)

    shutil.copy(image_path, photo_path)

    return encoding, photo_path
