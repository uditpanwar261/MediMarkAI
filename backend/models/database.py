"""
MediMark AI - Database Models
PostgreSQL compatible (no inline ENUMs - uses String instead)
"""

from backend.extensions import db
from datetime import datetime
import uuid


def generate_uuid():
    return str(uuid.uuid4())


class User(db.Model):
    __tablename__ = 'users'

    id            = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    email         = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name     = db.Column(db.String(255), nullable=False)
    role          = db.Column(db.String(20), nullable=False, default='radiologist')
    specialty     = db.Column(db.String(100))
    institution   = db.Column(db.String(255))
    is_active     = db.Column(db.Boolean, default=True)
    is_verified   = db.Column(db.Boolean, default=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    last_login    = db.Column(db.DateTime)

    images      = db.relationship('MedicalImage', backref='uploaded_by_user',
                                   lazy='dynamic', foreign_keys='MedicalImage.uploaded_by')
    annotations = db.relationship('Annotation', backref='annotator',
                                   lazy='dynamic', foreign_keys='Annotation.annotated_by')

    def to_dict(self):
        return {
            'id':          self.id,
            'email':       self.email,
            'full_name':   self.full_name,
            'role':        self.role,
            'specialty':   self.specialty,
            'institution': self.institution,
            'is_active':   self.is_active,
            'created_at':  self.created_at.isoformat() if self.created_at else None,
        }


class MedicalImage(db.Model):
    __tablename__ = 'medical_images'

    id                 = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    filename           = db.Column(db.String(500), nullable=False)
    original_filename  = db.Column(db.String(500), nullable=False)
    file_path          = db.Column(db.String(1000), nullable=False)
    processed_path     = db.Column(db.String(1000))
    thumbnail_path     = db.Column(db.String(1000))
    file_size          = db.Column(db.BigInteger)
    mime_type          = db.Column(db.String(100))

    # Medical metadata
    modality          = db.Column(db.String(20), default='Other')
    body_part         = db.Column(db.String(100))
    patient_id        = db.Column(db.String(100))
    study_date        = db.Column(db.Date)
    study_description = db.Column(db.Text)
    series_uid        = db.Column(db.String(200))

    # Image properties
    width    = db.Column(db.Integer)
    height   = db.Column(db.Integer)
    channels = db.Column(db.Integer, default=3)

    # Status
    status              = db.Column(db.String(20), default='uploaded', index=True)
    ai_processed        = db.Column(db.Boolean, default=False)
    ai_processing_time  = db.Column(db.Float)

    uploaded_by = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    project_id  = db.Column(db.String(36), db.ForeignKey('projects.id'))
    created_at  = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at  = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    annotations  = db.relationship('Annotation', backref='image',
                                    lazy='dynamic', cascade='all, delete-orphan')
    ai_results   = db.relationship('AIInferenceResult', backref='image',
                                    lazy='dynamic', cascade='all, delete-orphan')

    def to_dict(self, include_annotations=False):
        # Expose Cloudinary URLs directly so frontend can load images without auth redirect
        file_path  = self.file_path  or ''
        thumb_path = self.thumbnail_path or ''
        data = {
            'id':                self.id,
            'filename':          self.filename,
            'original_filename': self.original_filename,
            'modality':          self.modality,
            'body_part':         self.body_part,
            'patient_id':        self.patient_id,
            'width':             self.width,
            'height':            self.height,
            'status':            self.status,
            'ai_processed':      self.ai_processed,
            'created_at':        self.created_at.isoformat() if self.created_at else None,
            'annotation_count':  self.annotations.count(),
            # Include cloud URLs if available — empty string if local path
            'file_path':      file_path  if file_path.startswith('http')  else '',
            'thumbnail_path': thumb_path if thumb_path.startswith('http') else '',
        }
        if include_annotations:
            data['annotations'] = [a.to_dict() for a in self.annotations.all()]
        return data


class Project(db.Model):
    __tablename__ = 'projects'

    id               = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    name             = db.Column(db.String(255), nullable=False)
    description      = db.Column(db.Text)
    modality         = db.Column(db.String(50))
    target_pathology = db.Column(db.String(200))
    status           = db.Column(db.String(20), default='active')
    created_by       = db.Column(db.String(36), db.ForeignKey('users.id'))
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)

    images        = db.relationship('MedicalImage', backref='project', lazy='dynamic')
    label_classes = db.relationship('LabelClass', backref='project',
                                     lazy='dynamic', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id':               self.id,
            'name':             self.name,
            'description':      self.description,
            'modality':         self.modality,
            'target_pathology': self.target_pathology,
            'status':           self.status,
            'image_count':      self.images.count(),
            'created_at':       self.created_at.isoformat() if self.created_at else None,
        }


