"""
MediMark AI - Dashboard / Frontend Routes
"""

from flask import Blueprint, render_template

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
@dashboard_bp.route('/dashboard')
@dashboard_bp.route('/annotate/<image_id>')
def index(image_id=None):
    return render_template('index.html')
