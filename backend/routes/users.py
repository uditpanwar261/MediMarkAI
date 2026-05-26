"""
MediMark AI — Users / Admin Routes
User management for admin role.
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from backend.extensions import db
from backend.models.database import User, AuditLog
from backend.utils.security import require_role
from datetime import datetime

users_bp = Blueprint('users', __name__)


@users_bp.route('/', methods=['GET'])
@jwt_required()
@require_role('admin')
def list_users():
    users = User.query.order_by(User.created_at.desc()).all()
    return jsonify({'users': [u.to_dict() for u in users]})


@users_bp.route('/<user_id>', methods=['GET'])
@jwt_required()
def get_user(user_id):
    current = get_jwt_identity()
    user = User.query.get_or_404(user_id)
    # Allow own profile or admin
    requester = User.query.get(current)
    if current != user_id and (not requester or requester.role != 'admin'):
        return jsonify({'error': 'Forbidden'}), 403
    return jsonify(user.to_dict())


@users_bp.route('/<user_id>', methods=['PUT'])
@jwt_required()
def update_user(user_id):
    current = get_jwt_identity()
    user = User.query.get_or_404(user_id)
    requester = User.query.get(current)

    if current != user_id and (not requester or requester.role != 'admin'):
        return jsonify({'error': 'Forbidden'}), 403

    data = request.get_json()
    allowed = ['full_name', 'specialty', 'institution']
    if requester and requester.role == 'admin':
        allowed += ['role', 'is_active', 'is_verified']

    for field in allowed:
        if field in data:
            setattr(user, field, data[field])

    db.session.commit()
    return jsonify({'user': user.to_dict()})


@users_bp.route('/<user_id>/deactivate', methods=['POST'])
@jwt_required()
@require_role('admin')
def deactivate_user(user_id):
    admin_id = get_jwt_identity()
    user = User.query.get_or_404(user_id)
    if user.id == admin_id:
        return jsonify({'error': 'Cannot deactivate yourself'}), 400
    user.is_active = False
    db.session.commit()
    try:
        AuditLog.log(admin_id, 'user_deactivate', 'user', user_id,
                     f"Deactivated user {user.email}", request.remote_addr)
    except Exception:
        pass
    return jsonify({'message': f'User {user.email} deactivated'})


@users_bp.route('/audit-log', methods=['GET'])
@jwt_required()
@require_role('admin')
def get_audit_log():
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 50, type=int), 200)
    user_filter = request.args.get('user_id')
    action_filter = request.args.get('action')

    query = AuditLog.query
    if user_filter:
        query = query.filter_by(user_id=user_filter)
    if action_filter:
        query = query.filter_by(action=action_filter)

    paginated = query.order_by(AuditLog.timestamp.desc()).paginate(
        page=page, per_page=per_page, error_out=False)

    entries = [{
        'id': e.id,
        'user_id': e.user_id,
        'action': e.action,
        'resource_type': e.resource_type,
        'resource_id': e.resource_id,
        'details': e.details,
        'ip_address': e.ip_address,
        'timestamp': e.timestamp.isoformat()
    } for e in paginated.items]

    return jsonify({'logs': entries, 'total': paginated.total, 'page': page})
