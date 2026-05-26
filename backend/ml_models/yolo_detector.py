"""
MediMark AI — YOLO Medical Detector
Standalone wrapper supporting ultralytics, OpenCV DNN, and mock backends.
Import via: from backend.ml_models.yolo_detector import YOLOMedicalDetector
"""

import cv2
import numpy as np
import time
import os
import logging

logger = logging.getLogger(__name__)

# 10 common radiological pathologies used in mock mode
MOCK_PATHOLOGIES = [
    'Pulmonary Nodule',
    'Ground-glass Opacity',
    'Consolidation',
    'Pleural Effusion',
    'Cardiomegaly',
    'Pneumothorax',
    'Mass Lesion',
    'Calcification',
    'Atelectasis',
    'Infiltrate',
]


class YOLOMedicalDetector:
    """
    YOLO detector for medical images.

    Backends (tried in order):
      1. ultralytics YOLO  — if model is .pt and ultralytics is installed
      2. OpenCV DNN        — fallback for ONNX / darknet weights
      3. mock              — synthetic bboxes for development / demo
    """

    def __init__(self, model_path: str,
                 confidence_threshold: float = 0.45,
                 nms_threshold: float = 0.4):
        self.model_path           = model_path
        self.confidence_threshold = confidence_threshold
        self.nms_threshold        = nms_threshold
        self.model                = None
        self.backend              = 'mock'
        self._load()

    # ── Loading ───────────────────────────────────────────────
    def _load(self):
        if not os.path.exists(self.model_path):
            logger.warning("YOLO: model not found at %s — using mock", self.model_path)
            return

        ext = os.path.splitext(self.model_path)[1].lower()

        if ext in ('.pt', '.yaml'):
            try:
                from ultralytics import YOLO
                self.model   = YOLO(self.model_path)
                self.backend = 'ultralytics'
                logger.info("YOLO loaded via ultralytics")
                return
            except Exception as e:
                logger.warning("ultralytics unavailable: %s", e)

        try:
            self.model   = cv2.dnn.readNet(self.model_path)
            self.backend = 'opencv_dnn'
            logger.info("YOLO loaded via OpenCV DNN")
        except Exception as e:
            logger.error("OpenCV DNN load failed: %s — using mock", e)

    # ── Public API ────────────────────────────────────────────
    def detect(self, image: np.ndarray) -> list:
        """
        Detect pathologies in a BGR image.
        Returns a list of dicts with keys:
          label, confidence, x_min, y_min, x_max, y_max (all normalised 0-1)
          x_min_px, y_min_px, x_max_px, y_max_px (pixel coords)
          inference_time_ms
        """
        t0 = time.time()
        if self.backend == 'ultralytics':
            result = self._detect_ultralytics(image)
        elif self.backend == 'opencv_dnn':
            result = self._detect_opencv(image)
        else:
            result = self._detect_mock(image)
        ms = round((time.time() - t0) * 1000, 2)
        for det in result:
            det['inference_time_ms'] = ms
        return result

    # ── Ultralytics backend ───────────────────────────────────
    def _detect_ultralytics(self, image: np.ndarray) -> list:
        results = self.model(image, conf=self.confidence_threshold, verbose=False)
        h, w   = image.shape[:2]
        out    = []
        for r in results:
            for box in r.boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                conf = float(box.conf[0])
                cid  = int(box.cls[0])
                name = r.names.get(cid, f'class_{cid}')
                out.append(self._det(name, conf, x1, y1, x2, y2, w, h))
        return out

    # ── OpenCV DNN backend ────────────────────────────────────
    def _detect_opencv(self, image: np.ndarray) -> list:
        h, w = image.shape[:2]
        blob = cv2.dnn.blobFromImage(image, 1/255.0, (640, 640),
                                      swapRB=True, crop=False)
        self.model.setInput(blob)
        layers = self.model.getUnconnectedOutLayersNames()
        outputs = self.model.forward(layers)
        boxes, confs, class_ids = [], [], []
        for layer in outputs:
            for det in layer:
                scores = det[5:]
                cid    = int(np.argmax(scores))
                conf   = float(scores[cid])
                if conf < self.confidence_threshold:
                    continue
                cx, cy, bw, bh = det[:4]
                x1 = int((cx - bw / 2) * w)
                y1 = int((cy - bh / 2) * h)
                boxes.append([x1, y1, int(bw * w), int(bh * h)])
                confs.append(conf)
                class_ids.append(cid)
        idxs = cv2.dnn.NMSBoxes(boxes, confs,
                                  self.confidence_threshold,
                                  self.nms_threshold)
        out = []
        for i in (idxs.flatten() if len(idxs) else []):
            bx, by, bw, bh = boxes[i]
            out.append(self._det(f'pathology_{class_ids[i]}', confs[i],
                                 bx, by, bx + bw, by + bh, w, h))
        return out

    # ── Mock backend ──────────────────────────────────────────
    def _detect_mock(self, image: np.ndarray) -> list:
        h, w = image.shape[:2]
        seed = int(np.mean(image)) % 1000
        rng  = np.random.default_rng(seed)
        n    = int(rng.integers(1, 5))
        out  = []
        for _ in range(n):
            cx = rng.uniform(0.2, 0.8)
            cy = rng.uniform(0.2, 0.8)
            bw = rng.uniform(0.08, 0.25)
            bh = rng.uniform(0.08, 0.25)
            x1 = max(0.0, cx - bw / 2) * w
            y1 = max(0.0, cy - bh / 2) * h
            x2 = min(1.0, cx + bw / 2) * w
            y2 = min(1.0, cy + bh / 2) * h
            conf  = float(rng.uniform(0.52, 0.96))
            label = MOCK_PATHOLOGIES[rng.integers(0, len(MOCK_PATHOLOGIES))]
            out.append(self._det(label, conf, x1, y1, x2, y2, w, h))
        return out

    # ── Helpers ───────────────────────────────────────────────
    @staticmethod
    def _det(label, conf, x1, y1, x2, y2, w, h) -> dict:
        x1, y1, x2, y2 = (max(0, x1), max(0, y1),
                           min(w, x2), min(h, y2))
        return {
            'label':          label,
            'confidence':     round(float(conf), 4),
            'x_min':          round(x1 / w, 4),
            'y_min':          round(y1 / h, 4),
            'x_max':          round(x2 / w, 4),
            'y_max':          round(y2 / h, 4),
            'x_min_px':       int(x1),
            'y_min_px':       int(y1),
            'x_max_px':       int(x2),
            'y_max_px':       int(y2),
            'inference_time_ms': 0.0,
        }

    @property
    def is_live(self) -> bool:
        return self.backend in ('ultralytics', 'opencv_dnn')

    def __repr__(self):
        return f"<YOLOMedicalDetector backend={self.backend}>"
