"""Camera Preview Panel — Hiển thị camera real-time với bounding box.

View layer thuần túy (MVP pattern):
- KHÔNG import từ src.core (panel này không cần events)
- Nhận frame qua get_frame_callback (callable)
- Vẽ bounding box theo coords nhận từ Presenter
- Presenter gọi set_bounding_box() từ main thread (dùng app.after(0, ...))

Performance notes:
- Dùng tkinter Label + PIL.ImageTk.PhotoImage thay vì CTkImage (nhanh hơn ~10x)
- Resize bằng cv2.resize (nhanh hơn PIL.resize)
- Chỉ copy frame khi cần vẽ bbox
- Face tracking nhẹ bằng OpenCV CascadeClassifier (~5ms) cho bbox mượt
"""

import logging
from PIL import Image, ImageTk
import customtkinter as ctk
import cv2
import tkinter as tk

logger = logging.getLogger(__name__)

# Load Haar Cascade 1 lần duy nhất (nhẹ, ~5ms/frame)
_CASCADE_PATH = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
_face_cascade = cv2.CascadeClassifier(_CASCADE_PATH)


class CameraPanel(ctk.CTkFrame):
    """Panel hiển thị camera preview real-time ~30fps.

    Args:
        master: Parent widget (CTk hoặc CTkFrame)
        get_frame_callback: Callable trả về RGB numpy array hoặc None.
            Presenter sẽ truyền camera_manager.get_frame.
    """

    def __init__(self, master, get_frame_callback: callable = None):
        super().__init__(master)
        self._get_frame_callback = get_frame_callback
        self._running = False
        self._after_id = None
        self._photo_image = None   # Giữ reference PhotoImage tránh GC

        # Bounding box từ Presenter (recognition match)
        self._match_bbox = None       # dict {'top','right','bottom','left'}
        self._match_color = "green"

        # Bounding box từ local tracking (fast cascade)
        self._track_bbox = None       # (x, y, w, h) from cascade
        self._frame_count = 0         # Counter để track mỗi 3 frames

        # Video label — dùng tkinter Label thuần (nhẹ hơn CTkLabel)
        self.video_label = tk.Label(
            self,
            text="📷 Camera đang tắt",
            font=("Arial", 16),
            bg="#2b2b2b",
            fg="#ffffff",
            anchor="center",
        )
        self.video_label.pack(expand=True, fill="both")

    def start_preview(self):
        """Bắt đầu camera preview loop (~30fps)."""
        if self._running:
            return
        self._running = True
        self._schedule_next()

    def stop_preview(self):
        """Dừng camera preview, cancel pending after."""
        self._running = False
        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        if self.winfo_exists():
            self.video_label.configure(image='', text="📷 Camera đang tắt")
        self._photo_image = None

    def set_bounding_box(self, coords: dict, color: str):
        """Lưu bounding box từ recognition match (Presenter gọi).

        Args:
            coords: Dict {'top', 'right', 'bottom', 'left'}
            color: "green" (match) hoặc "red"
        """
        self._match_bbox = coords
        self._match_color = color

    def clear_bounding_box(self):
        """Xóa bounding box từ Presenter."""
        self._match_bbox = None

    def _detect_face_fast(self, frame):
        """Detect khuôn mặt nhẹ bằng Haar Cascade (~5ms).

        Chạy trên ảnh thu nhỏ để tăng tốc. Chỉ dùng cho tracking bbox,
        KHÔNG dùng cho recognition.
        """
        # Giảm kích thước để cascade chạy nhanh hơn
        small = cv2.resize(frame, (0, 0), fx=0.35, fy=0.35)
        gray = cv2.cvtColor(small, cv2.COLOR_RGB2GRAY)
        faces = _face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.15,
            minNeighbors=4,
            minSize=(40, 40),
        )
        if len(faces) > 0:
            # Lấy mặt lớn nhất, scale ngược lại kích thước gốc
            x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
            scale = 1.0 / 0.35
            self._track_bbox = (
                int(x * scale), int(y * scale),
                int(w * scale), int(h * scale),
            )
        else:
            self._track_bbox = None

    def _update_frame(self):
        """Lấy frame, vẽ bbox, convert sang PhotoImage, cập nhật label."""
        if not self._running or not self.winfo_exists():
            return

        if not self._get_frame_callback:
            self._schedule_next()
            return

        try:
            frame = self._get_frame_callback()
        except Exception:
            self._schedule_next()
            return

        if frame is None:
            self._schedule_next()
            return

        # Lightweight face tracking mỗi 3 frames (~10fps)
        self._frame_count += 1
        if self._frame_count % 3 == 0:
            self._detect_face_fast(frame)

        # Xác định bbox để vẽ — ưu tiên match bbox (từ Presenter)
        need_draw = False
        if self._match_bbox:
            need_draw = True
        elif self._track_bbox:
            need_draw = True

        if need_draw:
            frame = frame.copy()
            if self._match_bbox:
                # Bbox từ recognition (đã match) — màu xanh
                top = self._match_bbox['top']
                right = self._match_bbox['right']
                bottom = self._match_bbox['bottom']
                left = self._match_bbox['left']
                color = (0, 255, 0) if self._match_color == "green" else (255, 0, 0)
                cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
            elif self._track_bbox:
                # Bbox từ local tracking — khung trắng mỏng (đang scan)
                x, y, w, h = self._track_bbox
                cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 255, 255), 1)

        # Scale frame giữ nguyên aspect ratio
        panel_w = self.winfo_width()
        panel_h = self.winfo_height()
        if panel_w <= 1 or panel_h <= 1:
            panel_w, panel_h = 640, 480

        frame_h, frame_w = frame.shape[:2]
        scale = min(panel_w / frame_w, panel_h / frame_h)
        new_w = int(frame_w * scale)
        new_h = int(frame_h * scale)

        if new_w != frame_w or new_h != frame_h:
            frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

        try:
            pil_image = Image.fromarray(frame)
            self._photo_image = ImageTk.PhotoImage(image=pil_image)
            self.video_label.configure(image=self._photo_image, text="")
        except Exception as e:
            logger.debug("Skip frame — conversion failed: %s", e)

        self._schedule_next()

    def _schedule_next(self):
        """Schedule frame update tiếp theo (~30fps = 33ms)."""
        if self._running and self.winfo_exists():
            self._after_id = self.after(33, self._update_frame)
