"""
MediMark AI — Image Routes
Handles upload, listing, serving, and stats.
Render-compatible: stores files in /tmp for free tier.
"""

from flask import Blueprint, request, jsonify, current_app, send_file, Response
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
from backend.extensions import db
from backend.models.database import MedicalImage, AuditLog
import os, uuid, cv2, numpy as np, base64
from pathlib import Path

images_bp = Blueprint('images', __name__)


def allowed_file(filename: str) -> bool:
    ext = Path(filename).suffix.lower().lstrip('.')
    return ext in current_app.config.get('ALLOWED_EXTENSIONS',
        {'png','jpg','jpeg','tiff','tif','dcm','bmp','webp'})


def get_upload_folder():
    """Use /tmp on Render (no persistent disk on free tier)."""
    folder = os.environ.get('UPLOAD_FOLDER', 'uploads/originals')
    # If relative path doesn't exist, fall back to /tmp
    if not os.path.isabs(folder):
        abs_folder = os.path.join(os.getcwd(), folder)
        if not os.path.exists(abs_folder):
            try:
                os.makedirs(abs_folder, exist_ok=True)
            except Exception:
                abs_folder = '/tmp/medimark_uploads'
                os.makedirs(abs_folder, exist_ok=True)
        return abs_folder
    os.makedirs(folder, exist_ok=True)
    return folder


def get_processed_folder():
    folder = os.environ.get('PROCESSED_FOLDER', 'uploads/processed')
    if not os.path.isabs(folder):
        abs_folder = os.path.join(os.getcwd(), folder)
        if not os.path.exists(abs_folder):
            try:
                os.makedirs(abs_folder, exist_ok=True)
            except Exception:
                abs_folder = '/tmp/medimark_processed'
                os.makedirs(abs_folder, exist_ok=True)
        return abs_folder
    os.makedirs(folder, exist_ok=True)
    return folder


def get_image_dimensions(file_path):
    try:
        img = cv2.imread(file_path)
        if img is not None:
            h, w = img.shape[:2]
            c = img.shape[2] if len(img.shape) == 3 else 1
            return w, h, c
    except Exception:
        pass
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

    upload_folder = get_upload_folder()
    upload_path   = os.path.join(upload_folder, unique_filename)
    file.save(upload_path)

    w, h, c = get_image_dimensions(upload_path)

    mime_map = {'.jpg':'image/jpeg', '.jpeg':'image/jpeg', '.png':'image/png',
                '.tiff':'image/tiff', '.tif':'image/tiff', '.dcm':'application/dicom'}
    mime_type = mime_map.get(ext, 'image/jpeg')

    # Generate thumbnail
    thumbnail_filename = None
    try:
        img = cv2.imread(upload_path)
        if img is not None:
            thumb = cv2.resize(img, (256, 256), interpolation=cv2.INTER_AREA)
            proc_folder = get_processed_folder()
            thumb_name  = f"thumb_{unique_filename.replace(ext, '.jpg')}"
            thumb_path  = os.path.join(proc_folder, thumb_name)
            cv2.imwrite(thumb_path, thumb)
            thumbnail_filename = thumb_name
    except Exception:
        pass

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
        project_id=request.form.get('project_id'),
        width=w, height=h, channels=c,
        uploaded_by=user_id,
        status='uploaded'
    )
    db.session.add(image)
    db.session.commit()
    return jsonify({'message': 'Image uploaded', 'image': image.to_dict()}), 201


@images_bp.route('/', methods=['GET'])
@jwt_required()
def list_images():
    page     = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 24, type=int)
    status_f   = request.args.get('status')
    modality_f = request.args.get('modality')
    project_f  = request.args.get('project_id')

    q = MedicalImage.query
    if status_f:   q = q.filter_by(status=status_f)
    if modality_f: q = q.filter_by(modality=modality_f)
    if project_f:  q = q.filter_by(project_id=project_f)
    q = q.order_by(MedicalImage.created_at.desc())

    pag = q.paginate(page=page, per_page=min(per_page, 100), error_out=False)
    return jsonify({
        'images':       [img.to_dict() for img in pag.items],
        'total':        pag.total,
        'pages':        pag.pages,
        'current_page': page,
        'per_page':     per_page,
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

    # Try to serve from disk
    if image.file_path and os.path.exists(image.file_path):
        return send_file(image.file_path,
                         mimetype=image.mime_type or 'image/jpeg')

    # File missing (Render free tier disk reset) — return 404 with message
    return jsonify({
        'error': 'Image file not found on disk. '
                 'On Render free tier, uploaded files are lost on restart. '
                 'Please re-upload the image.'
    }), 404


@images_bp.route('/<image_id>/thumbnail', methods=['GET'])
@jwt_required()
def serve_thumbnail(image_id):
    image = MedicalImage.query.get_or_404(image_id)
    if image.thumbnail_path:
        proc_folder = get_processed_folder()
        thumb_path  = os.path.join(proc_folder, image.thumbnail_path)
        if os.path.exists(thumb_path):
            return send_file(thumb_path, mimetype='image/jpeg')
    # Fallback to original
    return serve_image_file(image_id)


@images_bp.route('/<image_id>', methods=['DELETE'])
@jwt_required()
def delete_image(image_id):
    user_id = get_jwt_identity()
    image   = MedicalImage.query.get_or_404(image_id)
    for path in [image.file_path]:
        if path and os.path.exists(path):
            try: os.remove(path)
            except Exception: pass
    db.session.delete(image)
    db.session.commit()
    return jsonify({'message': 'Image deleted'})


@images_bp.route('/stats', methods=['GET'])
@jwt_required()
def get_stats():
    from sqlalchemy import func
    from backend.models.database import Annotation

    total       = MedicalImage.query.count()
    annotations = Annotation.query.filter_by(is_active=True).count()
    ai_done     = MedicalImage.query.filter_by(ai_processed=True).count()
    approved    = MedicalImage.query.filter_by(status='approved').count()

    mod_counts = db.session.query(
        MedicalImage.modality, func.count(MedicalImage.id)
    ).group_by(MedicalImage.modality).all()

    status_counts = db.session.query(
        MedicalImage.status, func.count(MedicalImage.id)
    ).group_by(MedicalImage.status).all()

    return jsonify({
        'total_images':      total,
        'total_annotations': annotations,
        'ai_processed':      ai_done,
        'approved':          approved,
        'by_modality':       {m: c for m, c in mod_counts},
        'by_status':         {s: c for s, c in status_counts},
    })
