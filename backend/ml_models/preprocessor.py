"""
MediMark AI — Medical Image Preprocessor
Handles loading, enhancement, and normalization of medical images
including DICOM (.dcm), TIFF, and standard raster formats.
"""

import cv2
import numpy as np
import os
import logging
from pathlib import Path
from typing import Optional, Tuple, Dict

logger = logging.getLogger(__name__)


class MedicalImagePreprocessor:
    """
    Full preprocessing pipeline:
      load → normalize → enhance (CLAHE) → denoise → thumbnail
    """

    SUPPORTED_EXTS = {'.png', '.jpg', '.jpeg', '.tiff', '.tif',
                      '.bmp', '.webp', '.dcm'}

    # ── Loading ───────────────────────────────────────────────
    @staticmethod
    def load(file_path: str) -> np.ndarray:
        """
        Load a medical image from disk.
        Supports DICOM (via pydicom) and all OpenCV-readable formats.
        Returns a BGR uint8 ndarray.
        """
        ext = Path(file_path).suffix.lower()

        if ext == '.dcm':
            return MedicalImagePreprocessor._load_dicom(file_path)

        img = cv2.imread(file_path, cv2.IMREAD_UNCHANGED)
        if img is None:
            raise ValueError(f"Cannot read image: {file_path}")

        # 16-bit grayscale → 8-bit
        if img.dtype == np.uint16:
            img = cv2.normalize(img, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)

        # Grayscale → BGR
        if len(img.shape) == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        elif img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

        return img

    @staticmethod
    def _load_dicom(file_path: str) -> np.ndarray:
        try:
            import pydicom
            dcm = pydicom.dcmread(file_path)
            arr = dcm.pixel_array.astype(np.float32)

            # Apply DICOM window/level if available
            wc = float(getattr(dcm, 'WindowCenter', arr.mean()))
            ww = float(getattr(dcm, 'WindowWidth',  arr.std() * 4 or 256))
            lo = wc - ww / 2
            hi = wc + ww / 2
            arr = np.clip(arr, lo, hi)
            arr = ((arr - lo) / (hi - lo) * 255).astype(np.uint8)

            if len(arr.shape) == 2:
                arr = cv2.cvtColor(arr, cv2.COLOR_GRAY2BGR)
            return arr
        except ImportError:
            logger.warning("pydicom not installed; attempting OpenCV fallback for DICOM")
            img = cv2.imread(file_path)
            if img is None:
                raise ValueError(f"Cannot read DICOM without pydicom: {file_path}")
            return img

    # ── Enhancement ───────────────────────────────────────────
    @staticmethod
    def enhance(image: np.ndarray,
                clip_limit: float = 3.0,
                tile_grid: Tuple[int, int] = (8, 8),
                denoise: bool = True) -> np.ndarray:
        """
        Apply CLAHE contrast enhancement and optional non-local-means denoising.
        Works on both grayscale and colour images.
        """
        if len(image.shape) == 3:
            lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid)
            l_eq  = clahe.apply(l)
            enhanced = cv2.cvtColor(cv2.merge([l_eq, a, b]), cv2.COLOR_LAB2BGR)
        else:
            clahe    = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid)
            enhanced = clahe.apply(image)

        if denoise:
            try:
                if len(enhanced.shape) == 3:
                    enhanced = cv2.fastNlMeansDenoisingColored(
                        enhanced, None, 8, 8, 7, 21)
                else:
                    enhanced = cv2.fastNlMeansDenoising(
                        enhanced, None, 10, 7, 21)
            except Exception as e:
                logger.debug("Denoising skipped: %s", e)

        return enhanced

    # ── Thumbnail ─────────────────────────────────────────────
    @staticmethod
    def thumbnail(image: np.ndarray,
                  size: Tuple[int, int] = (256, 256),
                  keep_aspect: bool = True) -> np.ndarray:
        if not keep_aspect:
            return cv2.resize(image, size, interpolation=cv2.INTER_AREA)

        h, w = image.shape[:2]
        scale = min(size[0] / w, size[1] / h)
        nw, nh = int(w * scale), int(h * scale)
        resized = cv2.resize(image, (nw, nh), interpolation=cv2.INTER_AREA)

        # Pad to exact size
        canvas = np.zeros((size[1], size[0], 3), dtype=np.uint8)
        ox = (size[0] - nw) // 2
        oy = (size[1] - nh) // 2
        canvas[oy:oy + nh, ox:ox + nw] = resized
        return canvas

    # ── Metadata ──────────────────────────────────────────────
    @staticmethod
    def metadata(image: np.ndarray) -> Dict:
        h, w = image.shape[:2]
        c = image.shape[2] if len(image.shape) == 3 else 1
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if c == 3 else image
        return {
            'width':           w,
            'height':          h,
            'channels':        c,
            'dtype':           str(image.dtype),
            'mean_intensity':  round(float(np.mean(gray)), 2),
            'std_intensity':   round(float(np.std(gray)), 2),
            'min_intensity':   int(gray.min()),
            'max_intensity':   int(gray.max()),
            'aspect_ratio':    round(w / h, 4),
        }

    # ── Pipeline ──────────────────────────────────────────────
    def process(self, file_path: str,
                thumb_path: Optional[str] = None) -> Dict:
        """
        Full pipeline: load → enhance → metadata → optional thumbnail save.
        Returns dict with keys: image, enhanced, metadata, thumb.
        """
        image    = self.load(file_path)
        enhanced = self.enhance(image)
        meta     = self.metadata(image)

        thumb = None
        if thumb_path:
            thumb = self.thumbnail(enhanced)
            os.makedirs(os.path.dirname(thumb_path), exist_ok=True)
            cv2.imwrite(thumb_path, thumb, [cv2.IMWRITE_JPEG_QUALITY, 85])

        return {
            'image':    image,
            'enhanced': enhanced,
            'metadata': meta,
            'thumb':    thumb,
        }
