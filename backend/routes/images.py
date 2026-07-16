"""
MediMark AI — Image Routes
AWS S3-first storage (private bucket, presigned URLs) with local disk fallback.
Solves Render free tier ephemeral filesystem issue.
"""

from flask import Blueprint, request, jsonify, current_app, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
from backend.extensions import db
from backend.models.database import MedicalImage
from backend.utils.s3_helper import (
    upload_image as s3_upload,
    upload_thumbnail as s3_upload_thumb,
    delete_image as s3_delete,
    get_presigned_url,
    S3_CONFIGURED
)
import os, uuid, cv2
from pathlib import Path

images_bp = Blueprint('images', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'tiff', 'tif', 'dcm', 'bmp', 'webp'}

def allowed_file(filename):
    return Path(filename).suffix.lower().lstrip('.') in ALLOWED_EXTENSIONS

def get_tmp_folder(sub='originals'):
    """Always use /tmp on Render — just for processing, then upload to S3."""
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

    # ── Upload to S3 if configured ───────────────────────────
    s3_key       = None
    s3_thumb_key = None

    if S3_CONFIGURED:
        result = s3_upload(tmp_path, public_id=unique_id, folder='medimark/originals')
        s3_key = result.get('key')

        # Generate thumbnail and upload
        try:
            img   = cv2.imread(tmp_path)
            thumb = cv2.resize(img, (256, 256), interpolation=cv2.INTER_AREA)
            thumb_tmp = os.path.join(get_tmp_folder('thumbs'), f"thumb_{unique_filename.replace(ext,'.jpg')}")
            cv2.imwrite(thumb_tmp, thumb)
            s3_thumb_key = s3_upload_thumb(thumb_tmp, public_id=f"thumb_{unique_id}")
        except Exception:
            pass

    # ── Determine file_path to store ────────────────────────
    # If S3 worked, store an "s3://<key>" marker (bucket is private — a fresh
    # presigned URL is generated on every serve request); else local tmp path
    stored_path = f"s3://{s3_key}" if s3_key else tmp_path
    thumb_path  = f"s3://{s3_thumb_key}" if s3_thumb_key else None

    image = MedicalImage(
        filename          = unique_filename,
        original_filename = original_filename,
        file_path         = stored_path,          # s3://<key> or local tmp path
        thumbnail_path    = thumb_path,            # s3://<key> or None
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
    user_id    = get_jwt_identity()
    page       = request.args.get('page', 1, type=int)
    per_page   = request.args.get('per_page', 24, type=int)
    status_f   = request.args.get('status')
    modality_f = request.args.get('modality')
    project_f  = request.args.get('project_id')

    # SECURITY: always filter by the logged-in user
    q = MedicalImage.query.filter_by(uploaded_by=user_id)
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
    user_id = get_jwt_identity()
    image   = MedicalImage.query.filter_by(id=image_id, uploaded_by=user_id).first_or_404()
    return jsonify(image.to_dict(include_annotations=True))


@images_bp.route('/<image_id>/file', methods=['GET'])
def serve_image_file(image_id):
    """
    Serve image file. Accepts JWT via:
    - Authorization header (normal API calls)
    - ?token= query param (canvas img.src direct loads)
    """
    from flask_jwt_extended import decode_token
    from flask_jwt_extended.exceptions import JWTDecodeError

    # Try header auth first
    auth_header = request.headers.get('Authorization', '')
    token_param = request.args.get('token', '')

    user_id = None
    if auth_header.startswith('Bearer '):
        try:
            from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
            verify_jwt_in_request()
            user_id = get_jwt_identity()
        except Exception:
            pass

    if not user_id and token_param:
        try:
            decoded = decode_token(token_param)
            user_id = decoded.get('sub')
        except Exception:
            pass

    if not user_id:
        return jsonify({'error': 'Unauthorized'}), 401

    # SECURITY: verify the image belongs to this user
    image = MedicalImage.query.filter_by(id=image_id, uploaded_by=user_id).first_or_404()
    path  = image.file_path

    if not path:
        return jsonify({'error': 'No file path stored'}), 404

    # S3 — bucket is private, so generate a fresh short-lived presigned URL
    if path.startswith('s3://'):
        key = path[len('s3://'):]
        url = get_presigned_url(key)
        if not url:
            return jsonify({'error': 'File not accessible'}), 404
        from flask import redirect
        response = redirect(url)
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response

    # Legacy Cloudinary or other external URL — redirect browser
    if path.startswith('http://') or path.startswith('https://'):
        from flask import redirect
        response = redirect(path)
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response

    # Local file
    if os.path.exists(path):
        response = send_file(path, mimetype=image.mime_type or 'image/jpeg')
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response

    return jsonify({'error': 'File not found. Please re-upload.'}), 404


@images_bp.route('/<image_id>/thumbnail', methods=['GET'])
@jwt_required()
def serve_thumbnail(image_id):
    user_id = get_jwt_identity()
    image   = MedicalImage.query.filter_by(id=image_id, uploaded_by=user_id).first_or_404()
    thumb   = image.thumbnail_path

    if thumb:
        if thumb.startswith('s3://'):
            key = thumb[len('s3://'):]
            url = get_presigned_url(key)
            if url:
                from flask import redirect
                return redirect(url)
        elif thumb.startswith('http://') or thumb.startswith('https://'):
            from flask import redirect
            return redirect(thumb)
        elif os.path.exists(thumb):
            return send_file(thumb, mimetype='image/jpeg')

    # Fallback to full image
    return serve_image_file(image_id)


@images_bp.route('/<image_id>', methods=['DELETE'])
@jwt_required()
def delete_image(image_id):
    user_id = get_jwt_identity()
    # SECURITY: only owner can delete their own image
    image = MedicalImage.query.filter_by(id=image_id, uploaded_by=user_id).first_or_404()
    if image.file_path:
        if image.file_path.startswith('s3://'):
            s3_delete(image.file_path[len('s3://'):])
        elif not image.file_path.startswith('http'):
            try: os.remove(image.file_path)
            except Exception: pass
    if image.thumbnail_path and image.thumbnail_path.startswith('s3://'):
        s3_delete(image.thumbnail_path[len('s3://'):])
    db.session.delete(image)
    db.session.commit()
    return jsonify({'message': 'Image deleted'})


@images_bp.route('/stats', methods=['GET'])
@jwt_required()
def get_stats():
    from sqlalchemy import func
    from backend.models.database import Annotation

    user_id = get_jwt_identity()

    # SECURITY: all stats scoped to current user only
    total   = MedicalImage.query.filter_by(uploaded_by=user_id).count()
    ai_done = MedicalImage.query.filter_by(uploaded_by=user_id, ai_processed=True).count()
    approved= MedicalImage.query.filter_by(uploaded_by=user_id, status='approved').count()

    # Count annotations only for this user's images
    annotations = db.session.query(func.count(Annotation.id)).join(
        MedicalImage, Annotation.image_id == MedicalImage.id
    ).filter(
        MedicalImage.uploaded_by == user_id,
        Annotation.is_active == True
    ).scalar() or 0

    mod_counts = db.session.query(
        MedicalImage.modality, func.count(MedicalImage.id)
    ).filter_by(uploaded_by=user_id).group_by(MedicalImage.modality).all()

    status_counts = db.session.query(
        MedicalImage.status, func.count(MedicalImage.id)
    ).filter_by(uploaded_by=user_id).group_by(MedicalImage.status).all()

    return jsonify({
        'total_images':      total,
        'total_annotations': annotations,
        'ai_processed':      ai_done,
        'approved':          approved,
        'by_modality':       {m: c for m, c in mod_counts},
        'by_status':         {s: c for s, c in status_counts},
    })
