"""
MediMark AI — Annotation Routes
All queries scoped to the logged-in user's images only.
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from backend.extensions import db
from backend.models.database import Annotation, MedicalImage, AuditLog
import json

annotations_bp = Blueprint('annotations', __name__)


def _verify_image_owner(image_id: str, user_id: str):
    """Return image if it belongs to user, else 404."""
    return MedicalImage.query.filter_by(
        id=image_id, uploaded_by=user_id
    ).first_or_404()


def _verify_annotation_owner(annotation_id: str, user_id: str):
    """Return annotation only if its image belongs to the user."""
    ann = Annotation.query.get_or_404(annotation_id)
    # Verify the parent image belongs to this user
    MedicalImage.query.filter_by(
        id=ann.image_id, uploaded_by=user_id
    ).first_or_404()
    return ann


@annotations_bp.route('/image/<image_id>', methods=['GET'])
@jwt_required()
def get_image_annotations(image_id):
    user_id = get_jwt_identity()
    # Verify ownership before returning annotations
    _verify_image_owner(image_id, user_id)

    annotation_type = request.args.get('type')
    source          = request.args.get('source')
    verified_only   = request.args.get('verified') == 'true'

    query = Annotation.query.filter_by(image_id=image_id, is_active=True)
    if annotation_type: query = query.filter_by(annotation_type=annotation_type)
    if source:          query = query.filter_by(source=source)
    if verified_only:   query = query.filter_by(is_verified=True)

    annotations = query.order_by(Annotation.created_at.asc()).all()
    return jsonify({'annotations': [a.to_dict() for a in annotations]})


@annotations_bp.route('/', methods=['POST'])
@jwt_required()
def create_annotation():
    user_id = get_jwt_identity()
    data    = request.get_json()

    required = ['image_id', 'label_name', 'annotation_type']
    for field in required:
        if not data.get(field):
            return jsonify({'error': f'{field} is required'}), 400

    # SECURITY: verify image belongs to this user
    image = _verify_image_owner(data['image_id'], user_id)

    annotation = Annotation(
        image_id          = data['image_id'],
        label_name        = data['label_name'],
        annotation_type   = data['annotation_type'],
        source            = data.get('source', 'manual'),
        x_min             = data.get('x_min'),
        y_min             = data.get('y_min'),
        x_max             = data.get('x_max'),
        y_max             = data.get('y_max'),
        segmentation_data = json.dumps(data['segmentation_data'])
            if isinstance(data.get('segmentation_data'), (dict, list))
            else data.get('segmentation_data'),
        confidence        = data.get('confidence'),
        notes             = data.get('notes'),
        severity          = data.get('severity'),
        label_class_id    = data.get('label_class_id'),
        annotated_by      = user_id,
    )
    db.session.add(annotation)

    if image.status == 'uploaded':
        image.status = 'under_review'
    db.session.commit()

    return jsonify({'annotation': annotation.to_dict()}), 201


@annotations_bp.route('/<annotation_id>', methods=['PUT'])
@jwt_required()
def update_annotation(annotation_id):
    user_id    = get_jwt_identity()
    # SECURITY: only owner can update
    annotation = _verify_annotation_owner(annotation_id, user_id)
    data       = request.get_json()

    updatable = ['label_name', 'x_min', 'y_min', 'x_max', 'y_max',
                 'segmentation_data', 'notes', 'severity', 'confidence',
                 'is_verified', 'label_class_id']

    for field in updatable:
        if field in data:
            val = data[field]
            if field == 'segmentation_data' and isinstance(val, (dict, list)):
                val = json.dumps(val)
            setattr(annotation, field, val)

    if data.get('is_verified') and (annotation.source or '').startswith('ai_'):
        annotation.source      = 'ai_assisted'
        annotation.verified_by = user_id

    db.session.commit()
    return jsonify({'annotation': annotation.to_dict()})


@annotations_bp.route('/<annotation_id>', methods=['DELETE'])
@jwt_required()
def delete_annotation(annotation_id):
    user_id    = get_jwt_identity()
    # SECURITY: only owner can delete
    annotation = _verify_annotation_owner(annotation_id, user_id)
    annotation.is_active = False
    db.session.commit()
    return jsonify({'message': 'Annotation deleted'})


@annotations_bp.route('/image/<image_id>/approve', methods=['POST'])
@jwt_required()
def approve_image_annotations(image_id):
    user_id = get_jwt_identity()
    # SECURITY: only owner can approve
    image = _verify_image_owner(image_id, user_id)

    Annotation.query.filter_by(
        image_id=image_id, is_active=True
    ).update({'is_verified': True, 'verified_by': user_id})

    image.status = 'approved'
    db.session.commit()
    return jsonify({'message': 'All annotations approved', 'image_status': 'approved'})


@annotations_bp.route('/export/<image_id>', methods=['GET'])
@jwt_required()
def export_annotations(image_id):
    user_id = get_jwt_identity()
    # SECURITY: only owner can export
    image = _verify_image_owner(image_id, user_id)

    fmt = request.args.get('format', 'coco').lower()
    annotations = Annotation.query.filter_by(
        image_id=image_id, is_active=True, is_verified=True
    ).all()

    if fmt == 'yolo':
        lines = []
        for ann in annotations:
            if ann.annotation_type == 'bounding_box' and ann.x_min is not None:
                cx = (ann.x_min + ann.x_max) / 2
                cy = (ann.y_min + ann.y_max) / 2
                bw = ann.x_max - ann.x_min
                bh = ann.y_max - ann.y_min
                lines.append(f"0 {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")
        return '\n'.join(lines), 200, {
            'Content-Type': 'text/plain',
            'Content-Disposition': f'attachment; filename={image_id}.txt'
        }
    else:
        # COCO format
        coco = {
            'info':        {'description': 'MediMark AI Export', 'version': '1.0'},
            'images':      [{'id': image_id, 'file_name': image.original_filename,
                              'width': image.width, 'height': image.height}],
            'annotations': [],
            'categories':  []
        }
        label_map = {}
        for i, ann in enumerate(annotations):
            if ann.label_name not in label_map:
                cat_id = len(label_map) + 1
                label_map[ann.label_name] = cat_id
                coco['categories'].append({'id': cat_id, 'name': ann.label_name})
            cat_id    = label_map[ann.label_name]
            ann_entry = {
                'id':          i + 1,
                'image_id':    image_id,
                'category_id': cat_id,
                'source':      ann.source,
                'confidence':  ann.confidence,
            }
            if ann.x_min is not None and image.width:
                x1 = ann.x_min * image.width
                y1 = ann.y_min * image.height
                bw = (ann.x_max - ann.x_min) * image.width
                bh = (ann.y_max - ann.y_min) * image.height
                ann_entry['bbox'] = [round(x1, 2), round(y1, 2), round(bw, 2), round(bh, 2)]
                ann_entry['area'] = round(bw * bh, 2)
            coco['annotations'].append(ann_entry)

        return json.dumps(coco, indent=2), 200, {
            'Content-Type': 'application/json',
            'Content-Disposition': f'attachment; filename={image_id}_coco.json'
        }
