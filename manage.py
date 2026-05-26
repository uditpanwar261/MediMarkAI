"""
MediMark AI — Flask CLI Management Commands
Usage:
  flask db-init        Create all tables from models
  flask seed           Seed demo data
  flask create-admin   Create an admin user interactively
  flask purge-uploads  Remove orphaned upload files
"""

import click
from flask.cli import with_appcontext
from app import app
from backend.extensions import db


@app.cli.command('db-init')
@with_appcontext
def db_init():
    """Create all database tables."""
    db.create_all()
    click.echo('✓ Database tables created.')


@app.cli.command('seed')
@with_appcontext
def seed_data():
    """Seed the database with demo project and label classes."""
    from backend.models.database import User, Project, LabelClass
    from werkzeug.security import generate_password_hash
    import uuid

    # Admin user
    if not User.query.filter_by(email='admin@medimark.ai').first():
        user = User(
            id=str(uuid.uuid4()),
            email='admin@medimark.ai',
            password_hash=generate_password_hash('demo1234'),
            full_name='Dr. Admin',
            role='admin',
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
        click.echo('✓ Demo admin, project, and label classes seeded.')
        click.echo('  Login: admin@medimark.ai / demo1234')
    else:
        click.echo('ℹ  Admin user already exists — skipping seed.')


@app.cli.command('create-admin')
@click.option('--email',    prompt='Email address')
@click.option('--name',     prompt='Full name')
@click.option('--password', prompt=True, hide_input=True,
              confirmation_prompt=True)
@with_appcontext
def create_admin(email, name, password):
    """Create a new admin user."""
    from backend.models.database import User
    from werkzeug.security import generate_password_hash
    import uuid

    if User.query.filter_by(email=email).first():
        click.echo(f'✗ User {email} already exists.')
        return

    user = User(
        id=str(uuid.uuid4()),
        email=email.lower().strip(),
        password_hash=generate_password_hash(password),
        full_name=name,
        role='admin',
        is_active=True,
        is_verified=True,
    )
    db.session.add(user)
    db.session.commit()
    click.echo(f'✓ Admin user {email} created.')


@app.cli.command('purge-uploads')
@click.option('--dry-run', is_flag=True, default=True,
              help='List files without deleting (default)')
@with_appcontext
def purge_uploads(dry_run):
    """Remove upload files not referenced in the database."""
    import os
    from flask import current_app
    from backend.models.database import MedicalImage

    folders = [
        current_app.config['UPLOAD_FOLDER'],
        current_app.config['PROCESSED_FOLDER'],
    ]
    db_files = {os.path.basename(img.file_path)
                for img in MedicalImage.query.all() if img.file_path}
    removed = 0

    for folder in folders:
        if not os.path.exists(folder):
            continue
        for fname in os.listdir(folder):
            fpath = os.path.join(folder, fname)
            if not os.path.isfile(fpath):
                continue
            if fname not in db_files:
                if dry_run:
                    click.echo(f'  [DRY-RUN] Would remove: {fpath}')
                else:
                    os.remove(fpath)
                    click.echo(f'  Removed: {fpath}')
                removed += 1

    action = 'Would remove' if dry_run else 'Removed'
    click.echo(f'✓ {action} {removed} orphaned file(s).')
    if dry_run and removed:
        click.echo('  Re-run with --no-dry-run to delete.')


if __name__ == '__main__':
    app.run()
