"""
MediMark AI - Medical Image Routes
"""

from flask import Blueprint, request, jsonify, current_app, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
from backend.extensions import db
from backend.models.database import MedicalImage, AuditLog
import os
import uuid
import cv2
import numpy as np
from pathlib import Path

images_bp = Blueprint('images', __name__)


def allowed_file(filename: str) -> bool:
    ext = Path(filename).suffix.lower().lstrip('.')
    return ext in current_app.config['ALLOWED_EXTENSIONS']


def get_image_dimensions(file_path: str):
    img = cv2.imread(file_path)
    if img is not None:
        h, w = img.shape[:2]
        c = img.shape[2] if len(img.shape) == 3 else 1
        return w, h, c
    return None, None, None


@images_bp.route('/upload', methods=['POST'])
@jwt_required()
def upload_image():
    user_id = get_jwt_identity()

    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if not file.filename or not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type'}), 400

    original_filename = secure_filename(file.filename)
    ext = Path(original_filename).suffix.lower()
    unique_filename = f"{uuid.uuid4().hex}{ext}"

    upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
    os.makedirs(os.path.dirname(upload_path), exist_ok=True)
    file.save(upload_path)

    # Get image dimensions
    w, h, c = get_image_dimensions(upload_path)

    # Determine MIME type
    mime_map = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
                '.png': 'image/png', '.tiff': 'image/tiff',
                '.tif': 'image/tiff', '.dcm': 'application/dicom'}
    mime_type = mime_map.get(ext, 'image/jpeg')

    # Generate thumbnail
    thumbnail_filename = None
    try:
        img = cv2.imread(upload_path)
        if img is not None:
            thumb = cv2.resize(img, (256, 256), interpolation=cv2.INTER_AREA)
            thumb_filename = f"thumb_{unique_filename.replace(ext, '.jpg')}"
            thumb_path = os.path.join(current_app.config['PROCESSED_FOLDER'], thumb_filename)
            os.makedirs(os.path.dirname(thumb_path), exist_ok=True)
            cv2.imwrite(thumb_path, thumb)
            thumbnail_filename = thumb_filename
    except Exception:
        pass

    # Create DB record
    image = MedicalImage(
        filename=unique_filename,
        original_filename=original_filename,
        file_path=upload_path,
        thumbnail_path=thumbnail_filename,
        file_size=os.path.getsize(upload_path),
        mime_type=mime_type,
        modality=request.form.get('modality', 'Other'),
        body_part=request.form.get('body_part'),
        patient_id=request.form.get('patient_id'),
        study_description=request.form.get('study_description'),
        project_id=request.form.get('project_id'),
        width=w,
        height=h,
        channels=c,
        uploaded_by=user_id,
        status='uploaded'
    )
    db.session.add(image)
    db.session.commit()

    try:
        AuditLog.log(user_id, 'image_upload', 'medical_image', image.id,
                     f"Uploaded {original_filename}", request.remote_addr)
    except Exception:
        pass

    return jsonify({
        'message': 'Image uploaded successfully',
        'image': image.to_dict()
    }), 201


@images_bp.route('/', methods=['GET'])
@jwt_required()
def list_images():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 24, type=int)
    status_filter = request.args.get('status')
    modality_filter = request.args.get('modality')
    project_id = request.args.get('project_id')

    query = MedicalImage.query

    if status_filter:
        query = query.filter_by(status=status_filter)
    if modality_filter:
        query = query.filter_by(modality=modality_filter)
    if project_id:
        query = query.filter_by(project_id=project_id)

    query = query.order_by(MedicalImage.created_at.desc())
    paginated = query.paginate(page=page, per_page=min(per_page, 100), error_out=False)

    return jsonify({
        'images': [img.to_dict() for img in paginated.items],
        'total': paginated.total,
        'pages': paginated.pages,
        'current_page': page,
        'per_page': per_page
    })


@images_bp.route('/<image_id>', methods=['GET'])
@jwt_required()
def get_image(image_id):
    image = MedicalImage.query.get_or_404(image_id)
    return jsonify(image.to_dict(include_annotations=True))


@images_bp.route('/<image_id>/file', methods=['GET'])
@jwt_required()
def serve_image_file(image_id):
    image = MedicalImage.query.get_or_404(image_id)
    if not os.path.exists(image.file_path):
        return jsonify({'error': 'File not found on disk'}), 404
    return send_file(image.file_path, mimetype=image.mime_type or 'image/jpeg')


@images_bp.route('/<image_id>/thumbnail', methods=['GET'])
@jwt_required()
def serve_thumbnail(image_id):
    image = MedicalImage.query.get_or_404(image_id)
    if image.thumbnail_path:
        thumb_path = os.path.join(current_app.config['PROCESSED_FOLDER'],
                                   image.thumbnail_path)
        if os.path.exists(thumb_path):
            return send_file(thumb_path, mimetype='image/jpeg')
    # Fallback to original
    return serve_image_file(image_id)


@images_bp.route('/<image_id>', methods=['DELETE'])
@jwt_required()
def delete_image(image_id):
    user_id = get_jwt_identity()
    image = MedicalImage.query.get_or_404(image_id)

    # Delete files
    for path in [image.file_path, image.processed_path]:
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass

    db.session.delete(image)
    db.session.commit()

    try:
        AuditLog.log(user_id, 'image_delete', 'medical_image', image_id,
                     f"Deleted {image.original_filename}", request.remote_addr)
    except Exception:
        pass

    return jsonify({'message': 'Image deleted successfully'})


@images_bp.route('/stats', methods=['GET'])
@jwt_required()
def get_stats():
    from sqlalchemy import func
    from backend.models.database import Annotation

    total_images = MedicalImage.query.count()
    total_annotations = Annotation.query.filter_by(is_active=True).count()
    ai_processed = MedicalImage.query.filter_by(ai_processed=True).count()
    approved = MedicalImage.query.filter_by(status='approved').count()

    modality_counts = db.session.query(
        MedicalImage.modality, func.count(MedicalImage.id)
    ).group_by(MedicalImage.modality).all()

    status_counts = db.session.query(
        MedicalImage.status, func.count(MedicalImage.id)
    ).group_by(MedicalImage.status).all()

    return jsonify({
        'total_images': total_images,
        'total_annotations': total_annotations,
        'ai_processed': ai_processed,
        'approved': approved,
        'by_modality': {m: c for m, c in modality_counts},
        'by_status': {s: c for s, c in status_counts}
    })
