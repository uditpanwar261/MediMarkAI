"""
MediMark AI — Response Helpers
Standardized JSON responses and pagination utilities.
"""

from flask import jsonify
from math import ceil


def success(data=None, message: str = 'OK', status: int = 200):
    payload = {'status': 'success', 'message': message}
    if data is not None:
        payload['data'] = data
    return jsonify(payload), status


def error(message: str, status: int = 400, details=None):
    payload = {'status': 'error', 'error': message}
    if details:
        payload['details'] = details
    return jsonify(payload), status


def paginated(items: list, total: int, page: int,
              per_page: int, key: str = 'items'):
    return jsonify({
        'status': 'success',
        key: items,
        'pagination': {
            'total': total,
            'page': page,
            'per_page': per_page,
            'pages': ceil(total / per_page) if per_page else 1,
            'has_next': (page * per_page) < total,
            'has_prev': page > 1,
        }
    })
