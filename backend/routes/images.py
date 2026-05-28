"""
MediMark AI — Image Routes
Cloudinary-first storage with local disk fallback.
Solves Render free tier ephemeral filesystem issue.
"""

from flask import Blueprint, request, jsonify, current_app, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
from backend.extensions import db
from backend.models.database import MedicalImage
from backend.utils.cloudinary_helper import (
    upload_image as cloud_upload,
    upload_thumbnail as cloud_upload_thumb,
    delete_image as cloud_delete,
    CLOUDINARY_CONFIGURED
)
import os, uuid, cv2
from pathlib import Path

images_bp = Blueprint('images', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'tiff', 'tif', 'dcm', 'bmp', 'webp'}

def allowed_file(filename):
    return Path(filename).suffix.lower().lstrip('.') in ALLOWED_EXTENSIONS

def get_tmp_folder(sub='originals'):
    """Always use /tmp on Render — just for processing, then upload to Cloudinary."""
    folder = f'/tmp/medimark_{sub}'
    os.makedirs(folder, exist_ok=True)
    return folder

def get_dims(path):
    try:
        img = cv2.imread(path)
        if img is not None:
            h, w = img.shape[:2]
            return w, h, img.shape[2] if len(img.shape) == 3 else 1
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
    unique_id = uuid.uuid4().hex
    unique_filename = f"{unique_id}{ext}"

    # Save to /tmp for processing
    tmp_folder = get_tmp_folder('originals')
    tmp_path   = os.path.join(tmp_folder, unique_filename)
    file.save(tmp_path)

    w, h, c = get_dims(tmp_path)

    mime_map = {'.jpg':'image/jpeg','.jpeg':'image/jpeg','.png':'image/png',
                '.tiff':'image/tiff','.tif':'image/tiff','.dcm':'application/dicom'}
    mime_type = mime_map.get(ext, 'image/jpeg')

    # ── Upload to Cloudinary if configured ──────────────────
    cloudinary_url      = None
    cloudinary_thumb    = None
    cloudinary_public_id = None

    if CLOUDINARY_CONFIGURED:
        result = cloud_upload(tmp_path, public_id=unique_id, folder='medimark/originals')
        cloudinary_url       = result.get('url')
        cloudinary_public_id = result.get('public_id')

        # Generate thumbnail and upload
        try:
            img   = cv2.imread(tmp_path)
            thumb = cv2.resize(img, (256, 256), interpolation=cv2.INTER_AREA)
            thumb_tmp = os.path.join(get_tmp_folder('thumbs'), f"thumb_{unique_filename.replace(ext,'.jpg')}")
            cv2.imwrite(thumb_tmp, thumb)
            cloudinary_thumb = cloud_upload_thumb(thumb_tmp, public_id=f"thumb_{unique_id}")
        except Exception:
            pass

    # ── Determine file_path to store ────────────────────────
    # If Cloudinary worked, store the CDN URL; else store local tmp path
    stored_path = cloudinary_url if cloudinary_url else tmp_path
    thumb_path  = cloudinary_thumb if cloudinary_thumb else None

    image = MedicalImage(
        filename          = unique_filename,
        original_filename = original_filename,
        file_path         = stored_path,          # Cloudinary URL or tmp path
        thumbnail_path    = thumb_path,            # Cloudinary URL or None
        file_size         = os.path.getsize(tmp_path),
        mime_type         = mime_type,
        modality          = request.form.get('modality', 'Other'),
        body_part         = request.form.get('body_part'),
        patient_id        = request.form.get('patient_id'),
        project_id        = request.form.get('project_id'),
        width=w, height=h, channels=c,
        uploaded_by       = user_id,
        status            = 'uploaded'
    )
    db.session.add(image)
    db.session.commit()

    return jsonify({'message': 'Image uploaded', 'image': image.to_dict()}), 201


@images_bp.route('/', methods=['GET'])
@jwt_required()
def list_images():
    page       = request.args.get('page', 1, type=int)
    per_page   = request.args.get('per_page', 24, type=int)
    status_f   = request.args.get('status')
    modality_f = request.args.get('modality')
    project_f  = request.args.get('project_id')

    q = MedicalImage.query
    if status_f:   q = q.filter_by(status=status_f)
    if modality_f: q = q.filter_by(modality=modality_f)
    if project_f:  q = q.filter_by(project_id=project_f)
    pag = q.order_by(MedicalImage.created_at.desc()).paginate(
        page=page, per_page=min(per_page, 100), error_out=False)

    return jsonify({
        'images': [i.to_dict() for i in pag.items],
        'total': pag.total, 'pages': pag.pages,
        'current_page': page, 'per_page': per_page
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

    path = image.file_path
    if not path:
        return jsonify({'error': 'No file path stored'}), 404

    # If it's a Cloudinary URL, redirect browser to it
    if path.startswith('http://') or path.startswith('https://'):
        from flask import redirect
        return redirect(path)

    # Local file
    if os.path.exists(path):
        return send_file(path, mimetype=image.mime_type or 'image/jpeg')

    return jsonify({'error': 'File not found. Please re-upload.'}), 404


@images_bp.route('/<image_id>/thumbnail', methods=['GET'])
@jwt_required()
def serve_thumbnail(image_id):
    image = MedicalImage.query.get_or_404(image_id)
    thumb = image.thumbnail_path

    if thumb:
        if thumb.startswith('http://') or thumb.startswith('https://'):
            from flask import redirect
            return redirect(thumb)
        if os.path.exists(thumb):
            return send_file(thumb, mimetype='image/jpeg')

    # Fallback to full image
    return serve_image_file(image_id)


@images_bp.route('/<image_id>', methods=['DELETE'])
@jwt_required()
def delete_image(image_id):
    image = MedicalImage.query.get_or_404(image_id)
    # Delete from local disk if applicable
    if image.file_path and not image.file_path.startswith('http'):
        try: os.remove(image.file_path)
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
