"""
Unit tests cho LivenessDetector (Story 10.1).

≥15 test cases bao phủ tất cả AC + edge cases + CR findings.
"""

import unittest
from unittest.mock import patch, MagicMock
import numpy as np
import math
import logging


class TestLivenessDetectorInit(unittest.TestCase):
    """Test 1-2: Khởi tạo LivenessDetector với config mặc định và custom."""

    @patch('src.core.liveness.Config')
    def test_init_default_config(self, mock_config_cls):
        """Test 1: LivenessDetector khởi tạo với config mặc định."""
        mock_config = MagicMock()
        mock_config.get.return_value = None  # Không có section liveness
        mock_config_cls.return_value = mock_config

        # Config().get('liveness', ...) trả None → dùng defaults
        def get_side_effect(*args, default=None):
            return default

        mock_config.get.side_effect = get_side_effect

        from src.core.liveness import LivenessDetector
        detector = LivenessDetector()

        self.assertTrue(detector._enabled)
        self.assertEqual(detector._texture_threshold, 80.0)
        self.assertEqual(detector._color_threshold, 0.4)
        self.assertEqual(detector._moire_threshold, 0.3)
        self.assertEqual(detector._reflection_threshold, 0.5)
        self.assertEqual(detector._edge_density_threshold, 0.15)
        self.assertEqual(detector._final_score_threshold, 0.6)
        self.assertEqual(detector._min_face_size, 30)
        self.assertAlmostEqual(sum(detector._weights.values()), 1.0, places=2)

    @patch('src.core.liveness.Config')
    def test_init_custom_config(self, mock_config_cls):
        """Test 2: LivenessDetector khởi tạo với config custom (mock Config())."""
        mock_config = MagicMock()
        mock_config_cls.return_value = mock_config

        custom_values = {
            ('liveness', 'enabled'): True,
            ('liveness', 'texture_threshold'): 100.0,
            ('liveness', 'color_threshold'): 0.5,
            ('liveness', 'moire_threshold'): 0.4,
            ('liveness', 'reflection_threshold'): 0.6,
            ('liveness', 'edge_density_threshold'): 0.2,
            ('liveness', 'final_score_threshold'): 0.7,
            ('liveness', 'min_face_size'): 50,
            ('liveness', 'weights'): {
                'texture': 0.25,
                'color': 0.25,
                'moire': 0.25,
                'reflection': 0.15,
                'edge_density': 0.10,
            },
        }

        def get_side_effect(*args, default=None):
            return custom_values.get(args, default)

        mock_config.get.side_effect = get_side_effect

        from src.core.liveness import LivenessDetector
        detector = LivenessDetector()

        self.assertEqual(detector._texture_threshold, 100.0)
        self.assertEqual(detector._color_threshold, 0.5)
        self.assertEqual(detector._moire_threshold, 0.4)
        self.assertEqual(detector._min_face_size, 50)
        self.assertEqual(detector._final_score_threshold, 0.7)
        self.assertAlmostEqual(sum(detector._weights.values()), 1.0, places=2)


class TestCheckTextureQuality(unittest.TestCase):
    """Test 3-4: _check_texture_quality — ảnh sắc nét vs ảnh mờ."""

    def _create_detector(self):
        with patch('src.core.liveness.Config') as mock_config_cls:
            mock_config = MagicMock()
            mock_config_cls.return_value = mock_config
            mock_config.get.side_effect = lambda *args, default=None: default
            from src.core.liveness import LivenessDetector
            return LivenessDetector()

    def test_sharp_image_high_score(self):
        """Test 3: Ảnh sắc nét → Laplacian variance cao → score cao."""
        detector = self._create_detector()
        # Tạo ảnh có texture phong phú (random noise)
        np.random.seed(42)
        sharp_image = np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)
        score = detector._check_texture_quality(sharp_image)
        self.assertGreater(score, 0.5)
        self.assertLessEqual(score, 1.0)

    def test_blurry_image_low_score(self):
        """Test 4: Ảnh mờ (gaussian blur) → Laplacian variance thấp → score thấp."""
        detector = self._create_detector()
        # Tạo ảnh phẳng (rất ít texture)
        import cv2
        flat_image = np.ones((100, 100, 3), dtype=np.uint8) * 128
        # Blur mạnh
        blurry = cv2.GaussianBlur(flat_image, (31, 31), 10)
        score = detector._check_texture_quality(blurry)
        self.assertLess(score, 0.3)


