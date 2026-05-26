"""
MediMark AI — Annotation Visualizer
Draws bounding boxes, segmentation overlays, and labels
onto medical images for review exports and previews.
"""

import cv2
import numpy as np
from typing import List, Optional


# ── Colour palette ────────────────────────────────────────────
LABEL_COLORS = {
    'Pulmonary Nodule':     (0,   69,  255),   # red-orange
    'Mass Lesion':          (0,   0,   220),   # red
    'Ground-glass Opacity': (0,  165,  255),   # orange
    'Consolidation':        (0,  200,   80),   # green
    'Pleural Effusion':     (200,  50, 200),   # purple
    'Cardiomegaly':         (100,  80, 255),   # pink
    'Pneumothorax':         (0,  210, 240),   # yellow-cyan
    'Calcification':        (255, 160,  50),   # blue
    'Atelectasis':          (50,  130, 255),   # coral
    'Infiltrate':           (255,  90,   0),   # sky-blue
    'Tumor':                (0,    0, 200),   # dark red
    'Normal':               (0,  230, 120),   # bright green
    'Region of Interest':   (255, 200,   0),   # cyan-gold
}
DEFAULT_COLOR = (50, 205, 50)


def _color(label: str, verified: bool = False) -> tuple:
    if verified:
        return (50, 205, 50)
    return LABEL_COLORS.get(label, DEFAULT_COLOR)


def draw_bbox(image: np.ndarray,
              label: str,
              x_min: float, y_min: float,
              x_max: float, y_max: float,
              confidence: float = 0.0,
              verified: bool = False,
              source: str = '') -> np.ndarray:
    """Draw a single normalised bounding box onto image (in-place copy)."""
    img = image.copy()
    h, w = img.shape[:2]
    x1, y1, x2, y2 = (int(x_min * w), int(y_min * h),
                       int(x_max * w), int(y_max * h))
    color = _color(label, verified)

    # Fill
    overlay = img.copy()
    cv2.rectangle(overlay, (x1, y1), (x2, y2), color, -1)
    cv2.addWeighted(overlay, 0.12, img, 0.88, 0, img)

    # Border
    thickness = 3 if verified else 2
    cv2.rectangle(img, (x1, y1), (x2, y2), color, thickness)

    # Corner brackets
    bl = max(8, int(min(x2 - x1, y2 - y1) * 0.15))
    for cx, cy, dx, dy in [(x1, y1, 1, 1), (x2, y1, -1, 1),
                            (x1, y2, 1, -1), (x2, y2, -1, -1)]:
        cv2.line(img, (cx, cy), (cx + dx * bl, cy), color, 3)
        cv2.line(img, (cx, cy), (cx, cy + dy * bl), color, 3)

    # Label pill
    conf_str = f" {int(confidence * 100)}%" if confidence else ""
    ver_str  = " ✓" if verified else ""
    text = f"{label}{conf_str}{ver_str}"
    fs   = max(0.38, min(0.62, w / 1400))
    (tw, th), bl2 = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, fs, 1)
    px, py = max(0, x1), max(th + bl2 + 4, y1)
    cv2.rectangle(img, (px, py - th - bl2 - 4), (px + tw + 8, py), color, -1)
    cv2.putText(img, text, (px + 4, py - bl2 - 1),
                cv2.FONT_HERSHEY_SIMPLEX, fs, (255, 255, 255), 1, cv2.LINE_AA)
    return img


def draw_segmentation(image: np.ndarray,
                       points: list,
                       label: str = '',
                       normalized: bool = True,
                       alpha: float = 0.3,
                       verified: bool = False) -> np.ndarray:
    """Draw a polygon segmentation mask onto image (in-place copy)."""
    if not points or len(points) < 3:
        return image
    img = image.copy()
    h, w = img.shape[:2]

    if normalized:
        pts = np.array([[int(p[0] * w), int(p[1] * h)] for p in points],
                       dtype=np.int32)
    else:
        pts = np.array([[int(p[0]), int(p[1])] for p in points], dtype=np.int32)

    color = _color(label, verified)
    overlay = img.copy()
    cv2.fillPoly(overlay, [pts], color)
    cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0, img)
    cv2.polylines(img, [pts], True, color, 2, cv2.LINE_AA)
    return img


def annotate_image(image: np.ndarray,
                   annotations: list,
                   draw_seg: bool = True,
                   draw_boxes: bool = True) -> np.ndarray:
    """
    Draw all annotations onto an image.
    `annotations` is a list of Annotation.to_dict() records.
    """
    import json
    img = image.copy()

    # Segmentation first (behind bboxes)
    if draw_seg:
        for ann in annotations:
            if ann.get('annotation_type') != 'segmentation':
                continue
            seg = ann.get('segmentation_data')
            if isinstance(seg, str):
                try:
                    seg = json.loads(seg)
                except Exception:
                    continue
            pts = (seg or {}).get('normalized_points') or \
                  (seg or {}).get('polygon_points')
            if pts:
                norm = 'normalized_points' in (seg or {})
                img  = draw_segmentation(
                    img, pts, ann.get('label_name', ''),
                    normalized=norm,
                    verified=ann.get('is_verified', False))

    # Bounding boxes
    if draw_boxes:
        for ann in annotations:
            if ann.get('annotation_type') != 'bounding_box':
                continue
            bbox = ann.get('bbox')
            if not bbox:
                continue
            img = draw_bbox(
                img,
                ann.get('label_name', 'Unknown'),
                bbox['x_min'], bbox['y_min'],
                bbox['x_max'], bbox['y_max'],
                ann.get('confidence', 0.0),
                ann.get('is_verified', False),
                ann.get('source', ''))

    return img


def save_annotated(image: np.ndarray,
                   annotations: list,
                   out_path: str,
                   jpeg_quality: int = 90) -> str:
    """Render and save an annotated image; return the output path."""
    rendered = annotate_image(image, annotations)
    cv2.imwrite(out_path, rendered, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])
    return out_path
