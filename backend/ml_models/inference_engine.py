"""
MediMark AI - AI Inference Engine
Combines YOLO detection + U-Net segmentation.
Fixed: bbox kwarg, PostgreSQL compatible.
"""

import cv2
import numpy as np
import json
import time
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class YOLOMedicalDetector:
    """YOLO detector — ultralytics → OpenCV DNN → mock fallback."""

    MOCK_LABELS = [
        'Pulmonary Nodule', 'Ground-glass Opacity', 'Consolidation',
        'Pleural Effusion', 'Cardiomegaly', 'Pneumothorax',
        'Mass Lesion', 'Calcification', 'Atelectasis', 'Infiltrate'
    ]

    def __init__(self, model_path: str, confidence_threshold: float = 0.45):
        self.model_path = model_path
        self.confidence_threshold = confidence_threshold
        self.model = None
        self.backend = 'mock'
        self._load()

    def _load(self):
        if not os.path.exists(self.model_path):
            logger.info("YOLO model not found — using mock mode")
            return
        try:
            from ultralytics import YOLO
            self.model = YOLO(self.model_path)
            self.backend = 'ultralytics'
        except Exception:
            try:
                self.model = cv2.dnn.readNet(self.model_path)
                self.backend = 'opencv_dnn'
            except Exception:
                pass

    def detect(self, image: np.ndarray) -> list:
        t0 = time.time()
        if self.backend == 'ultralytics':
            results = self._detect_ultralytics(image)
        elif self.backend == 'opencv_dnn':
            results = self._detect_opencv(image)
        else:
            results = self._detect_mock(image)
        ms = round((time.time() - t0) * 1000, 2)
        for r in results:
            r['inference_time_ms'] = ms
        return results

    def _detect_ultralytics(self, image):
        out = []
        h, w = image.shape[:2]
        for r in self.model(image, conf=self.confidence_threshold, verbose=False):
            for box in r.boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                out.append(self._fmt(r.names.get(int(box.cls[0]), 'unknown'),
                                     float(box.conf[0]), x1, y1, x2, y2, w, h))
        return out

    def _detect_opencv(self, image):
        h, w = image.shape[:2]
        blob = cv2.dnn.blobFromImage(image, 1/255.0, (640, 640), swapRB=True, crop=False)
        self.model.setInput(blob)
        out = []
        for layer in self.model.forward(self.model.getUnconnectedOutLayersNames()):
            for det in layer:
                scores = det[5:]
                cid = int(np.argmax(scores))
                conf = float(scores[cid])
                if conf >= self.confidence_threshold:
                    cx, cy, bw, bh = det[:4]
                    x1 = int((cx - bw/2) * w); y1 = int((cy - bh/2) * h)
                    x2 = int((cx + bw/2) * w); y2 = int((cy + bh/2) * h)
                    out.append(self._fmt(f'pathology_{cid}', conf,
                                         x1, y1, x2, y2, w, h))
        return out

    def _detect_mock(self, image):
        h, w = image.shape[:2]
        rng = np.random.default_rng(int(np.mean(image)) % 9999)
        n = int(rng.integers(2, 5))
        out = []
        for _ in range(n):
            cx, cy = rng.uniform(0.2, 0.8), rng.uniform(0.2, 0.8)
            bw, bh = rng.uniform(0.08, 0.25), rng.uniform(0.08, 0.25)
            x1, y1 = max(0.0, cx-bw/2)*w, max(0.0, cy-bh/2)*h
            x2, y2 = min(1.0, cx+bw/2)*w, min(1.0, cy+bh/2)*h
            label = self.MOCK_LABELS[rng.integers(0, len(self.MOCK_LABELS))]
            conf  = float(rng.uniform(0.52, 0.95))
            out.append(self._fmt(label, conf, x1, y1, x2, y2, w, h))
        return out

    @staticmethod
    def _fmt(label, conf, x1, y1, x2, y2, w, h):
        return {
            'label':      label,
            'confidence': round(float(conf), 4),
            'x_min':      round(float(max(0,x1))/w, 4),
            'y_min':      round(float(max(0,y1))/h, 4),
            'x_max':      round(float(min(w,x2))/w, 4),
            'y_max':      round(float(min(h,y2))/h, 4),
            'x_min_px':   int(max(0,x1)),
            'y_min_px':   int(max(0,y1)),
            'x_max_px':   int(min(w,x2)),
            'y_max_px':   int(min(h,y2)),
            'inference_time_ms': 0.0,
        }