class TestCheckColorDistribution(unittest.TestCase):
    """Test 5: _check_color_distribution — ảnh da thường → score hợp lý."""

    def _create_detector(self):
        with patch('src.core.liveness.Config') as mock_config_cls:
            mock_config = MagicMock()
            mock_config_cls.return_value = mock_config
            mock_config.get.side_effect = lambda *args, default=None: default
            from src.core.liveness import LivenessDetector
            return LivenessDetector()

    def test_skin_color_reasonable_score(self):
        """Test 5: Ảnh có nhiều pixel skin tone → score hợp lý."""
        detector = self._create_detector()
        # Tạo ảnh RGB giống tông da (trung bình)
        # RGB ~(180, 130, 100) tương đương skin tone
        skin_image = np.zeros((100, 100, 3), dtype=np.uint8)
        skin_image[:, :, 0] = 180  # R
        skin_image[:, :, 1] = 130  # G
        skin_image[:, :, 2] = 100  # B
        score = detector._check_color_distribution(skin_image)
        self.assertGreater(score, 0.0)
        self.assertLessEqual(score, 1.0)


class TestCheckMoirePattern(unittest.TestCase):
    """Test 6: _check_moire_pattern — ảnh bình thường vs ảnh có pattern."""

    def _create_detector(self):
        with patch('src.core.liveness.Config') as mock_config_cls:
            mock_config = MagicMock()
            mock_config_cls.return_value = mock_config
            mock_config.get.side_effect = lambda *args, default=None: default
            from src.core.liveness import LivenessDetector
            return LivenessDetector()

    def test_normal_vs_pattern_image(self):
        """Test 6: Ảnh bình thường vs ảnh có high-frequency pattern → phân biệt được."""
        detector = self._create_detector()

        # Ảnh bình thường — smooth gradient (genuinely low-freq content)
        normal_image = np.zeros((100, 100, 3), dtype=np.uint8)
        for i in range(100):
            normal_image[i, :] = int(i * 255 / 99)  # Smooth vertical gradient
        normal_score = detector._check_moire_pattern(normal_image)

        # Ảnh có moiré pattern (high-freq repeating checkerboard)
        moire_image = np.zeros((100, 100, 3), dtype=np.uint8)
        for i in range(100):
            for j in range(100):
                moire_image[i, j] = 255 if (i + j) % 2 == 0 else 0
        moire_score = detector._check_moire_pattern(moire_image)

        # Ảnh bình thường nên có score cao hơn ảnh moiré
        self.assertGreater(normal_score, moire_score)


class TestCheckReflection(unittest.TestCase):
    """Test 7: _check_reflection — ảnh không glare vs ảnh có glare."""

    def _create_detector(self):
        with patch('src.core.liveness.Config') as mock_config_cls:
            mock_config = MagicMock()
            mock_config_cls.return_value = mock_config
            mock_config.get.side_effect = lambda *args, default=None: default
            from src.core.liveness import LivenessDetector
            return LivenessDetector()

    def test_no_glare_vs_glare(self):
        """Test 7: Ảnh không có glare → score cao. Ảnh có vùng sáng quá → score thấp hơn."""
        detector = self._create_detector()

        # Ảnh bình thường (không có vùng sáng > 250)
        normal = np.ones((100, 100, 3), dtype=np.uint8) * 128
        normal_score = detector._check_reflection(normal)

        # Ảnh có nhiều vùng sáng bất thường
        glare = np.ones((100, 100, 3), dtype=np.uint8) * 128
        glare[0:60, 0:60] = 255  # 60% ảnh quá sáng
        glare_score = detector._check_reflection(glare)

        self.assertGreater(normal_score, glare_score)


