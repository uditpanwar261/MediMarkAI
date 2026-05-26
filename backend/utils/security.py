"""
MediMark AI — Security Utilities
Password hashing, token helpers, input sanitization
"""

import re
import bleach
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from flask import request, jsonify
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
from backend.models.database import User


def hash_password(password: str) -> str:
    return generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)


def verify_password(password: str, password_hash: str) -> bool:
    return check_password_hash(password_hash, password)


def sanitize_string(value: str, max_length: int = 500) -> str:
    """Strip HTML and limit length."""
    if not value:
        return value
    cleaned = bleach.clean(str(value), tags=[], strip=True)
    return cleaned[:max_length]


def validate_email(email: str) -> bool:
    pattern = r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_uuid(value: str) -> bool:
    pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    return bool(re.match(pattern, str(value).lower()))


def require_role(*roles):
    """Decorator to restrict endpoint to specific user roles."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            user_id = get_jwt_identity()
            user = User.query.get(user_id)
            if not user or user.role not in roles:
                return jsonify({'error': 'Insufficient permissions'}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def get_client_ip() -> str:
    """Get real client IP behind proxies."""
    if request.headers.get('X-Forwarded-For'):
        return request.headers['X-Forwarded-For'].split(',')[0].strip()
    return request.remote_addr or 'unknown'
