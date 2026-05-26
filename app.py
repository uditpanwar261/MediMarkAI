"""
MediMark AI — Flask Application Factory
Auto-creates tables and seeds data on first startup.
Works on Render free tier without shell access.
"""

from flask import Flask
from flask_cors import CORS
from backend.config import Config
from backend.extensions import db, migrate, jwt, limiter
from backend.routes.auth import auth_bp
from backend.routes.images import images_bp
from backend.routes.annotations import annotations_bp
from backend.routes.ai_inference import ai_bp
from backend.routes.dashboard import dashboard_bp
from backend.routes.projects import projects_bp
from backend.routes.users import users_bp
import logging
import os


def seed_initial_data(app):
    """
    Create tables and seed demo data automatically on first startup.
    Safe to call multiple times — skips if data already exists.
    """
    with app.app_context():
        try:
            # Create all tables
            db.create_all()
            app.logger.info("Database tables ready.")

            # Seed demo data
            from backend.models.database import User, Project, LabelClass
            from werkzeug.security import generate_password_hash
            import uuid

            if User.query.filter_by(email='admin@medimark.ai').first():
                app.logger.info("Seed data already exists — skipping.")
                return

            app.logger.info("Seeding demo data...")

            user = User(
                id=str(uuid.uuid4()),
                email='admin@medimark.ai',
                password_hash=generate_password_hash('demo1234'),
                full_name='Dr. Admin',
                role='admin',
                specialty='Radiology',
                institution='MediMark Medical Center',
                is_active=True,
                is_verified=True,
            )
            db.session.add(user)
            db.session.flush()

            project = Project(
                id=str(uuid.uuid4()),
                name='Chest X-Ray Pathology Detection',
                description='Annotation project for common chest pathologies.',
                modality='X-Ray',
                target_pathology='Pneumonia, Nodules, Cardiomegaly',
                created_by=user.id,
            )
            db.session.add(project)
            db.session.flush()

            CLASSES = [
                ('Pulmonary Nodule',     '#FF4757', 'J98.4'),
                ('Ground-glass Opacity', '#FFA502', 'J18.0'),
                ('Consolidation',        '#2ED573', 'J18.9'),
                ('Pleural Effusion',     '#5352ED', 'J90'),
                ('Cardiomegaly',         '#FF6B81', 'I51.7'),
                ('Pneumothorax',         '#ECCC68', 'J93.1'),
                ('Mass Lesion',          '#FF3742', 'R91.1'),
                ('Calcification',        '#70A1FF', None),
                ('Atelectasis',          '#FF7F50', None),
                ('Normal',               '#00E676', 'Z00.00'),
            ]
            for name, color, icd in CLASSES:
                db.session.add(LabelClass(
                    id=str(uuid.uuid4()),
                    project_id=project.id,
                    name=name,
                    display_name=name,
                    color=color,
                    icd_code=icd,
                ))

            db.session.commit()
            app.logger.info("✓ Seed complete — admin@medimark.ai / demo1234")

        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Seed error (non-fatal): {e}")


def create_app(config_class=Config):
    app = Flask(
        __name__,
        template_folder='frontend/templates',
        static_folder='frontend/static'
    )
    app.config.from_object(config_class)

    # Extensions
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    limiter.init_app(app)
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # Blueprints
    app.register_blueprint(auth_bp,        url_prefix='/api/auth')
    app.register_blueprint(images_bp,      url_prefix='/api/images')
    app.register_blueprint(annotations_bp, url_prefix='/api/annotations')
    app.register_blueprint(ai_bp,          url_prefix='/api/ai')
    app.register_blueprint(projects_bp,    url_prefix='/api/projects')
    app.register_blueprint(users_bp,       url_prefix='/api/users')
    app.register_blueprint(dashboard_bp,   url_prefix='/')

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    )

    # Create upload directories
    os.makedirs(app.config['UPLOAD_FOLDER'],    exist_ok=True)
    os.makedirs(app.config['PROCESSED_FOLDER'], exist_ok=True)

    # Auto-seed on startup (safe to run multiple times)
    seed_initial_data(app)

    return app


app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
