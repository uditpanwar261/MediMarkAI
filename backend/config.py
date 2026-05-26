"""
MediMark AI - Configuration
Supports both local MySQL (dev) and Render PostgreSQL (production).
Render automatically injects DATABASE_URL — the app detects and uses it.
"""

import os
from datetime import timedelta


def _build_db_uri():
    """
    Priority:
    1. DATABASE_URL env var  → Render / any PaaS (PostgreSQL)
    2. SQLALCHEMY_DATABASE_URI env var → explicit override
    3. Individual MYSQL_* vars → local development
    """
    # Render injects DATABASE_URL for the linked PostgreSQL database
    database_url = os.environ.get('DATABASE_URL', '')
    if database_url:
        # Render uses postgres:// but SQLAlchemy 1.4+ needs postgresql://
        return database_url.replace('postgres://', 'postgresql+psycopg2://', 1)

    # Explicit full URI override
    explicit_uri = os.environ.get('SQLALCHEMY_DATABASE_URI', '')
    if explicit_uri:
        return explicit_uri

    # Local MySQL fallback
    host     = os.environ.get('MYSQL_HOST',     'localhost')
    port     = os.environ.get('MYSQL_PORT',     '3306')
    user     = os.environ.get('MYSQL_USER',     'medimark_user')
    password = os.environ.get('MYSQL_PASSWORD', 'medimark_pass')
    db       = os.environ.get('MYSQL_DB',       'medimark_ai')
    return f'mysql+pymysql://{user}:{password}@{host}:{port}/{db}'


class Config:
    # ── Flask ────────────────────────────────────────────────────
    SECRET_KEY = os.environ.get('SECRET_KEY', 'medimark-dev-secret-change-in-prod')
    DEBUG      = os.environ.get('DEBUG', 'False').lower() == 'true'

    # ── Database ─────────────────────────────────────────────────
    SQLALCHEMY_DATABASE_URI      = _build_db_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS    = {
        'pool_recycle':  1800,   # shorter for Render free tier
        'pool_pre_ping': True,
        'pool_size':     5,      # lower for free tier RAM limits
        'max_overflow':  10,
    }

    # ── JWT ──────────────────────────────────────────────────────
    JWT_SECRET_KEY            = os.environ.get('JWT_SECRET_KEY', 'jwt-dev-secret-change-in-prod')
    JWT_ACCESS_TOKEN_EXPIRES  = timedelta(hours=8)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)

    # ── File uploads ─────────────────────────────────────────────
    UPLOAD_FOLDER      = os.environ.get('UPLOAD_FOLDER',    'uploads/originals')
    PROCESSED_FOLDER   = os.environ.get('PROCESSED_FOLDER', 'uploads/processed')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'tiff', 'tif', 'dcm', 'bmp', 'webp'}
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50 MB

    # ── AI Models ────────────────────────────────────────────────
    YOLO_MODEL_PATH          = os.environ.get('YOLO_MODEL_PATH', 'ml_models/yolo_medical.pt')
    UNET_MODEL_PATH          = os.environ.get('UNET_MODEL_PATH', 'ml_models/unet_medical.h5')
    YOLO_CONFIDENCE_THRESHOLD = float(os.environ.get('YOLO_CONFIDENCE', '0.45'))
    UNET_THRESHOLD            = float(os.environ.get('UNET_THRESHOLD',  '0.5'))

    # ── Rate limiting ────────────────────────────────────────────
    RATELIMIT_DEFAULT     = '200 per day;50 per hour'
    RATELIMIT_STORAGE_URL = 'memory://'

    # ── Security ─────────────────────────────────────────────────
    BCRYPT_LOG_ROUNDS = 13

    # ── Pagination ───────────────────────────────────────────────
    ANNOTATIONS_PER_PAGE = 20
    IMAGES_PER_PAGE      = 24


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_recycle':  3600,
        'pool_pre_ping': True,
        'pool_size':     10,
        'max_overflow':  20,
    }


class ProductionConfig(Config):
    DEBUG             = False
    BCRYPT_LOG_ROUNDS = 15


class TestingConfig(Config):
    TESTING                  = True
    SQLALCHEMY_DATABASE_URI  = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED         = False
