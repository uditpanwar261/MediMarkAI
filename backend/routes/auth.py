"""
MediMark AI - Authentication Routes
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    create_access_token, create_refresh_token,
    jwt_required, get_jwt_identity
)
from werkzeug.security import generate_password_hash, check_password_hash
from backend.extensions import db
from backend.models.database import User, AuditLog
from datetime import datetime
import re

auth_bp = Blueprint('auth', __name__)


def validate_email(email: str) -> bool:
    return bool(re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email))


@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()

    required = ['email', 'password', 'full_name', 'role']
    for field in required:
        if not data.get(field):
            return jsonify({'error': f'{field} is required'}), 400

    email = data['email'].lower().strip()
    if not validate_email(email):
        return jsonify({'error': 'Invalid email format'}), 400

    if len(data['password']) < 8:
        return jsonify({'error': 'Password must be at least 8 characters'}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Email already registered'}), 409

    user = User(
        email=email,
        password_hash=generate_password_hash(data['password']),
        full_name=data['full_name'],
        role=data.get('role', 'radiologist'),
        specialty=data.get('specialty'),
        institution=data.get('institution')
    )
    db.session.add(user)
    db.session.commit()

    access_token = create_access_token(identity=user.id)
    refresh_token = create_refresh_token(identity=user.id)

    return jsonify({
        'message': 'Registration successful',
        'user': user.to_dict(),
        'access_token': access_token,
        'refresh_token': refresh_token
    }), 201


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email', '').lower().strip()
    password = data.get('password', '')

    user = User.query.filter_by(email=email, is_active=True).first()
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({'error': 'Invalid credentials'}), 401

    user.last_login = datetime.utcnow()
    db.session.commit()

    try:
        AuditLog.log(user.id, 'login',
                     ip_address=request.remote_addr,
                     user_agent=request.user_agent.string[:500])
    except Exception:
        pass

    access_token = create_access_token(identity=user.id)
    refresh_token = create_refresh_token(identity=user.id)

    return jsonify({
        'user': user.to_dict(),
        'access_token': access_token,
        'refresh_token': refresh_token
    })


@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    user_id = get_jwt_identity()
    user = User.query.get_or_404(user_id)
    return jsonify(user.to_dict())


@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    user_id = get_jwt_identity()
    access_token = create_access_token(identity=user_id)
    return jsonify({'access_token': access_token})