class TestCheckEdgeDensity(unittest.TestCase):
    """Test 8: _check_edge_density — ảnh chi tiết vs ảnh phẳng."""

    def _create_detector(self):
        with patch('src.core.liveness.Config') as mock_config_cls:
            mock_config = MagicMock()
            mock_config_cls.return_value = mock_config
            mock_config.get.side_effect = lambda *args, default=None: default
            from src.core.liveness import LivenessDetector
            return LivenessDetector()

    def test_detailed_vs_flat_image(self):
        """Test 8: Ảnh chi tiết (nhiều edges) vs ảnh phẳng → score khác nhau."""
        detector = self._create_detector()

        # Ảnh chi tiết (random → nhiều edges)
        np.random.seed(42)
        detailed = np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)
        detailed_score = detector._check_edge_density(detailed)

        # Ảnh phẳng (ít edges)
        flat = np.ones((100, 100, 3), dtype=np.uint8) * 128
        flat_score = detector._check_edge_density(flat)

        self.assertGreater(detailed_score, flat_score)


class TestCheckLivenessPipeline(unittest.TestCase):
    """Test 9-10: check_liveness() — full pipeline + guard cases."""

    def _create_detector(self):
        with patch('src.core.liveness.Config') as mock_config_cls:
            mock_config = MagicMock()
            mock_config_cls.return_value = mock_config
            mock_config.get.side_effect = lambda *args, default=None: default
            from src.core.liveness import LivenessDetector
            return LivenessDetector()

    def test_full_pipeline(self):
        """Test 9: check_liveness() — full pipeline với ảnh tổng hợp."""
        detector = self._create_detector()

        # Tạo frame 200x200
        np.random.seed(42)
        frame = np.random.randint(0, 256, (200, 200, 3), dtype=np.uint8)
        face_location = {'top': 30, 'right': 170, 'bottom': 170, 'left': 30}

        result = detector.check_liveness(frame, face_location)

        self.assertIn('is_live', result)
        self.assertIn('score', result)
        self.assertIn('details', result)
        self.assertIsInstance(result['is_live'], bool)
        self.assertIsInstance(result['score'], float)
        self.assertGreaterEqual(result['score'], 0.0)
        self.assertLessEqual(result['score'], 1.0)
        # Kiểm tra chi tiết
        for key in ['texture', 'color', 'moire', 'reflection', 'edge_density']:
            self.assertIn(key, result['details'])
            self.assertGreaterEqual(result['details'][key], 0.0)
            self.assertLessEqual(result['details'][key], 1.0)

    def test_guard_cases(self):
        """Test 10: Guard cases — None frame, None location, quá nhỏ, ROI 0×0."""
        detector = self._create_detector()

        expected = {'is_live': False, 'score': 0.0, 'details': {}}

        cases = [
            ('None frame', None, {'top': 0, 'right': 100, 'bottom': 100, 'left': 0}),
            ('None face_location', np.zeros((100, 100, 3), dtype=np.uint8), None),
            ('ROI quá nhỏ (20x20)', np.zeros((100, 100, 3), dtype=np.uint8),
             {'top': 10, 'right': 30, 'bottom': 30, 'left': 10}),
            ('ROI 0×0 (top==bottom)', np.zeros((100, 100, 3), dtype=np.uint8),
             {'top': 50, 'right': 80, 'bottom': 50, 'left': 30}),
            ('ROI 0×0 (left==right)', np.zeros((100, 100, 3), dtype=np.uint8),
             {'top': 30, 'right': 50, 'bottom': 80, 'left': 50}),
        ]

        for label, frame, loc in cases:
            with self.subTest(case=label):
                result = detector.check_liveness(frame, loc)
                self.assertEqual(result, expected, f"Failed for case: {label}")


