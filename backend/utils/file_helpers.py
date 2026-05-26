"""
MediMark AI — File Utilities
Safe filename handling, MIME detection, path helpers
"""

import os
import uuid
import hashlib
from pathlib import Path
from typing import Optional


ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'tiff', 'tif', 'dcm', 'bmp', 'webp'}

MIME_MAP = {
    '.jpg':  'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.png':  'image/png',
    '.tiff': 'image/tiff',
    '.tif':  'image/tiff',
    '.bmp':  'image/bmp',
    '.webp': 'image/webp',
    '.dcm':  'application/dicom',
}


def allowed_file(filename: str) -> bool:
    ext = Path(filename).suffix.lower().lstrip('.')
    return ext in ALLOWED_EXTENSIONS


def get_mime_type(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    return MIME_MAP.get(ext, 'application/octet-stream')


def generate_unique_filename(original: str) -> str:
    ext = Path(original).suffix.lower()
    return f"{uuid.uuid4().hex}{ext}"


def safe_filename(filename: str) -> str:
    """Remove dangerous characters from filename."""
    name = Path(filename).stem
    ext  = Path(filename).suffix.lower()
    safe = ''.join(c for c in name if c.isalnum() or c in '-_ ')
    safe = safe.strip().replace(' ', '_') or 'unnamed'
    return f"{safe}{ext}"


def file_md5(path: str, chunk_size: int = 8192) -> Optional[str]:
    """Compute MD5 hash of a file for deduplication."""
    if not os.path.exists(path):
        return None
    h = hashlib.md5()
    with open(path, 'rb') as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


def ensure_dir(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path


def human_readable_size(size_bytes: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"
