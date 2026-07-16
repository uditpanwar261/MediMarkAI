"""
MediMark AI — AWS S3 Storage Helper
Uploads medical images to a private S3 bucket and serves them via short-lived
presigned URLs (images are never made public, since this is medical data).
Falls back to local disk if S3 is not configured.
"""

import os
import logging
import cv2
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

logger = logging.getLogger(__name__)

AWS_S3_BUCKET = os.environ.get('AWS_S3_BUCKET')
AWS_REGION = os.environ.get('AWS_REGION', 'ap-south-1')
PRESIGNED_URL_EXPIRY = int(os.environ.get('S3_PRESIGNED_URL_EXPIRY', '3600'))  # seconds

# S3 is considered configured once a bucket name is set. Credentials can come
# from explicit env vars (AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY) or from
# boto3's default credential chain (IAM role, ~/.aws/credentials, etc).
S3_CONFIGURED = bool(AWS_S3_BUCKET)

_s3_client = None


def _get_client():
    """Lazy-create a single boto3 S3 client for the process."""
    global _s3_client
    if _s3_client is None:
        kwargs = {'region_name': AWS_REGION}
        access_key = os.environ.get('AWS_ACCESS_KEY_ID')
        secret_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
        if access_key and secret_key:
            kwargs['aws_access_key_id'] = access_key
            kwargs['aws_secret_access_key'] = secret_key
        _s3_client = boto3.client('s3', **kwargs)
    return _s3_client


_CONTENT_TYPES = {
    '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
    '.tiff': 'image/tiff', '.tif': 'image/tiff', '.dcm': 'application/dicom',
    '.bmp': 'image/bmp', '.webp': 'image/webp',
}


def upload_image(file_path: str, public_id: str = None, folder: str = 'medimark/originals') -> dict:
    """
    Upload an image to S3 (private object — no ACL).
    Returns dict with: key, width, height, s3 (bool). Falls back gracefully
    if S3 is not configured or the upload fails.
    """
    if not S3_CONFIGURED:
        return {'key': None, 's3': False}

    try:
        ext = os.path.splitext(file_path)[1].lower() or '.jpg'
        base_name = public_id or os.path.splitext(os.path.basename(file_path))[0]
        key = f"{folder}/{base_name}{ext}"
        content_type = _CONTENT_TYPES.get(ext, 'application/octet-stream')

        client = _get_client()
        client.upload_file(
            file_path, AWS_S3_BUCKET, key,
            ExtraArgs={'ContentType': content_type}
        )

        img = cv2.imread(file_path)
        height, width = (img.shape[0], img.shape[1]) if img is not None else (None, None)

        return {'key': key, 'width': width, 'height': height, 's3': True}
    except (ClientError, NoCredentialsError) as e:
        logger.error(f"S3 upload failed: {e}")
        return {'key': None, 's3': False}


def upload_thumbnail(file_path: str, public_id: str, folder: str = 'medimark/thumbs') -> str:
    """Upload a thumbnail to S3. Returns the S3 object key, or None."""
    if not S3_CONFIGURED:
        return None
    try:
        key = f"{folder}/{public_id}.jpg"
        client = _get_client()
        client.upload_file(
            file_path, AWS_S3_BUCKET, key,
            ExtraArgs={'ContentType': 'image/jpeg'}
        )
        return key
    except (ClientError, NoCredentialsError) as e:
        logger.error(f"S3 thumbnail upload failed: {e}")
        return None


def delete_image(key: str) -> bool:
    """Delete an object from S3 by key."""
    if not S3_CONFIGURED or not key:
        return False
    try:
        client = _get_client()
        client.delete_object(Bucket=AWS_S3_BUCKET, Key=key)
        return True
    except ClientError as e:
        logger.error(f"S3 delete failed: {e}")
        return False


def get_presigned_url(key: str, expires_in: int = None) -> str:
    """
    Generate a short-lived presigned GET URL for a private S3 object.
    Called on every serve request rather than storing a permanent public URL.
    """
    if not S3_CONFIGURED or not key:
        return None
    try:
        client = _get_client()
        return client.generate_presigned_url(
            'get_object',
            Params={'Bucket': AWS_S3_BUCKET, 'Key': key},
            ExpiresIn=expires_in or PRESIGNED_URL_EXPIRY
        )
    except ClientError as e:
        logger.error(f"S3 presigned URL generation failed: {e}")
        return None