class LabelClass(db.Model):
    __tablename__ = 'label_classes'

    id           = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    project_id   = db.Column(db.String(36), db.ForeignKey('projects.id'), nullable=False)
    name         = db.Column(db.String(100), nullable=False)
    display_name = db.Column(db.String(150))
    color        = db.Column(db.String(7), default='#FF6B6B')
    description  = db.Column(db.Text)
    icd_code     = db.Column(db.String(20))
    is_active    = db.Column(db.Boolean, default=True)

    def to_dict(self):
        return {
            'id':           self.id,
            'name':         self.name,
            'display_name': self.display_name or self.name,
            'color':        self.color,
            'description':  self.description,
            'icd_code':     self.icd_code,
        }


class Annotation(db.Model):
    __tablename__ = 'annotations'

    id              = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    image_id        = db.Column(db.String(36), db.ForeignKey('medical_images.id'),
                                nullable=False, index=True)
    label_class_id  = db.Column(db.String(36), db.ForeignKey('label_classes.id'))
    label_name      = db.Column(db.String(100), nullable=False)

    annotation_type = db.Column(db.String(20), nullable=False, default='bounding_box')
    source          = db.Column(db.String(20), default='manual')

    x_min = db.Column(db.Float)
    y_min = db.Column(db.Float)
    x_max = db.Column(db.Float)
    y_max = db.Column(db.Float)

    segmentation_data = db.Column(db.Text)
    mask_path         = db.Column(db.String(500))

    confidence  = db.Column(db.Float)
    is_verified = db.Column(db.Boolean, default=False)
    is_active   = db.Column(db.Boolean, default=True)
    notes       = db.Column(db.Text)
    severity    = db.Column(db.String(20))

    annotated_by = db.Column(db.String(36), db.ForeignKey('users.id'))
    verified_by  = db.Column(db.String(36), db.ForeignKey('users.id'))
    created_at   = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at   = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id':              self.id,
            'image_id':        self.image_id,
            'label_name':      self.label_name,
            'annotation_type': self.annotation_type,
            'source':          self.source,
            'bbox': {
                'x_min': self.x_min,
                'y_min': self.y_min,
                'x_max': self.x_max,
                'y_max': self.y_max,
            } if self.x_min is not None else None,
            'segmentation_data': self.segmentation_data,
            'confidence':        self.confidence,
            'is_verified':       self.is_verified,
            'notes':             self.notes,
            'severity':          self.severity,
            'annotated_by':      self.annotated_by,
            'created_at':        self.created_at.isoformat() if self.created_at else None,
        }


class AIInferenceResult(db.Model):
    __tablename__ = 'ai_inference_results'

    id            = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    image_id      = db.Column(db.String(36), db.ForeignKey('medical_images.id'),
                               nullable=False, index=True)
    model_type    = db.Column(db.String(20), nullable=False)
    model_version = db.Column(db.String(50))

    detections    = db.Column(db.Text)
    segmentations = db.Column(db.Text)

    inference_time  = db.Column(db.Float)
    num_detections  = db.Column(db.Integer, default=0)
    avg_confidence  = db.Column(db.Float)

    status        = db.Column(db.String(20), default='pending')
    error_message = db.Column(db.Text)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        import json
        return {
            'id':             self.id,
            'image_id':       self.image_id,
            'model_type':     self.model_type,
            'model_version':  self.model_version,
            'detections':     json.loads(self.detections)    if self.detections    else [],
            'segmentations':  json.loads(self.segmentations) if self.segmentations else [],
            'inference_time': self.inference_time,
            'num_detections': self.num_detections,
            'avg_confidence': self.avg_confidence,
            'status':         self.status,
            'created_at':     self.created_at.isoformat() if self.created_at else None,
        }


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'

    id            = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    user_id       = db.Column(db.String(36), db.ForeignKey('users.id'))
    action        = db.Column(db.String(100), nullable=False)
    resource_type = db.Column(db.String(50))
    resource_id   = db.Column(db.String(36))
    details       = db.Column(db.Text)
    ip_address    = db.Column(db.String(45))
    user_agent    = db.Column(db.String(500))
    timestamp     = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    @classmethod
    def log(cls, user_id, action, resource_type=None, resource_id=None,
            details=None, ip_address=None, user_agent=None):
        try:
            entry = cls(
                user_id=user_id, action=action,
                resource_type=resource_type, resource_id=resource_id,
                details=details, ip_address=ip_address, user_agent=user_agent
            )
            db.session.add(entry)
            db.session.commit()
            return entry
        except Exception:
            db.session.rollback()