class UNetSegmentor:
    """U-Net segmentor — TensorFlow → PyTorch → mock fallback."""

    def __init__(self, model_path: str, threshold: float = 0.5,
                 input_size: tuple = (256, 256)):
        self.model_path = model_path
        self.threshold  = threshold
        self.input_size = input_size
        self.model   = None
        self.backend = 'mock'
        self._load()

    def _load(self):
        if not os.path.exists(self.model_path):
            logger.info("U-Net model not found — using mock mode")
            return
        ext = Path(self.model_path).suffix.lower()
        if ext in ('.h5', '.keras', '.pb'):
            try:
                import tensorflow as tf
                self.model   = tf.keras.models.load_model(self.model_path, compile=False)
                self.backend = 'tensorflow'
                return
            except Exception: pass
        if ext in ('.pt', '.pth'):
            try:
                import torch
                self.model   = torch.load(self.model_path, map_location='cpu')
                self.model.eval()
                self.backend = 'pytorch'
            except Exception: pass

    # ── FIX: bbox is now a positional-or-keyword arg, default None ──
    def segment(self, image: np.ndarray, bbox=None) -> list:
        """
        Run segmentation. bbox is optional dict with x_min/y_min/x_max/y_max.
        """
        h, w = image.shape[:2]
        if self.backend == 'tensorflow':
            return self._seg_tf(image, bbox, h, w)
        elif self.backend == 'pytorch':
            return self._seg_torch(image, bbox, h, w)
        else:
            return self._seg_mock(image, bbox, h, w)

    def _crop_roi(self, image, bbox, h, w):
        if not bbox:
            return image, 0, 0
        x1 = int(bbox.get('x_min', 0) * w)
        y1 = int(bbox.get('y_min', 0) * h)
        x2 = int(bbox.get('x_max', 1) * w)
        y2 = int(bbox.get('y_max', 1) * h)
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        if x2 <= x1 or y2 <= y1:
            return image, 0, 0
        return image[y1:y2, x1:x2], x1, y1

    def _pred_to_segs(self, pred, rw, rh, ox, oy, img_w, img_h):
        mask = (pred > self.threshold).astype(np.uint8) * 255
        mask = cv2.resize(mask, (rw, rh))
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        out = []
        for cnt in contours:
            if cv2.contourArea(cnt) < 100:
                continue
            eps    = 0.02 * cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, eps, True)
            pts_px = [[int(p[0][0]+ox), int(p[0][1]+oy)] for p in approx]
            pts_nm = [[round(p[0]/img_w, 4), round(p[1]/img_h, 4)] for p in pts_px]
            roi_vals = pred[mask > 0]
            conf = float(np.mean(roi_vals)) if roi_vals.size else 0.0
            out.append({'polygon_points': pts_px, 'normalized_points': pts_nm,
                        'area_px': int(cv2.contourArea(cnt)), 'confidence': round(conf, 4)})
        return out

    def _seg_tf(self, image, bbox, h, w):
        roi, ox, oy = self._crop_roi(image, bbox, h, w)
        rh, rw = roi.shape[:2]
        inp  = cv2.resize(roi, self.input_size).astype(np.float32) / 255.0
        pred = self.model.predict(np.expand_dims(inp, 0), verbose=0)[0, :, :, 0]
        return self._pred_to_segs(pred, rw, rh, ox, oy, w, h)

    def _seg_torch(self, image, bbox, h, w):
        import torch
        roi, ox, oy = self._crop_roi(image, bbox, h, w)
        rh, rw = roi.shape[:2]
        inp    = cv2.resize(roi, self.input_size).astype(np.float32) / 255.0
        tensor = torch.from_numpy(inp.transpose(2,0,1)).unsqueeze(0)
        with torch.no_grad():
            pred = self.model(tensor)[0, 0].numpy()
        return self._pred_to_segs(pred, rw, rh, ox, oy, w, h)

    def _seg_mock(self, image, bbox, h, w):
        gray    = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (15, 15), 0)
        _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        kernel  = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
        cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN,  kernel)
        if bbox:
            mask = np.zeros_like(cleaned)
            x1 = int(bbox.get('x_min', 0) * w)
            y1 = int(bbox.get('y_min', 0) * h)
            x2 = int(bbox.get('x_max', 1) * w)
            y2 = int(bbox.get('y_max', 1) * h)
            mask[y1:y2, x1:x2] = cleaned[y1:y2, x1:x2]
            cleaned = mask
        contours, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        rng = np.random.default_rng(int(np.mean(image)) % 9999)
        out = []
        for cnt in sorted(contours, key=cv2.contourArea, reverse=True)[:3]:
            if cv2.contourArea(cnt) < 300:
                continue
            eps    = 0.015 * cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, eps, True)
            pts_px = approx.reshape(-1, 2).tolist()
            pts_nm = [[round(p[0]/w, 4), round(p[1]/h, 4)] for p in pts_px]
            out.append({
                'polygon_points':    pts_px,
                'normalized_points': pts_nm,
                'area_px':           int(cv2.contourArea(cnt)),
                'confidence':        round(float(rng.uniform(0.58, 0.93)), 4),
                'label':             bbox.get('label', 'Region of Interest') if bbox else 'ROI',
            })
        return out


