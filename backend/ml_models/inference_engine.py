"""
MediMark AI - AI Inference Engine
Integrates YOLO (detection) and U-Net (segmentation) models
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
    """
    YOLO-based medical anomaly detection.
    Supports YOLOv8/YOLOv5 via ultralytics or OpenCV DNN.
    Falls back to a mock detector when no model file is available (dev mode).
    """

    def __init__(self, model_path: str, confidence_threshold: float = 0.45):
        self.model_path = model_path
        self.confidence_threshold = confidence_threshold
        self.model = None
        self.backend = None
        self._load_model()

    def _load_model(self):
        if not os.path.exists(self.model_path):
            logger.warning(f"YOLO model not found at {self.model_path}. Using mock detector.")
            self.backend = 'mock'
            return

        try:
            from ultralytics import YOLO
            self.model = YOLO(self.model_path)
            self.backend = 'ultralytics'
            logger.info(f"YOLO model loaded via ultralytics from {self.model_path}")
        except ImportError:
            try:
                self.model = cv2.dnn.readNet(self.model_path)
                self.backend = 'opencv_dnn'
                logger.info(f"YOLO model loaded via OpenCV DNN from {self.model_path}")
            except Exception as e:
                logger.error(f"Failed to load YOLO model: {e}")
                self.backend = 'mock'

    def detect(self, image: np.ndarray) -> list:
        """
        Run detection on a BGR image.
        Returns list of dicts: {label, confidence, x_min, y_min, x_max, y_max}
        """
        start_time = time.time()

        if self.backend == 'ultralytics':
            return self._detect_ultralytics(image, start_time)
        elif self.backend == 'opencv_dnn':
            return self._detect_opencv(image, start_time)
        else:
            return self._detect_mock(image, start_time)

    def _detect_ultralytics(self, image: np.ndarray, start_time: float) -> list:
        results = self.model(image, conf=self.confidence_threshold)
        detections = []
        h, w = image.shape[:2]

        for result in results:
            for box in result.boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                conf = float(box.conf[0])
                cls_id = int(box.cls[0])
                label = result.names.get(cls_id, f'class_{cls_id}')

                detections.append({
                    'label': label,
                    'confidence': round(conf, 4),
                    'x_min': round(x1 / w, 4),
                    'y_min': round(y1 / h, 4),
                    'x_max': round(x2 / w, 4),
                    'y_max': round(y2 / h, 4),
                    'x_min_px': int(x1),
                    'y_min_px': int(y1),
                    'x_max_px': int(x2),
                    'y_max_px': int(y2),
                    'inference_time_ms': round((time.time() - start_time) * 1000, 2)
                })
        return detections

    def _detect_opencv(self, image: np.ndarray, start_time: float) -> list:
        """OpenCV DNN backend for YOLO inference"""
        h, w = image.shape[:2]
        blob = cv2.dnn.blobFromImage(image, 1/255.0, (640, 640),
                                      swapRB=True, crop=False)
        self.model.setInput(blob)
        output_layers = self.model.getUnconnectedOutLayersNames()
        outputs = self.model.forward(output_layers)

        detections = []
        for output in outputs:
            for detection in output:
                scores = detection[5:]
                class_id = np.argmax(scores)
                confidence = float(scores[class_id])
                if confidence > self.confidence_threshold:
                    cx, cy, bw, bh = detection[:4]
                    x1 = int((cx - bw / 2) * w)
                    y1 = int((cy - bh / 2) * h)
                    x2 = int((cx + bw / 2) * w)
                    y2 = int((cy + bh / 2) * h)
                    detections.append({
                        'label': f'pathology_{class_id}',
                        'confidence': round(confidence, 4),
                        'x_min': round(max(0, x1) / w, 4),
                        'y_min': round(max(0, y1) / h, 4),
                        'x_max': round(min(w, x2) / w, 4),
                        'y_max': round(min(h, y2) / h, 4),
                        'x_min_px': max(0, x1),
                        'y_min_px': max(0, y1),
                        'x_max_px': min(w, x2),
                        'y_max_px': min(h, y2),
                        'inference_time_ms': round((time.time() - start_time) * 1000, 2)
                    })
        return detections

    def _detect_mock(self, image: np.ndarray, start_time: float) -> list:
        """
        Mock detector for development/demo — generates plausible findings
        using image statistics to create reproducible results.
        """
        h, w = image.shape[:2]
        np.random.seed(int(np.mean(image)) % 1000)

        pathologies = [
            'Pulmonary Nodule', 'Ground-glass Opacity', 'Consolidation',
            'Pleural Effusion', 'Cardiomegaly', 'Pneumothorax',
            'Mass Lesion', 'Calcification', 'Atelectasis', 'Infiltrate'
        ]

        n_detections = np.random.randint(1, 5)
        detections = []
        for i in range(n_detections):
            cx = np.random.uniform(0.2, 0.8)
            cy = np.random.uniform(0.2, 0.8)
            bw = np.random.uniform(0.08, 0.25)
            bh = np.random.uniform(0.08, 0.25)
            x1 = max(0.0, cx - bw / 2)
            y1 = max(0.0, cy - bh / 2)
            x2 = min(1.0, cx + bw / 2)
            y2 = min(1.0, cy + bh / 2)
            conf = np.random.uniform(0.52, 0.95)
            label = np.random.choice(pathologies)

            detections.append({
                'label': label,
                'confidence': round(float(conf), 4),
                'x_min': round(float(x1), 4),
                'y_min': round(float(y1), 4),
                'x_max': round(float(x2), 4),
                'y_max': round(float(y2), 4),
                'x_min_px': int(x1 * w),
                'y_min_px': int(y1 * h),
                'x_max_px': int(x2 * w),
                'y_max_px': int(y2 * h),
                'inference_time_ms': round((time.time() - start_time) * 1000, 2)
            })
        return detections


class UNetSegmentor:
    """
    U-Net based medical image segmentation.
    Supports TensorFlow/Keras or PyTorch backends.
    Falls back to OpenCV-based mock segmentation in dev mode.
    """

    def __init__(self, model_path: str, threshold: float = 0.5,
                 input_size: tuple = (256, 256)):
        self.model_path = model_path
        self.threshold = threshold
        self.input_size = input_size
        self.model = None
        self.backend = None
        self._load_model()

    def _load_model(self):
        if not os.path.exists(self.model_path):
            logger.warning(f"U-Net model not found at {self.model_path}. Using mock segmentor.")
            self.backend = 'mock'
            return

        # Try TensorFlow/Keras first
        if self.model_path.endswith(('.h5', '.keras', '.pb')):
            try:
                import tensorflow as tf
                self.model = tf.keras.models.load_model(self.model_path)
                self.backend = 'tensorflow'
                logger.info("U-Net loaded via TensorFlow")
                return
            except ImportError:
                pass

        # Try PyTorch
        if self.model_path.endswith(('.pt', '.pth')):
            try:
                import torch
                self.model = torch.load(self.model_path, map_location='cpu')
                self.model.eval()
                self.backend = 'pytorch'
                logger.info("U-Net loaded via PyTorch")
                return
            except ImportError:
                pass

        logger.warning("No deep learning framework found. Using mock segmentor.")
        self.backend = 'mock'

    def segment(self, image: np.ndarray, detection_bbox: dict = None) -> list:
        """
        Run segmentation on a BGR image.
        Returns list of segmentation results with polygon points and mask paths.
        """
        if self.backend in ('tensorflow', 'pytorch'):
            return self._segment_model(image, detection_bbox)
        else:
            return self._segment_mock(image, detection_bbox)

    def _segment_model(self, image: np.ndarray, bbox: dict = None) -> list:
        h, w = image.shape[:2]

        # Preprocess
        roi = image.copy()
        if bbox:
            x1 = int(bbox['x_min'] * w)
            y1 = int(bbox['y_min'] * h)
            x2 = int(bbox['x_max'] * w)
            y2 = int(bbox['y_max'] * h)
            roi = image[y1:y2, x1:x2]

        roi_resized = cv2.resize(roi, self.input_size)
        roi_norm = roi_resized.astype(np.float32) / 255.0
        roi_input = np.expand_dims(roi_norm, axis=0)

        # Inference
        if self.backend == 'tensorflow':
            pred = self.model.predict(roi_input)[0, :, :, 0]
        else:
            import torch
            with torch.no_grad():
                tensor = torch.from_numpy(roi_input.transpose(0, 3, 1, 2))
                pred = self.model(tensor)[0, 0].numpy()

        # Post-process mask
        mask = (pred > self.threshold).astype(np.uint8) * 255
        mask_resized = cv2.resize(mask, (roi.shape[1], roi.shape[0]))
        contours, _ = cv2.findContours(mask_resized, cv2.RETR_EXTERNAL,
                                        cv2.CHAIN_APPROX_SIMPLE)

        results = []
        for contour in contours:
            if cv2.contourArea(contour) < 100:
                continue
            epsilon = 0.02 * cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, epsilon, True)
            points = approx.reshape(-1, 2).tolist()
            results.append({
                'polygon_points': points,
                'area_px': int(cv2.contourArea(contour)),
                'confidence': float(np.mean(pred[mask_resized > 0])) if mask_resized.any() else 0.0
            })
        return results

    def _segment_mock(self, image: np.ndarray, bbox: dict = None) -> list:
        """
        Mock segmentation using OpenCV image processing techniques.
        Simulates realistic organ/lesion masks for development.
        """
        h, w = image.shape[:2]
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Gaussian blur + Otsu threshold to simulate segmentation
        blurred = cv2.GaussianBlur(gray, (15, 15), 0)
        _, thresh = cv2.threshold(blurred, 0, 255,
                                   cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Morphological cleanup
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
        cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, kernel)

        # Focus on bbox region if provided
        if bbox:
            mask_roi = np.zeros_like(cleaned)
            x1, y1 = int(bbox['x_min'] * w), int(bbox['y_min'] * h)
            x2, y2 = int(bbox['x_max'] * w), int(bbox['y_max'] * h)
            mask_roi[y1:y2, x1:x2] = cleaned[y1:y2, x1:x2]
            cleaned = mask_roi

        contours, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL,
                                        cv2.CHAIN_APPROX_SIMPLE)
        results = []
        for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:3]:
            area = cv2.contourArea(contour)
            if area < 500:
                continue
            epsilon = 0.015 * cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, epsilon, True)
            points = approx.reshape(-1, 2).tolist()
            norm_points = [[round(p[0]/w, 4), round(p[1]/h, 4)] for p in points]
            results.append({
                'polygon_points': points,
                'normalized_points': norm_points,
                'area_px': int(area),
                'confidence': round(float(np.random.uniform(0.60, 0.92)), 4)
            })
        return results


class MedicalImagePreprocessor:
    """Image preprocessing pipeline for medical images"""

    @staticmethod
    def load_image(file_path: str) -> np.ndarray:
        """Load image supporting DICOM, TIFF, and standard formats"""
        ext = Path(file_path).suffix.lower()

        if ext == '.dcm':
            try:
                import pydicom
                dcm = pydicom.dcmread(file_path)
                pixel_array = dcm.pixel_array.astype(np.float32)
                # Normalize to 0-255
                pixel_array = ((pixel_array - pixel_array.min()) /
                               (pixel_array.max() - pixel_array.min()) * 255).astype(np.uint8)
                if len(pixel_array.shape) == 2:
                    pixel_array = cv2.cvtColor(pixel_array, cv2.COLOR_GRAY2BGR)
                return pixel_array
            except ImportError:
                pass

        image = cv2.imread(file_path)
        if image is None:
            raise ValueError(f"Cannot load image from {file_path}")
        return image

    @staticmethod
    def enhance_medical_image(image: np.ndarray) -> np.ndarray:
        """Apply medical image enhancement pipeline"""
        # CLAHE for contrast enhancement
        if len(image.shape) == 3:
            lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            cl = clahe.apply(l)
            enhanced = cv2.merge((cl, a, b))
            enhanced = cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)
        else:
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(image)

        # Denoise
        enhanced = cv2.fastNlMeansDenoisingColored(enhanced, None, 10, 10, 7, 21)
        return enhanced

    @staticmethod
    def generate_thumbnail(image: np.ndarray, size: tuple = (256, 256)) -> np.ndarray:
        return cv2.resize(image, size, interpolation=cv2.INTER_AREA)

    @staticmethod
    def get_image_metadata(image: np.ndarray) -> dict:
        h, w = image.shape[:2]
        channels = image.shape[2] if len(image.shape) == 3 else 1
        return {
            'width': w,
            'height': h,
            'channels': channels,
            'dtype': str(image.dtype),
            'mean_intensity': float(np.mean(image)),
            'std_intensity': float(np.std(image))
        }


class AIInferenceEngine:
    """
    Combined YOLO + U-Net inference pipeline for medical images.
    Orchestrates detection → segmentation → annotation generation.
    """

    def __init__(self, yolo_model_path: str, unet_model_path: str,
                 yolo_confidence: float = 0.45, unet_threshold: float = 0.5):
        self.detector = YOLOMedicalDetector(yolo_model_path, yolo_confidence)
        self.segmentor = UNetSegmentor(unet_model_path, unet_threshold)
        self.preprocessor = MedicalImagePreprocessor()
        logger.info("AIInferenceEngine initialized")

    def process_image(self, image_path: str) -> dict:
        """
        Full pipeline: load → preprocess → detect → segment → format results
        """
        start_time = time.time()

        # Load and preprocess
        image = self.preprocessor.load_image(image_path)
        enhanced = self.preprocessor.enhance_medical_image(image)
        metadata = self.preprocessor.get_image_metadata(image)

        # YOLO Detection
        t_detect = time.time()
        detections = self.detector.detect(enhanced)
        detect_time = round((time.time() - t_detect) * 1000, 2)

        # U-Net Segmentation per detection
        t_seg = time.time()
        segmentations = []
        for det in detections:
            segs = self.segmentor.segment(enhanced, bbox=det)
            for seg in segs:
                seg['label'] = det['label']
                seg['detection_confidence'] = det['confidence']
                segmentations.append(seg)

        # Full-image segmentation if no detections
        if not detections:
            segs = self.segmentor.segment(enhanced)
            segmentations.extend(segs)

        seg_time = round((time.time() - t_seg) * 1000, 2)

        total_time = round((time.time() - start_time) * 1000, 2)

        avg_conf = (float(np.mean([d['confidence'] for d in detections]))
                    if detections else 0.0)

        return {
            'detections': detections,
            'segmentations': segmentations,
            'metadata': metadata,
            'performance': {
                'total_ms': total_time,
                'detection_ms': detect_time,
                'segmentation_ms': seg_time
            },
            'num_detections': len(detections),
            'num_segmentations': len(segmentations),
            'avg_confidence': round(avg_conf, 4),
            'model_info': {
                'yolo_backend': self.detector.backend,
                'unet_backend': self.segmentor.backend
            }
        }

    def draw_annotations(self, image_path: str, detections: list,
                          segmentations: list = None) -> np.ndarray:
        """
        Draw bounding boxes and segmentation overlays on image.
        Returns annotated image as numpy array.
        """
        image = self.preprocessor.load_image(image_path)
        h, w = image.shape[:2]
        overlay = image.copy()

        # Color palette
        colors = {
            'Pulmonary Nodule': (0, 69, 255),
            'Mass Lesion': (0, 0, 220),
            'Ground-glass Opacity': (255, 165, 0),
            'Consolidation': (0, 128, 0),
            'Pleural Effusion': (128, 0, 128),
            'default': (50, 205, 50)
        }

        # Draw segmentation masks
        if segmentations:
            for seg in segmentations:
                color = colors.get(seg.get('label', ''), colors['default'])
                if 'polygon_points' in seg and seg['polygon_points']:
                    pts = np.array(seg['polygon_points'], dtype=np.int32)
                    if pts.ndim == 2 and pts.shape[0] > 2:
                        cv2.fillPoly(overlay, [pts], color)

        # Blend overlay
        alpha = 0.35
        image = cv2.addWeighted(overlay, alpha, image, 1 - alpha, 0)

        # Draw bounding boxes
        for det in detections:
            x1 = int(det['x_min'] * w)
            y1 = int(det['y_min'] * h)
            x2 = int(det['x_max'] * w)
            y2 = int(det['y_max'] * h)
            color = colors.get(det['label'], colors['default'])
            label = det['label']
            conf = det['confidence']

            cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)

            label_text = f"{label} {conf:.2f}"
            font_scale = max(0.4, min(0.7, w / 1000))
            (lw, lh), baseline = cv2.getTextSize(label_text,
                                                   cv2.FONT_HERSHEY_SIMPLEX,
                                                   font_scale, 2)
            cv2.rectangle(image, (x1, y1 - lh - baseline - 4),
                           (x1 + lw + 4, y1), color, -1)
            cv2.putText(image, label_text, (x1 + 2, y1 - baseline - 2),
                        cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255), 2)

        return image
