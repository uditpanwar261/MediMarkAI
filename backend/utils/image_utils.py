"""
MediMark AI — Image Processing Utilities
OpenCV-based helpers used across routes and the ML pipeline.
"""

import cv2
import numpy as np
from typing import Optional, Tuple


def load_image_safe(path: str) -> Optional[np.ndarray]:
    """Load an image; return None if it cannot be read."""
    img = cv2.imread(path)
    return img if img is not None else None


def resize_keep_aspect(image: np.ndarray,
                        max_dim: int = 1024) -> np.ndarray:
    h, w = image.shape[:2]
    if max(h, w) <= max_dim:
        return image
    scale = max_dim / max(h, w)
    new_w, new_h = int(w * scale), int(h * scale)
    return cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)


def make_thumbnail(image: np.ndarray,
                   size: Tuple[int, int] = (256, 256)) -> np.ndarray:
    return cv2.resize(image, size, interpolation=cv2.INTER_AREA)


def apply_clahe(image: np.ndarray,
                clip_limit: float = 3.0,
                tile_grid: Tuple[int, int] = (8, 8)) -> np.ndarray:
    """Contrast Limited Adaptive Histogram Equalization."""
    if len(image.shape) == 3:
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid)
        cl = clahe.apply(l)
        enhanced = cv2.merge((cl, a, b))
        return cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid)
    return clahe.apply(image)


def normalize_bbox(x1: int, y1: int, x2: int, y2: int,
                   img_w: int, img_h: int) -> dict:
    """Convert pixel coords to normalized 0-1 bbox dict."""
    return {
        'x_min': round(max(0.0, x1 / img_w), 6),
        'y_min': round(max(0.0, y1 / img_h), 6),
        'x_max': round(min(1.0, x2 / img_w), 6),
        'y_max': round(min(1.0, y2 / img_h), 6),
    }


def bbox_to_pixels(bbox: dict, img_w: int, img_h: int) -> Tuple[int, int, int, int]:
    """Convert normalized bbox to pixel coordinates."""
    x1 = int(bbox['x_min'] * img_w)
    y1 = int(bbox['y_min'] * img_h)
    x2 = int(bbox['x_max'] * img_w)
    y2 = int(bbox['y_max'] * img_h)
    return x1, y1, x2, y2


def compute_iou(box_a: dict, box_b: dict) -> float:
    """Intersection-over-Union for two normalized bboxes."""
    ix1 = max(box_a['x_min'], box_b['x_min'])
    iy1 = max(box_a['y_min'], box_b['y_min'])
    ix2 = min(box_a['x_max'], box_b['x_max'])
    iy2 = min(box_a['y_max'], box_b['y_max'])
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    area_a = (box_a['x_max'] - box_a['x_min']) * (box_a['y_max'] - box_a['y_min'])
    area_b = (box_b['x_max'] - box_b['x_min']) * (box_b['y_max'] - box_b['y_min'])
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def contours_to_polygon(contour: np.ndarray,
                         img_w: int, img_h: int,
                         epsilon_factor: float = 0.015) -> list:
    """Simplify a contour and return normalized polygon points."""
    epsilon = epsilon_factor * cv2.arcLength(contour, True)
    approx = cv2.approxPolyDP(contour, epsilon, True)
    pts = approx.reshape(-1, 2)
    return [[round(float(p[0]) / img_w, 4), round(float(p[1]) / img_h, 4)]
            for p in pts]


def encode_mask_rle(mask: np.ndarray) -> dict:
    """Run-Length Encode a binary mask (uint8, values 0/1)."""
    flat = mask.flatten(order='F')
    runs, counts = [], []
    run_val = flat[0]
    count = 1
    for v in flat[1:]:
        if v == run_val:
            count += 1
        else:
            runs.append(int(run_val))
            counts.append(count)
            run_val = v
            count = 1
    runs.append(int(run_val))
    counts.append(count)
    return {'runs': runs, 'counts': counts,
            'shape': list(mask.shape), 'encoding': 'rle_f'}


def decode_mask_rle(rle: dict) -> np.ndarray:
    """Decode an RLE mask back to a 2D numpy array."""
    h, w = rle['shape']
    flat = np.zeros(h * w, dtype=np.uint8)
    idx = 0
    for val, cnt in zip(rle['runs'], rle['counts']):
        flat[idx:idx + cnt] = val
        idx += cnt
    return flat.reshape((h, w), order='F')