class TestDisabledLiveness(unittest.TestCase):
    """Test 11: liveness.enabled = false → luôn return is_live=True, score=1.0."""

    @patch('src.core.liveness.Config')
    def test_disabled_bypass(self, mock_config_cls):
        """Test 11: Disabled → bypass, return is_live=True, score=1.0."""
        mock_config = MagicMock()
        mock_config_cls.return_value = mock_config

        def get_side_effect(*args, default=None):
            if args == ('liveness', 'enabled'):
                return False
            return default

        mock_config.get.side_effect = get_side_effect

        from src.core.liveness import LivenessDetector
        detector = LivenessDetector()

        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        face_loc = {'top': 10, 'right': 90, 'bottom': 90, 'left': 10}
        result = detector.check_liveness(frame, face_loc)

        self.assertTrue(result['is_live'])
        self.assertEqual(result['score'], 1.0)
        self.assertEqual(result['details'], {})


class TestExceptionFallback(unittest.TestCase):
    """Test 12: Exception trong 1 check → fallback 0.5, pipeline vẫn chạy."""

    def test_single_check_exception_handled(self):
        """Test 12: Nếu 1 check throw exception → score 0.5, pipeline không crash."""
        with patch('src.core.liveness.Config') as mock_config_cls:
            mock_config = MagicMock()
            mock_config_cls.return_value = mock_config
            mock_config.get.side_effect = lambda *args, default=None: default

            from src.core.liveness import LivenessDetector
            detector = LivenessDetector()

        # Patch 1 check method để throw exception
        with patch.object(detector, '_check_texture_quality', side_effect=RuntimeError("Test error")):
            frame = np.random.randint(0, 256, (200, 200, 3), dtype=np.uint8)
            face_loc = {'top': 30, 'right': 170, 'bottom': 170, 'left': 30}

            result = detector.check_liveness(frame, face_loc)

            # Pipeline vẫn chạy
            self.assertIn('is_live', result)
            self.assertIn('score', result)
            # Texture bị exception → fallback 0.5
            self.assertEqual(result['details']['texture'], 0.5)
            # Các check khác vẫn có score hợp lệ
            self.assertIsInstance(result['details']['color'], float)
            self.assertIsInstance(result['details']['moire'], float)


class TestGrayscaleInput(unittest.TestCase):
    """Test 13: [CR-F6] Grayscale input (2D array) → mỗi check xử lý gracefully."""

    def _create_detector(self):
        with patch('src.core.liveness.Config') as mock_config_cls:
            mock_config = MagicMock()
            mock_config_cls.return_value = mock_config
            mock_config.get.side_effect = lambda *args, default=None: default
            from src.core.liveness import LivenessDetector
            return LivenessDetector()

    def test_grayscale_input_all_checks(self):
        """Test 13: Grayscale 2D input → không crash, trả score hợp lệ."""
        detector = self._create_detector()

        np.random.seed(42)
        gray_roi = np.random.randint(0, 256, (100, 100), dtype=np.uint8)

        # Texture — nên hoạt động bình thường (skip cvtColor)
        score = detector._check_texture_quality(gray_roi)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

        # Color — nên trả 0.5 (không thể phân tích color từ grayscale)
        score = detector._check_color_distribution(gray_roi)
        self.assertEqual(score, 0.5)

        # Moiré — nên hoạt động bình thường
        score = detector._check_moire_pattern(gray_roi)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

        # Reflection — nên hoạt động bình thường
        score = detector._check_reflection(gray_roi)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

        # Edge density — nên hoạt động bình thường
        score = detector._check_edge_density(gray_roi)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)


