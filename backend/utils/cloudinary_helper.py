"""
MediMark AI — Cloudinary Storage Helper
Uploads images to Cloudinary (free tier: 25GB storage, 25GB bandwidth/month).
Falls back to local disk if Cloudinary is not configured.
"""

import os
import logging
import base64
import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Check if Cloudinary is configured
CLOUDINARY_CONFIGURED = bool(os.environ.get('CLOUDINARY_CLOUD_NAME'))


def _get_cloudinary():
    """Lazy import cloudinary only when configured."""
    import cloudinary
    import cloudinary.uploader
    cloudinary.config(
        cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME'),
        api_key    = os.environ.get('CLOUDINARY_API_KEY'),
        api_secret = os.environ.get('CLOUDINARY_API_SECRET'),
        secure     = True
    )
    return cloudinary


def upload_image(file_path: str, public_id: str = None, folder: str = 'medimark') -> dict:
    """
    Upload image to Cloudinary.
    Returns dict with: url, public_id, width, height
    Falls back gracefully if Cloudinary not configured.
    """
    if not CLOUDINARY_CONFIGURED:
        return {'url': None, 'public_id': None, 'cloudinary': False}

    try:
        cloudinary = _get_cloudinary()
        result = cloudinary.uploader.upload(
            file_path,
            public_id     = public_id,
            folder        = folder,
            resource_type = 'image',
            overwrite     = True,
            # Allow cross-origin access from any domain (needed for Canvas)
            access_mode   = 'public',
            transformation = [{'quality': 'auto', 'fetch_format': 'auto'}]
        )
        return {
            'url':        result.get('secure_url'),
            'public_id':  result.get('public_id'),
            'width':      result.get('width'),
            'height':     result.get('height'),
            'cloudinary': True
        }
    except Exception as e:
        logger.error(f"Cloudinary upload failed: {e}")
        return {'url': None, 'public_id': None, 'cloudinary': False}


def upload_thumbnail(file_path: str, public_id: str, folder: str = 'medimark/thumbs') -> str:
    """Upload thumbnail to Cloudinary, return URL or None."""
    if not CLOUDINARY_CONFIGURED:
        return None
    try:
        cloudinary = _get_cloudinary()
        result = cloudinary.uploader.upload(
            file_path,
            public_id  = public_id,
            folder     = folder,
            resource_type = 'image',
            overwrite  = True,
            transformation = [
                {'width': 256, 'height': 256, 'crop': 'fill', 'quality': 'auto'}
            ]
        )
        return result.get('secure_url')
    except Exception as e:
        logger.error(f"Cloudinary thumbnail upload failed: {e}")
        return None


def delete_image(public_id: str) -> bool:
    """Delete image from Cloudinary by public_id."""
    if not CLOUDINARY_CONFIGURED or not public_id:
        return False
    try:
        cloudinary = _get_cloudinary()
        cloudinary.uploader.destroy(public_id)
        return True
    except Exception as e:
        logger.error(f"Cloudinary delete failed: {e}")
        return False


def get_cloudinary_url(public_id: str, width: int = None, height: int = None) -> str:
    """Generate a Cloudinary URL with optional transformations."""
    if not CLOUDINARY_CONFIGURED or not public_id:
        return None
    try:
        import cloudinary.utils
        transformation = []
        if width and height:
            transformation = [{'width': width, 'height': height, 'crop': 'fill'}]
        url, _ = cloudinary.utils.cloudinary_url(
            public_id, transformation=transformation, secure=True
        )
        return url
    except Exception:
        return None
