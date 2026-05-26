"""
MediMark AI — ML Model Unit Tests
Tests YOLO detector, U-Net segmentor, and preprocessor in mock/OpenCV mode.
"""

import pytest
import numpy as np
import cv2


@pytest.fixture
def sample_image():
    """128×128 synthetic chest-like image."""
    img = np.zeros((128, 128, 3), dtype=np.uint8)
    # Simulate lung fields
    cv2.ellipse(img, (40, 64),  (30, 45), 0, 0, 360, (160, 160, 160), -1)
    cv2.ellipse(img, (88, 64),  (30, 45), 0, 0, 360, (160, 160, 160), -1)
    # Simulate nodule
    cv2.circle(img, (50, 50), 8, (220, 220, 220), -1)
    return img


class TestYOLODetector:

    def _detector(self):
        from backend.ml_models.yolo_detector import YOLOMedicalDetector
        return YOLOMedicalDetector(model_path='nonexistent_model.pt')

    def test_backend_is_mock(self):
        det = self._detector()
        assert det.backend == 'mock'
        assert not det.is_live

    def test_detect_returns_list(self, sample_image):
        det    = self._detector()
        result = det.detect(sample_image)
        assert isinstance(result, list)

    def test_detect_has_required_keys(self, sample_image):
        det    = self._detector()
        result = det.detect(sample_image)
        assert len(result) > 0
        for det_item in result:
            for key in ('label', 'confidence', 'x_min', 'y_min', 'x_max', 'y_max'):
                assert key in det_item, f"Missing key: {key}"

    def test_detect_normalized_coords(self, sample_image):
        det    = self._detector()
        result = det.detect(sample_image)
        for d in result:
            assert 0.0 <= d['x_min'] < d['x_max'] <= 1.0
            assert 0.0 <= d['y_min'] < d['y_max'] <= 1.0

    def test_detect_confidence_range(self, sample_image):
        det    = self._detector()
        result = det.detect(sample_image)
        for d in result:
            assert 0.0 <= d['confidence'] <= 1.0

    def test_detect_reproducible(self, sample_image):
        det = self._detector()
        r1  = det.detect(sample_image)
        r2  = det.detect(sample_image)
        assert len(r1) == len(r2)
        for a, b in zip(r1, r2):
            assert a['label']      == b['label']
            assert a['confidence'] == b['confidence']


class TestUNetSegmentor:

    def _segmentor(self):
        from backend.ml_models.unet_segmentor import UNetSegmentor
        return UNetSegmentor(model_path='nonexistent_unet.h5')

    def test_backend_is_mock(self):
        seg = self._segmentor()
        assert seg.backend == 'mock'
        assert not seg.is_live

    def test_segment_returns_list(self, sample_image):
        seg    = self._segmentor()
        result = seg.segment(sample_image)
        assert isinstance(result, list)

    def test_segment_with_bbox(self, sample_image):
        seg  = self._segmentor()
        bbox = {'x_min': 0.1, 'y_min': 0.1, 'x_max': 0.6, 'y_max': 0.6}
        result = seg.segment(sample_image, bbox=bbox)
        assert isinstance(result, list)

    def test_segment_has_required_keys(self, sample_image):
        seg    = self._segmentor()
        result = seg.segment(sample_image)
        for s in result:
            assert 'polygon_points'    in s
            assert 'normalized_points' in s
            assert 'area_px'           in s
            assert 'confidence'        in s

    def test_segment_confidence_range(self, sample_image):
        seg    = self._segmentor()
        result = seg.segment(sample_image)
        for s in result:
            assert 0.0 <= s['confidence'] <= 1.0

    def test_segment_polygon_has_enough_points(self, sample_image):
        seg    = self._segmentor()
        result = seg.segment(sample_image)
        for s in result:
            assert len(s['polygon_points']) >= 3


class TestPreprocessor:

    def _prep(self):
        from backend.ml_models.preprocessor import MedicalImagePreprocessor
        return MedicalImagePreprocessor()

    def test_enhance_returns_same_shape(self, sample_image):
        prep     = self._prep()
        enhanced = prep.enhance(sample_image)
        assert enhanced.shape == sample_image.shape

    def test_thumbnail_correct_size(self, sample_image):
        prep  = self._prep()
        thumb = prep.thumbnail(sample_image, size=(64, 64))
        assert thumb.shape[:2] == (64, 64)

    def test_metadata_keys(self, sample_image):
        prep = self._prep()
        meta = prep.metadata(sample_image)
        for key in ('width', 'height', 'channels',
                    'mean_intensity', 'std_intensity'):
            assert key in meta

    def test_metadata_correct_dims(self, sample_image):
        prep = self._prep()
        meta = prep.metadata(sample_image)
        assert meta['width']    == 128
        assert meta['height']   == 128
        assert meta['channels'] == 3