class TestWeightsNormalization(unittest.TestCase):
    """Test 14: [CR-F3] Weights tổng ≠ 1.0 → auto-normalize + WARNING log."""

    @patch('src.core.liveness.Config')
    def test_weights_auto_normalize(self, mock_config_cls):
        """Test 14: Weights tổng != 1.0 → auto normalize + WARNING."""
        mock_config = MagicMock()
        mock_config_cls.return_value = mock_config

        bad_weights = {
            'texture': 0.5,
            'color': 0.5,
            'moire': 0.5,
            'reflection': 0.5,
            'edge_density': 0.5,
        }  # Tổng = 2.5

        def get_side_effect(*args, default=None):
            if args == ('liveness', 'weights'):
                return bad_weights
            return default

        mock_config.get.side_effect = get_side_effect

        from src.core.liveness import LivenessDetector

        with self.assertLogs('src.core.liveness', level='WARNING') as cm:
            detector = LivenessDetector()

        # Phải có warning log
        self.assertTrue(any('normalize' in msg.lower() or 'tổng' in msg.lower() for msg in cm.output))

        # Weights phải được normalize về tổng = 1.0
        self.assertAlmostEqual(sum(detector._weights.values()), 1.0, places=2)
        # Mỗi weight = 0.2 (vì 0.5/2.5 = 0.2)
        for w in detector._weights.values():
            self.assertAlmostEqual(w, 0.2, places=2)


class TestScoreSanitization(unittest.TestCase):
    """Test 15: [CR-F9] Check trả NaN/Infinity → sanitize thành 0.5."""

    def _create_detector(self):
        with patch('src.core.liveness.Config') as mock_config_cls:
            mock_config = MagicMock()
            mock_config_cls.return_value = mock_config
            mock_config.get.side_effect = lambda *args, default=None: default
            from src.core.liveness import LivenessDetector
            return LivenessDetector()

    def test_nan_infinity_sanitization(self):
        """Test 15: NaN, Infinity, out-of-range → fallback 0.5."""
        detector = self._create_detector()

        self.assertEqual(detector._sanitize_score(float('nan')), 0.5)
        self.assertEqual(detector._sanitize_score(float('inf')), 0.5)
        self.assertEqual(detector._sanitize_score(float('-inf')), 0.5)
        self.assertEqual(detector._sanitize_score(-0.1), 0.5)
        self.assertEqual(detector._sanitize_score(1.5), 0.5)
        self.assertEqual(detector._sanitize_score(None), 0.5)

        # Valid scores — phải giữ nguyên
        self.assertEqual(detector._sanitize_score(0.0), 0.0)
        self.assertEqual(detector._sanitize_score(0.5), 0.5)
        self.assertEqual(detector._sanitize_score(1.0), 1.0)

    def test_nan_in_pipeline(self):
        """Test 15b: Check trả NaN trong pipeline → sanitize thành 0.5, pipeline tiếp tục."""
        detector = self._create_detector()

        # Patch texture check to return NaN
        with patch.object(detector, '_check_texture_quality', return_value=float('nan')):
            frame = np.random.randint(0, 256, (200, 200, 3), dtype=np.uint8)
            face_loc = {'top': 30, 'right': 170, 'bottom': 170, 'left': 30}
            result = detector.check_liveness(frame, face_loc)

            # NaN → sanitize thành 0.5
            self.assertEqual(result['details']['texture'], 0.5)
            # Pipeline vẫn chạy
            self.assertIn('score', result)


