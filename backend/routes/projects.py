"""
MediMark AI — Projects Routes
Create and manage annotation projects that group related images.
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from backend.extensions import db
from backend.models.database import Project, LabelClass, MedicalImage, AuditLog

projects_bp = Blueprint('projects', __name__)


@projects_bp.route('/', methods=['GET'])
@jwt_required()
def list_projects():
    user_id = get_jwt_identity()
    status  = request.args.get('status')
    # SECURITY: only return this user's projects
    query = Project.query.filter_by(created_by=user_id)
    if status:
        query = query.filter_by(status=status)
    projects = query.order_by(Project.created_at.desc()).all()
    return jsonify({'projects': [p.to_dict() for p in projects]})


@projects_bp.route('/', methods=['POST'])
@jwt_required()
def create_project():
    user_id = get_jwt_identity()
    data = request.get_json()

    if not data.get('name'):
        return jsonify({'error': 'Project name is required'}), 400

    project = Project(
        name=data['name'],
        description=data.get('description'),
        modality=data.get('modality'),
        target_pathology=data.get('target_pathology'),
        created_by=user_id
    )
    db.session.add(project)

    # Seed default label classes if provided
    for lc_data in data.get('label_classes', []):
        lc = LabelClass(
            project_id=project.id,
            name=lc_data['name'],
            display_name=lc_data.get('display_name', lc_data['name']),
            color=lc_data.get('color', '#00D4FF'),
            icd_code=lc_data.get('icd_code')
        )
        db.session.add(lc)

    db.session.commit()

    try:
        AuditLog.log(user_id, 'project_create', 'project', project.id,
                     f"Created project: {project.name}", request.remote_addr)
    except Exception:
        pass

    return jsonify({'project': project.to_dict()}), 201


@projects_bp.route('/<project_id>', methods=['GET'])
@jwt_required()
def get_project(project_id):
    project = Project.query.get_or_404(project_id)
    data = project.to_dict()
    data['label_classes'] = [lc.to_dict() for lc in project.label_classes.all()]
    return jsonify(data)


@projects_bp.route('/<project_id>', methods=['PUT'])
@jwt_required()
def update_project(project_id):
    project = Project.query.get_or_404(project_id)
    data = request.get_json()

    for field in ['name', 'description', 'modality', 'target_pathology', 'status']:
        if field in data:
            setattr(project, field, data[field])

    db.session.commit()
    return jsonify({'project': project.to_dict()})


@projects_bp.route('/<project_id>/label-classes', methods=['POST'])
@jwt_required()
def add_label_class(project_id):
    Project.query.get_or_404(project_id)
    data = request.get_json()

    if not data.get('name'):
        return jsonify({'error': 'Label name required'}), 400

    lc = LabelClass(
        project_id=project_id,
        name=data['name'],
        display_name=data.get('display_name', data['name']),
        color=data.get('color', '#00D4FF'),
        description=data.get('description'),
        icd_code=data.get('icd_code')
    )
    db.session.add(lc)
    db.session.commit()
    return jsonify({'label_class': lc.to_dict()}), 201


@projects_bp.route('/<project_id>/stats', methods=['GET'])
@jwt_required()
def project_stats(project_id):
    from sqlalchemy import func
    from backend.models.database import Annotation

    project = Project.query.get_or_404(project_id)
    total = project.images.count()
    approved = project.images.filter_by(status='approved').count()
    ai_done = project.images.filter_by(ai_processed=True).count()

    ann_count = db.session.query(func.count(Annotation.id)).join(
        MedicalImage, Annotation.image_id == MedicalImage.id
    ).filter(
        MedicalImage.project_id == project_id,
        Annotation.is_active == True
    ).scalar()

    return jsonify({
        'project_id': project_id,
        'total_images': total,
        'approved': approved,
        'ai_processed': ai_done,
        'total_annotations': ann_count or 0,
        'completion_pct': round((approved / total * 100) if total else 0, 1)
    })
