"""
MediMark AI — U-Net Medical Segmentor
Standalone wrapper supporting TensorFlow, PyTorch, and mock (OpenCV) backends.
Import via: from backend.ml_models.unet_segmentor import UNetSegmentor
"""

import cv2
import numpy as np
import time
import os
import logging

logger = logging.getLogger(__name__)


class UNetSegmentor:
    """
    U-Net segmentor for medical images.

    Backends (tried in order):
      1. TensorFlow/Keras  — if model ends in .h5 / .keras / .pb
      2. PyTorch           — if model ends in .pt / .pth
      3. mock              — OpenCV-based pseudo-segmentation for dev/demo
    """

    def __init__(self, model_path: str,
                 threshold: float = 0.5,
                 input_size: tuple = (256, 256)):
        self.model_path = model_path
        self.threshold  = threshold
        self.input_size = input_size   # (W, H)
        self.model      = None
        self.backend    = 'mock'
        self._load()

    # ── Loading ───────────────────────────────────────────────
    def _load(self):
        if not os.path.exists(self.model_path):
            logger.warning("U-Net: model not found at %s — using mock", self.model_path)
            return

        ext = os.path.splitext(self.model_path)[1].lower()

        if ext in ('.h5', '.keras', '.pb', '.savedmodel'):
            try:
                import tensorflow as tf
                self.model   = tf.keras.models.load_model(self.model_path, compile=False)
                self.backend = 'tensorflow'
                logger.info("U-Net loaded via TensorFlow")
                return
            except Exception as e:
                logger.warning("TensorFlow load failed: %s", e)

        if ext in ('.pt', '.pth'):
            try:
                import torch
                self.model   = torch.load(self.model_path, map_location='cpu')
                self.model.eval()
                self.backend = 'pytorch'
                logger.info("U-Net loaded via PyTorch")
                return
            except Exception as e:
                logger.warning("PyTorch load failed: %s", e)

        logger.warning("U-Net: no compatible framework — using mock")

    # ── Public API ────────────────────────────────────────────
    def segment(self, image: np.ndarray,
                bbox: dict = None) -> list:
        """
        Segment the image (optionally within a bounding box).
        Returns list of dicts with keys:
          polygon_points      — list of [x, y] in pixel space
          normalized_points   — list of [x, y] in 0-1 space
          area_px             — contour area in pixels
          confidence          — float 0-1
          label               — propagated from bbox if provided
          mask_path           — path if mask was saved (optional)
        """
        t0 = time.time()
        h, w = image.shape[:2]

        if self.backend == 'tensorflow':
            result = self._seg_tf(image, bbox, h, w)
        elif self.backend == 'pytorch':
            result = self._seg_torch(image, bbox, h, w)
        else:
            result = self._seg_mock(image, bbox, h, w)

        ms = round((time.time() - t0) * 1000, 2)
        for seg in result:
            seg['inference_time_ms'] = ms
        return result

    # ── TensorFlow backend ────────────────────────────────────
    def _seg_tf(self, image, bbox, h, w):
        roi, ox, oy = self._crop_roi(image, bbox, h, w)
        rh, rw = roi.shape[:2]
        inp  = cv2.resize(roi, self.input_size).astype(np.float32) / 255.0
        inp  = np.expand_dims(inp, 0)
        pred = self.model.predict(inp, verbose=0)[0, :, :, 0]
        return self._pred_to_segs(pred, rw, rh, ox, oy, w, h)

    # ── PyTorch backend ───────────────────────────────────────
    def _seg_torch(self, image, bbox, h, w):
        import torch
        roi, ox, oy = self._crop_roi(image, bbox, h, w)
        rh, rw = roi.shape[:2]
        inp  = cv2.resize(roi, self.input_size).astype(np.float32) / 255.0
        tensor = torch.from_numpy(inp.transpose(2, 0, 1)).unsqueeze(0)
        with torch.no_grad():
            pred = self.model(tensor)[0, 0].numpy()
        return self._pred_to_segs(pred, rw, rh, ox, oy, w, h)

    # ── Mock (OpenCV) backend ─────────────────────────────────
    def _seg_mock(self, image, bbox, h, w):
        gray    = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (15, 15), 0)
        _, thresh = cv2.threshold(blurred, 0, 255,
                                   cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        kernel  = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
        cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN,  kernel)

        if bbox:
            mask = np.zeros_like(cleaned)
            x1 = int(bbox['x_min'] * w)
            y1 = int(bbox['y_min'] * h)
            x2 = int(bbox['x_max'] * w)
            y2 = int(bbox['y_max'] * h)
            mask[y1:y2, x1:x2] = cleaned[y1:y2, x1:x2]
            cleaned = mask

        contours, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL,
                                        cv2.CHAIN_APPROX_SIMPLE)
        rng = np.random.default_rng(int(np.mean(image)) % 9999)
        out = []
        for cnt in sorted(contours, key=cv2.contourArea, reverse=True)[:3]:
            area = cv2.contourArea(cnt)
            if area < 300:
                continue
            eps   = 0.015 * cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, eps, True)
            pts    = approx.reshape(-1, 2).tolist()
            norm   = [[round(p[0] / w, 4), round(p[1] / h, 4)] for p in pts]
            out.append({
                'polygon_points':    pts,
                'normalized_points': norm,
                'area_px':           int(area),
                'confidence':        round(float(rng.uniform(0.58, 0.93)), 4),
                'label':             bbox.get('label', 'Region of Interest') if bbox else 'Region of Interest',
            })
        return out

    # ── Helpers ───────────────────────────────────────────────
    def _crop_roi(self, image, bbox, h, w):
        if not bbox:
            return image, 0, 0
        x1 = int(bbox['x_min'] * w)
        y1 = int(bbox['y_min'] * h)
        x2 = int(bbox['x_max'] * w)
        y2 = int(bbox['y_max'] * h)
        return image[y1:y2, x1:x2], x1, y1

    def _pred_to_segs(self, pred, rw, rh, ox, oy, img_w, img_h):
        mask = (pred > self.threshold).astype(np.uint8) * 255
        mask = cv2.resize(mask, (rw, rh))
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL,
                                        cv2.CHAIN_APPROX_SIMPLE)
        out = []
        for cnt in contours:
            if cv2.contourArea(cnt) < 100:
                continue
            eps   = 0.02 * cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, eps, True)
            pts_px = [[int(p[0][0] + ox), int(p[0][1] + oy)] for p in approx]
            pts_nm = [[round(p[0] / img_w, 4), round(p[1] / img_h, 4)] for p in pts_px]
            roi_vals = pred[mask > 0]
            conf = float(np.mean(roi_vals)) if roi_vals.size else 0.0
            out.append({
                'polygon_points':    pts_px,
                'normalized_points': pts_nm,
                'area_px':           int(cv2.contourArea(cnt)),
                'confidence':        round(conf, 4),
                'label':             'Segmented Region',
            })
        return out

    @property
    def is_live(self) -> bool:
        return self.backend in ('tensorflow', 'pytorch')

    def __repr__(self):
        return f"<UNetSegmentor backend={self.backend} threshold={self.threshold}>"