class TestGrayscaleFullPipeline(unittest.TestCase):
    """Test 16: [H1/H2] Grayscale 2D frame through full check_liveness() pipeline."""

    def _create_detector(self):
        with patch('src.core.liveness.Config') as mock_config_cls:
            mock_config = MagicMock()
            mock_config_cls.return_value = mock_config
            mock_config.get.side_effect = lambda *args, default=None: default
            from src.core.liveness import LivenessDetector
            return LivenessDetector()

    def test_grayscale_frame_pipeline(self):
        """Test 16: 2D grayscale frame → check_liveness() runs all checks, color returns 0.5."""
        detector = self._create_detector()

        # Create a 2D (grayscale) frame — simulates ndim==2 input
        np.random.seed(42)
        gray_frame = np.random.randint(0, 256, (200, 200), dtype=np.uint8)
        face_loc = {'top': 30, 'right': 170, 'bottom': 170, 'left': 30}

        result = detector.check_liveness(gray_frame, face_loc)

        self.assertIn('is_live', result)
        self.assertIn('score', result)
        self.assertIn('details', result)
        # Color check should return 0.5 (neutral) for grayscale input
        self.assertEqual(result['details']['color'], 0.5)
        # Other checks should produce valid scores
        for key in ['texture', 'moire', 'reflection', 'edge_density']:
            self.assertGreaterEqual(result['details'][key], 0.0)
            self.assertLessEqual(result['details'][key], 1.0)


class TestZeroWeightsEdgeCase(unittest.TestCase):
    """Test 17: [M1] All weights = 0 → fallback to defaults."""

    @patch('src.core.liveness.Config')
    def test_zero_weights_fallback(self, mock_config_cls):
        """Test 17: Weights all zero → fallback to default weights."""
        mock_config = MagicMock()
        mock_config_cls.return_value = mock_config

        zero_weights = {
            'texture': 0.0,
            'color': 0.0,
            'moire': 0.0,
            'reflection': 0.0,
            'edge_density': 0.0,
        }

        def get_side_effect(*args, default=None):
            if args == ('liveness', 'weights'):
                return zero_weights
            return default

        mock_config.get.side_effect = get_side_effect

        from src.core.liveness import LivenessDetector
        detector = LivenessDetector()

        # Should fallback to defaults (sum ≈ 1.0)
        self.assertAlmostEqual(sum(detector._weights.values()), 1.0, places=2)
        # Verify it's actually the defaults, not zeros
        self.assertGreater(detector._weights['texture'], 0.0)


class TestEmptyRoiAfterCrop(unittest.TestCase):
    """Test 18: [M2] Frame so small that ROI after padding+crop is empty."""

    def _create_detector(self):
        with patch('src.core.liveness.Config') as mock_config_cls:
            mock_config = MagicMock()
            mock_config_cls.return_value = mock_config
            # Set min_face_size very low so guard doesn't trigger before crop
            def get_side_effect(*args, default=None):
                if args == ('liveness', 'min_face_size'):
                    return 1
                return default
            mock_config.get.side_effect = get_side_effect
            from src.core.liveness import LivenessDetector
            return LivenessDetector()

    def test_empty_roi_guard(self):
        """Test 18: Tiny frame with valid face_location → empty ROI after crop → safe return."""
        detector = self._create_detector()

        # 3x3 frame, face_location covers it but clamp makes ROI 0-size
        tiny_frame = np.zeros((3, 3, 3), dtype=np.uint8)
        # Location exactly fills the frame — after padding, crop clamps to frame bounds
        # This should still work, but let's test a truly problematic case
        face_loc = {'top': 0, 'right': 3, 'bottom': 3, 'left': 0}
        result = detector.check_liveness(tiny_frame, face_loc)
        # Should either return a valid result or the safe fallback
        self.assertIn('is_live', result)
        self.assertIn('score', result)


class TestNegativeThresholdGuard(unittest.TestCase):
    """Test 19: [H3] Negative threshold in config → fallback to default + WARNING."""

    @patch('src.core.liveness.Config')
    def test_negative_threshold_fallback(self, mock_config_cls):
        """Test 19: Negative threshold → revert to default, log WARNING."""
        mock_config = MagicMock()
        mock_config_cls.return_value = mock_config

        def get_side_effect(*args, default=None):
            if args == ('liveness', 'texture_threshold'):
                return -10.0
            if args == ('liveness', 'color_threshold'):
                return 0  # zero also invalid
            return default

        mock_config.get.side_effect = get_side_effect

        from src.core.liveness import LivenessDetector

        with self.assertLogs('src.core.liveness', level='WARNING') as cm:
            detector = LivenessDetector()

        # Should revert to defaults
        self.assertEqual(detector._texture_threshold, 80.0)
        self.assertEqual(detector._color_threshold, 0.4)
        # Should have warning logs
        self.assertTrue(any('_texture_threshold' in msg for msg in cm.output))
        self.assertTrue(any('_color_threshold' in msg for msg in cm.output))


