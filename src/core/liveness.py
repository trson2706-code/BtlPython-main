"""
Module Liveness Detection — Chống giả mạo khuôn mặt (Anti-Spoofing).

Sử dụng 5 heuristic checks (texture, color, moiré, reflection, edge density)
để phát hiện ảnh từ điện thoại/tablet/giấy in.
"""

from __future__ import annotations

import cv2
import numpy as np
import math
import logging
from typing import TYPE_CHECKING
from src.core.config import Config

if TYPE_CHECKING:
    from src.core.recognition import FaceDetectionResult

logger = logging.getLogger(__name__)


class LivenessDetector:
    """
    Phát hiện khuôn mặt giả mạo (photo spoofing) bằng heuristic analysis.

    Sử dụng 5 checks:
    1. Texture Quality (Laplacian Variance)
    2. Color Distribution (YCrCb Histogram)
    3. Moiré Pattern (FFT Frequency Analysis)
    4. Reflection (Specular Highlights)
    5. Edge Density (Canny)

    Thread-safe: stateless per check_liveness() call.
    """

    # Default thresholds
    _DEFAULT_TEXTURE_THRESHOLD = 80.0
    _DEFAULT_COLOR_THRESHOLD = 0.4
    _DEFAULT_MOIRE_THRESHOLD = 0.3
    _DEFAULT_REFLECTION_THRESHOLD = 0.5
    _DEFAULT_EDGE_DENSITY_THRESHOLD = 0.15
    _DEFAULT_FINAL_SCORE_THRESHOLD = 0.6
    _DEFAULT_MIN_FACE_SIZE = 30
    _DEFAULT_WEIGHTS = {
        'texture': 0.30,
        'color': 0.20,
        'moire': 0.20,
        'reflection': 0.15,
        'edge_density': 0.15,
    }

    def __init__(self):
        """
        Khởi tạo LivenessDetector, đọc config từ Config() singleton.
        Nếu section 'liveness' không tồn tại → dùng toàn bộ defaults.
        """
        config = Config()

        # Enabled flag
        self._enabled = config.get('liveness', 'enabled', default=True)

        # [F3] Thresholds — tất cả đọc từ Config(), có default hợp lý
        # Wrap trong try/except để xử lý config value không phải numeric
        self._texture_threshold = self._safe_float(
            config.get('liveness', 'texture_threshold', default=self._DEFAULT_TEXTURE_THRESHOLD),
            self._DEFAULT_TEXTURE_THRESHOLD, 'texture_threshold'
        )
        self._color_threshold = self._safe_float(
            config.get('liveness', 'color_threshold', default=self._DEFAULT_COLOR_THRESHOLD),
            self._DEFAULT_COLOR_THRESHOLD, 'color_threshold'
        )
        self._moire_threshold = self._safe_float(
            config.get('liveness', 'moire_threshold', default=self._DEFAULT_MOIRE_THRESHOLD),
            self._DEFAULT_MOIRE_THRESHOLD, 'moire_threshold'
        )
        self._reflection_threshold = self._safe_float(
            config.get('liveness', 'reflection_threshold', default=self._DEFAULT_REFLECTION_THRESHOLD),
            self._DEFAULT_REFLECTION_THRESHOLD, 'reflection_threshold'
        )
        self._edge_density_threshold = self._safe_float(
            config.get('liveness', 'edge_density_threshold', default=self._DEFAULT_EDGE_DENSITY_THRESHOLD),
            self._DEFAULT_EDGE_DENSITY_THRESHOLD, 'edge_density_threshold'
        )
        self._final_score_threshold = self._safe_float(
            config.get('liveness', 'final_score_threshold', default=self._DEFAULT_FINAL_SCORE_THRESHOLD),
            self._DEFAULT_FINAL_SCORE_THRESHOLD, 'final_score_threshold'
        )
        self._min_face_size = self._safe_int(
            config.get('liveness', 'min_face_size', default=self._DEFAULT_MIN_FACE_SIZE),
            self._DEFAULT_MIN_FACE_SIZE, 'min_face_size'
        )

        # [H3] Validate thresholds > 0 — tránh division-by-zero / inverted scores
        for attr_name, default_val in [
            ('_texture_threshold', self._DEFAULT_TEXTURE_THRESHOLD),
            ('_color_threshold', self._DEFAULT_COLOR_THRESHOLD),
            ('_moire_threshold', self._DEFAULT_MOIRE_THRESHOLD),
            ('_reflection_threshold', self._DEFAULT_REFLECTION_THRESHOLD),
            ('_edge_density_threshold', self._DEFAULT_EDGE_DENSITY_THRESHOLD),
        ]:
            val = getattr(self, attr_name)
            if val <= 0:
                logger.warning(
                    f"Liveness threshold {attr_name} = {val} (≤ 0). "
                    f"Dùng default = {default_val}."
                )
                setattr(self, attr_name, default_val)

        # [F1] Validate final_score_threshold: phải > 0 và ≤ 1.0
        # Nếu ≤ 0 → mọi frame đều is_live=True (security bypass)
        # Nếu > 1.0 → không frame nào pass (deny-all)
        if self._final_score_threshold <= 0 or self._final_score_threshold > 1.0:
            logger.warning(
                f"Liveness _final_score_threshold = {self._final_score_threshold} "
                f"(phải > 0.0 và ≤ 1.0). Dùng default = {self._DEFAULT_FINAL_SCORE_THRESHOLD}."
            )
            self._final_score_threshold = self._DEFAULT_FINAL_SCORE_THRESHOLD

        # Weights — đọc từ config, validate tổng ≈ 1.0
        weights_config = config.get('liveness', 'weights', default=None)
        if weights_config and isinstance(weights_config, dict):
            self._weights = {
                'texture': float(weights_config.get('texture', self._DEFAULT_WEIGHTS['texture'])),
                'color': float(weights_config.get('color', self._DEFAULT_WEIGHTS['color'])),
                'moire': float(weights_config.get('moire', self._DEFAULT_WEIGHTS['moire'])),
                'reflection': float(weights_config.get('reflection', self._DEFAULT_WEIGHTS['reflection'])),
                'edge_density': float(weights_config.get('edge_density', self._DEFAULT_WEIGHTS['edge_density'])),
            }
        else:
            # Defensive copy to avoid mutating class-level _DEFAULT_WEIGHTS [M4]
            self._weights = dict(self._DEFAULT_WEIGHTS)

        # [CR-F3] Weights validation: auto-normalize nếu tổng ≠ 1.0
        weight_sum = sum(self._weights.values())
        if abs(weight_sum - 1.0) > 0.01:
            logger.warning(
                f"Liveness weights tổng = {weight_sum:.4f} (≠ 1.0). "
                f"Tự động normalize weights."
            )
            if weight_sum > 0:
                self._weights = {k: v / weight_sum for k, v in self._weights.items()}
            else:
                # Edge case: tất cả weights = 0 → dùng defaults
                self._weights = dict(self._DEFAULT_WEIGHTS)

        # [CR-F5] Log INFO 1 lần khi disabled
        if not self._enabled:
            logger.info("Liveness detection disabled via config")

    def check_liveness(self, frame: np.ndarray, face_location: 'FaceDetectionResult') -> dict:
        """
        Pipeline chính — chạy 5 checks và trả kết quả tổng hợp.

        Args:
            frame: Frame gốc (RGB, từ CameraManager.get_frame())
            face_location: FaceDetectionResult TypedDict (top, right, bottom, left)

        Returns:
            dict: {'is_live': bool, 'score': float, 'details': dict}
        """
        # Bypass khi disabled
        if not self._enabled:
            return {'is_live': True, 'score': 1.0, 'details': {}}

        # Guard: None frame
        if frame is None:
            return {'is_live': False, 'score': 0.0, 'details': {}}

        # [F5] Guard: frame phải là array >= 2D (height × width × ...)
        if not isinstance(frame, np.ndarray) or frame.ndim < 2:
            return {'is_live': False, 'score': 0.0, 'details': {}}

        # Guard: None face_location
        if face_location is None:
            return {'is_live': False, 'score': 0.0, 'details': {}}

        # Crop face ROI với padding 10% + clamp
        top = face_location['top']
        right = face_location['right']
        bottom = face_location['bottom']
        left = face_location['left']

        height = bottom - top
        width = right - left

        # Guard: ROI 0×0 hoặc quá nhỏ [CR-F7, CR-F8]
        if width < self._min_face_size or height < self._min_face_size:
            return {'is_live': False, 'score': 0.0, 'details': {}}

        # [F7] Padding 10% — best-effort, clamp to frame bounds [CR-F4]
        # Note: max(0,...) + min(frame.shape,...) đảm bảo an toàn ngay cả khi
        # face_location chứa giá trị rất lớn — clamp luôn giới hạn trong frame.
        pad_h = int(height * 0.1)
        pad_w = int(width * 0.1)
        y1 = max(0, top - pad_h)
        y2 = min(frame.shape[0], bottom + pad_h)
        x1 = max(0, left - pad_w)
        x2 = min(frame.shape[1], right + pad_w)

        face_roi = frame[y1:y2, x1:x2]

        # Guard: ROI sau crop có thể rỗng
        if face_roi.size == 0:
            return {'is_live': False, 'score': 0.0, 'details': {}}

        # Chạy 5 checks — mỗi check try/except riêng
        details = {}

        # Check 1: Texture
        try:
            texture_score = self._check_texture_quality(face_roi)
            texture_score = self._sanitize_score(texture_score)
        except Exception as e:
            logger.warning(f"Liveness texture check failed: {e}")
            texture_score = 0.5
        details['texture'] = texture_score

        # Check 2: Color
        try:
            color_score = self._check_color_distribution(face_roi)
            color_score = self._sanitize_score(color_score)
        except Exception as e:
            logger.warning(f"Liveness color check failed: {e}")
            color_score = 0.5
        details['color'] = color_score

        # Check 3: Moiré
        try:
            moire_score = self._check_moire_pattern(face_roi)
            moire_score = self._sanitize_score(moire_score)
        except Exception as e:
            logger.warning(f"Liveness moiré check failed: {e}")
            moire_score = 0.5
        details['moire'] = moire_score

        # Check 4: Reflection
        try:
            reflection_score = self._check_reflection(face_roi)
            reflection_score = self._sanitize_score(reflection_score)
        except Exception as e:
            logger.warning(f"Liveness reflection check failed: {e}")
            reflection_score = 0.5
        details['reflection'] = reflection_score

        # Check 5: Edge Density
        try:
            edge_score = self._check_edge_density(face_roi)
            edge_score = self._sanitize_score(edge_score)
        except Exception as e:
            logger.warning(f"Liveness edge density check failed: {e}")
            edge_score = 0.5
        details['edge_density'] = edge_score

        # Weighted average
        final_score = (
            self._weights['texture'] * details['texture']
            + self._weights['color'] * details['color']
            + self._weights['moire'] * details['moire']
            + self._weights['reflection'] * details['reflection']
            + self._weights['edge_density'] * details['edge_density']
        )

        # [F6] Clamp final_score to [0.0, 1.0] — defensive, dù individual scores
        # đã sanitize nhưng đảm bảo output luôn hợp lệ.
        final_score = max(0.0, min(1.0, final_score))

        is_live = final_score >= self._final_score_threshold

        if not is_live:
            logger.warning(
                f"Phát hiện spoof — score={final_score:.3f} "
                f"(threshold={self._final_score_threshold}), "
                f"details={details}"
            )

        return {
            'is_live': is_live,
            'score': round(final_score, 4),
            'details': details,
        }

    # ──────────────────────────────────────────────────────────
    # 5 Check Methods
    # ──────────────────────────────────────────────────────────

    def _check_texture_quality(self, face_roi: np.ndarray) -> float:
        """
        AC2: Laplacian variance — ảnh thật có texture phong phú → score cao.
        """
        # [CR-F6] Grayscale input guard
        if face_roi.ndim == 2:
            gray = face_roi
        elif face_roi.ndim == 3:
            gray = cv2.cvtColor(face_roi, cv2.COLOR_RGB2GRAY)
        else:
            return 0.5  # ndim không hợp lệ → fallback

        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        score = min(1.0, laplacian_var / self._texture_threshold)
        return score

    def _check_color_distribution(self, face_roi: np.ndarray) -> float:
        """
        AC3: YCrCb histogram — da thật có phân bố Cr/Cb đặc trưng.
        """
        # [CR-F6] Grayscale input guard
        if face_roi.ndim == 2:
            return 0.5  # Không thể phân tích color từ grayscale → neutral
        elif face_roi.ndim != 3:
            return 0.5

        ycrcb = cv2.cvtColor(face_roi, cv2.COLOR_RGB2YCrCb)
        cr = ycrcb[:, :, 1]
        cb = ycrcb[:, :, 2]

        # Skin color range: Cr 133-173, Cb 77-127
        skin_mask = (
            (cr >= 133) & (cr <= 173) &
            (cb >= 77) & (cb <= 127)
        )

        total_pixels = face_roi.shape[0] * face_roi.shape[1]
        if total_pixels == 0:
            return 0.5

        skin_pixels = np.sum(skin_mask)
        skin_ratio = skin_pixels / total_pixels
        score = min(1.0, skin_ratio / self._color_threshold)
        return score

    def _check_moire_pattern(self, face_roi: np.ndarray) -> float:
        """
        AC4: FFT frequency analysis — màn hình có moiré pattern → high-freq ratio cao.
        """
        # [CR-F6] Grayscale input guard
        if face_roi.ndim == 2:
            gray = face_roi
        elif face_roi.ndim == 3:
            gray = cv2.cvtColor(face_roi, cv2.COLOR_RGB2GRAY)
        else:
            return 0.5

        f_transform = np.fft.fft2(gray.astype(np.float64))
        f_shift = np.fft.fftshift(f_transform)
        magnitude = np.abs(f_shift)

        rows, cols = magnitude.shape
        crow, ccol = rows // 2, cols // 2
        r = min(rows, cols) // 6  # inner 1/3 radius [CR-F11]

        # Guard: r == 0 cho ROI cực nhỏ
        if r == 0:
            return 0.5

        total_energy = np.sum(magnitude)
        if total_energy == 0:
            return 0.5

        low_freq_energy = np.sum(magnitude[crow - r:crow + r, ccol - r:ccol + r])
        high_freq_energy = total_energy - low_freq_energy
        high_freq_ratio = high_freq_energy / total_energy

        # high_freq_ratio cao → moiré → score thấp
        score = max(0.0, 1.0 - (high_freq_ratio / self._moire_threshold))
        return score

    def _check_reflection(self, face_roi: np.ndarray) -> float:
        """
        AC5: Specular highlights — phản chiếu ánh sáng trên kính.
        """
        # [CR-F6] Grayscale input guard
        if face_roi.ndim == 2:
            gray = face_roi
        elif face_roi.ndim == 3:
            gray = cv2.cvtColor(face_roi, cv2.COLOR_RGB2GRAY)
        else:
            return 0.5

        _, bright_mask = cv2.threshold(gray, 250, 255, cv2.THRESH_BINARY)
        bright_ratio = np.sum(bright_mask > 0) / bright_mask.size

        # bright_ratio cao → reflection → score thấp
        score = max(0.0, 1.0 - (bright_ratio / self._reflection_threshold))
        return score

    def _check_edge_density(self, face_roi: np.ndarray) -> float:
        """
        AC6: Canny edge detection — khuôn mặt thật có edge density cao.
        """
        # [CR-F6] Grayscale input guard
        if face_roi.ndim == 2:
            gray = face_roi
        elif face_roi.ndim == 3:
            gray = cv2.cvtColor(face_roi, cv2.COLOR_RGB2GRAY)
        else:
            return 0.5

        edges = cv2.Canny(gray, 50, 150)
        edge_ratio = np.sum(edges > 0) / edges.size
        score = min(1.0, edge_ratio / self._edge_density_threshold)
        return score

    # ──────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────

    @staticmethod
    def _sanitize_score(score: float) -> float:
        """
        [CR-F9] Validate score trong 0.0-1.0.
        NaN/Infinity/out-of-range → fallback 0.5.
        """
        if score is None or not isinstance(score, (int, float)):
            return 0.5
        if math.isnan(score) or math.isinf(score):
            return 0.5
        if score < 0.0 or score > 1.0:
            return 0.5
        return float(score)

    @staticmethod
    def _safe_float(value, default: float, name: str) -> float:
        """
        [F3] An toàn parse float từ config. Non-numeric → fallback + WARNING.
        """
        try:
            return float(value)
        except (TypeError, ValueError):
            logger.warning(
                f"Liveness config '{name}' = {value!r} (không phải numeric). "
                f"Dùng default = {default}."
            )
            return default

    @staticmethod
    def _safe_int(value, default: int, name: str) -> int:
        """
        [F3] An toàn parse int từ config. Non-numeric → fallback + WARNING.
        """
        try:
            return int(value)
        except (TypeError, ValueError):
            logger.warning(
                f"Liveness config '{name}' = {value!r} (không phải numeric). "
                f"Dùng default = {default}."
            )
            return default