class MedicalImagePreprocessor:
    @staticmethod
    def load(file_path: str) -> np.ndarray:
        ext = Path(file_path).suffix.lower()
        if ext == '.dcm':
            try:
                import pydicom
                dcm = pydicom.dcmread(file_path)
                arr = dcm.pixel_array.astype(np.float32)
                arr = ((arr - arr.min()) / max(arr.max() - arr.min(), 1) * 255).astype(np.uint8)
                if len(arr.shape) == 2:
                    arr = cv2.cvtColor(arr, cv2.COLOR_GRAY2BGR)
                return arr
            except ImportError:
                pass
        img = cv2.imread(file_path)
        if img is None:
            raise ValueError(f"Cannot read image: {file_path}")
        return img

    @staticmethod
    def enhance(image: np.ndarray) -> np.ndarray:
        try:
            if len(image.shape) == 3:
                lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
                l, a, b = cv2.split(lab)
                clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
                enhanced = cv2.cvtColor(cv2.merge([clahe.apply(l), a, b]), cv2.COLOR_LAB2BGR)
            else:
                clahe    = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
                enhanced = clahe.apply(image)
            return cv2.fastNlMeansDenoisingColored(enhanced, None, 8, 8, 7, 21)
        except Exception:
            return image

    @staticmethod
    def metadata(image: np.ndarray) -> dict:
        h, w = image.shape[:2]
        c = image.shape[2] if len(image.shape) == 3 else 1
        return {'width': w, 'height': h, 'channels': c,
                'mean_intensity': round(float(np.mean(image)), 2)}


class AIInferenceEngine:
    """Orchestrates YOLO + U-Net pipeline."""

    def __init__(self, yolo_model_path, unet_model_path,
                 yolo_confidence=0.45, unet_threshold=0.5):
        self.detector    = YOLOMedicalDetector(yolo_model_path, yolo_confidence)
        self.segmentor   = UNetSegmentor(unet_model_path, unet_threshold)
        self.preprocessor = MedicalImagePreprocessor()

    def process_image(self, image_path: str) -> dict:
        t0 = time.time()

        image    = self.preprocessor.load(image_path)
        enhanced = self.preprocessor.enhance(image)
        metadata = self.preprocessor.metadata(image)

        # YOLO detection
        t_det = time.time()
        detections = self.detector.detect(enhanced)
        det_ms = round((time.time() - t_det) * 1000, 2)

        # U-Net segmentation — FIX: pass bbox as positional arg, not keyword
        t_seg = time.time()
        segmentations = []
        for det in detections:
            # Pass bbox dict directly as positional argument
            segs = self.segmentor.segment(enhanced, det)
            for seg in segs:
                seg['label'] = det['label']
                seg['detection_confidence'] = det['confidence']
                segmentations.append(seg)

        if not detections:
            segs = self.segmentor.segment(enhanced)
            segmentations.extend(segs)
        seg_ms = round((time.time() - t_seg) * 1000, 2)

        total_ms = round((time.time() - t0) * 1000, 2)
        avg_conf = float(np.mean([d['confidence'] for d in detections])) if detections else 0.0

        return {
            'detections':       detections,
            'segmentations':    segmentations,
            'metadata':         metadata,
            'performance':      {'total_ms': total_ms, 'detection_ms': det_ms,
                                 'segmentation_ms': seg_ms},
            'num_detections':   len(detections),
            'num_segmentations': len(segmentations),
            'avg_confidence':   round(avg_conf, 4),
            'model_info':       {'yolo_backend': self.detector.backend,
                                 'unet_backend': self.segmentor.backend},
        }