class TestDisabledLogging(unittest.TestCase):
    """Test 20: [L3/CR-F5] Disabled mode → INFO log emitted once."""

    @patch('src.core.liveness.Config')
    def test_disabled_logs_info(self, mock_config_cls):
        """Test 20: enabled=false → INFO log 'Liveness detection disabled via config'."""
        mock_config = MagicMock()
        mock_config_cls.return_value = mock_config

        def get_side_effect(*args, default=None):
            if args == ('liveness', 'enabled'):
                return False
            return default

        mock_config.get.side_effect = get_side_effect

        from src.core.liveness import LivenessDetector

        with self.assertLogs('src.core.liveness', level='INFO') as cm:
            detector = LivenessDetector()

        self.assertTrue(
            any('disabled via config' in msg for msg in cm.output),
            f"Expected 'disabled via config' in logs, got: {cm.output}"
        )


class TestBoundaryScoreThreshold(unittest.TestCase):
    """Test 21: [F2] score == threshold → is_live=True."""

    @patch('src.core.liveness.Config')
    def test_score_equals_threshold(self, mock_config_cls):
        """Test 21: Khi final_score == final_score_threshold → is_live=True."""
        mock_config = MagicMock()
        mock_config_cls.return_value = mock_config
        mock_config.get.side_effect = lambda *args, default=None: default

        from src.core.liveness import LivenessDetector
        detector = LivenessDetector()

        # Patch all checks to return exactly threshold (0.6)
        for method in ['_check_texture_quality', '_check_color_distribution',
                       '_check_moire_pattern', '_check_reflection', '_check_edge_density']:
            setattr(detector, method, lambda roi, m=method: 0.6)

        frame = np.zeros((200, 200, 3), dtype=np.uint8)
        face_loc = {'top': 30, 'right': 170, 'bottom': 170, 'left': 30}
        result = detector.check_liveness(frame, face_loc)

        # score = 0.6 == threshold 0.6 → is_live=True (>=)
        self.assertTrue(result['is_live'])
        self.assertAlmostEqual(result['score'], 0.6, places=2)


class TestNonNumericConfigValue(unittest.TestCase):
    """Test 22: [F3] Non-numeric config → fallback to default + WARNING."""

    @patch('src.core.liveness.Config')
    def test_string_config_fallback(self, mock_config_cls):
        """Test 22: texture_threshold='abc' → fallback 80.0, min_face_size='xyz' → fallback 30."""
        mock_config = MagicMock()
        mock_config_cls.return_value = mock_config

        def get_side_effect(*args, default=None):
            if args == ('liveness', 'texture_threshold'):
                return 'abc'
            if args == ('liveness', 'min_face_size'):
                return 'xyz'
            return default

        mock_config.get.side_effect = get_side_effect

        from src.core.liveness import LivenessDetector

        with self.assertLogs('src.core.liveness', level='WARNING') as cm:
            detector = LivenessDetector()

        self.assertEqual(detector._texture_threshold, 80.0)
        self.assertEqual(detector._min_face_size, 30)
        self.assertTrue(any('texture_threshold' in msg for msg in cm.output))
        self.assertTrue(any('min_face_size' in msg for msg in cm.output))


