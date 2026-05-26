"""
MediMark AI - Configuration
"""

import os
from datetime import timedelta

class Config:
    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY', 'medimark-ai-secret-key-change-in-production')
    DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'

    # MySQL Database
    MYSQL_HOST = os.environ.get('MYSQL_HOST', 'localhost')
    MYSQL_PORT = int(os.environ.get('MYSQL_PORT', 3306))
    MYSQL_USER = os.environ.get('MYSQL_USER', 'medimark_user')
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', 'medimark_pass')
    MYSQL_DB = os.environ.get('MYSQL_DB', 'medimark_ai')
    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}"
        f"@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_recycle': 3600,
        'pool_pre_ping': True,
        'pool_size': 10,
        'max_overflow': 20
    }

    # JWT
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'jwt-secret-medimark')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=8)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)

    # File Uploads
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'uploads/originals')
    PROCESSED_FOLDER = os.environ.get('PROCESSED_FOLDER', 'uploads/processed')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'tiff', 'tif', 'dcm', 'bmp'}
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB

    # AI Model Paths
    YOLO_MODEL_PATH = os.environ.get('YOLO_MODEL_PATH', 'ml_models/yolo_medical.pt')
    UNET_MODEL_PATH = os.environ.get('UNET_MODEL_PATH', 'ml_models/unet_medical.h5')
    YOLO_CONFIDENCE_THRESHOLD = float(os.environ.get('YOLO_CONFIDENCE', '0.45'))
    UNET_THRESHOLD = float(os.environ.get('UNET_THRESHOLD', '0.5'))

    # Rate Limiting
    RATELIMIT_DEFAULT = "200 per day;50 per hour"
    RATELIMIT_STORAGE_URL = "memory://"

    # Security
    BCRYPT_LOG_ROUNDS = 13
    WTF_CSRF_ENABLED = True

    # Pagination
    ANNOTATIONS_PER_PAGE = 20
    IMAGES_PER_PAGE = 24


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_ECHO = False


class ProductionConfig(Config):
    DEBUG = False
    BCRYPT_LOG_ROUNDS = 15


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