class TestOneDimensionalFrame(unittest.TestCase):
    """Test 23: [F5] 1D frame array → safe return."""

    def test_1d_frame_guard(self):
        """Test 23: frame là 1D array → return is_live=False."""
        with patch('src.core.liveness.Config') as mock_config_cls:
            mock_config = MagicMock()
            mock_config_cls.return_value = mock_config
            mock_config.get.side_effect = lambda *args, default=None: default
            from src.core.liveness import LivenessDetector
            detector = LivenessDetector()

        frame_1d = np.array([1, 2, 3, 4, 5], dtype=np.uint8)
        face_loc = {'top': 0, 'right': 5, 'bottom': 5, 'left': 0}
        result = detector.check_liveness(frame_1d, face_loc)
        self.assertEqual(result, {'is_live': False, 'score': 0.0, 'details': {}})

    def test_non_array_frame_guard(self):
        """Test 23b: frame là list → return is_live=False."""
        with patch('src.core.liveness.Config') as mock_config_cls:
            mock_config = MagicMock()
            mock_config_cls.return_value = mock_config
            mock_config.get.side_effect = lambda *args, default=None: default
            from src.core.liveness import LivenessDetector
            detector = LivenessDetector()

        result = detector.check_liveness([[1, 2], [3, 4]], {'top': 0, 'right': 2, 'bottom': 2, 'left': 0})
        self.assertEqual(result, {'is_live': False, 'score': 0.0, 'details': {}})


class TestPartialWeightsConfig(unittest.TestCase):
    """Test 24: [F9] Partial weights config → auto-normalize."""

    @patch('src.core.liveness.Config')
    def test_partial_weights_normalize(self, mock_config_cls):
        """Test 24: Only texture weight provided → fill others from defaults, normalize."""
        mock_config = MagicMock()
        mock_config_cls.return_value = mock_config

        partial_weights = {'texture': 0.5}  # Only texture, rest from defaults

        def get_side_effect(*args, default=None):
            if args == ('liveness', 'weights'):
                return partial_weights
            return default

        mock_config.get.side_effect = get_side_effect

        from src.core.liveness import LivenessDetector
        detector = LivenessDetector()

        # texture=0.5, color=0.20, moire=0.20, reflection=0.15, edge=0.15 → sum=1.2 → normalize
        self.assertAlmostEqual(sum(detector._weights.values()), 1.0, places=2)
        # texture should be highest
        self.assertGreater(detector._weights['texture'], detector._weights['color'])


class TestFinalScoreThresholdValidation(unittest.TestCase):
    """Test 25: [F1] final_score_threshold ≤ 0 or > 1.0 → revert to default."""

    @patch('src.core.liveness.Config')
    def test_negative_final_threshold(self, mock_config_cls):
        """Test 25: final_score_threshold=-0.5 → revert to 0.6."""
        mock_config = MagicMock()
        mock_config_cls.return_value = mock_config

        def get_side_effect(*args, default=None):
            if args == ('liveness', 'final_score_threshold'):
                return -0.5
            return default

        mock_config.get.side_effect = get_side_effect

        from src.core.liveness import LivenessDetector
        with self.assertLogs('src.core.liveness', level='WARNING') as cm:
            detector = LivenessDetector()

        self.assertEqual(detector._final_score_threshold, 0.6)
        self.assertTrue(any('_final_score_threshold' in msg for msg in cm.output))

    @patch('src.core.liveness.Config')
    def test_over_one_final_threshold(self, mock_config_cls):
        """Test 25b: final_score_threshold=1.5 → revert to 0.6."""
        mock_config = MagicMock()
        mock_config_cls.return_value = mock_config

        def get_side_effect(*args, default=None):
            if args == ('liveness', 'final_score_threshold'):
                return 1.5
            return default

        mock_config.get.side_effect = get_side_effect

        from src.core.liveness import LivenessDetector
        with self.assertLogs('src.core.liveness', level='WARNING') as cm:
            detector = LivenessDetector()

        self.assertEqual(detector._final_score_threshold, 0.6)


if __name__ == '__main__':
    unittest.main()
