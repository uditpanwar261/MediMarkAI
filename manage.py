"""
MediMark AI — Flask CLI Management Commands
Works with both MySQL (local) and PostgreSQL (Render).

Usage:
  flask --app manage seed           Seed demo data
  flask --app manage create-admin   Create admin interactively
  flask --app manage db-init        Create all tables
  flask --app manage purge-uploads  Remove orphaned files
"""

import click
from flask.cli import with_appcontext
from app import app
from backend.extensions import db


@app.cli.command('db-init')
@with_appcontext
def db_init():
    """Create all database tables from SQLAlchemy models."""
    db.create_all()
    click.echo('✓ All tables created.')


@app.cli.command('seed')
@with_appcontext
def seed_data():
    """Seed admin user, demo project and label classes."""
    from backend.models.database import User, Project, LabelClass
    from werkzeug.security import generate_password_hash
    import uuid

    # ── Admin user ───────────────────────────────────────────────
    if User.query.filter_by(email='admin@medimark.ai').first():
        click.echo('ℹ  Admin user already exists — skipping seed.')
        return

    click.echo('Seeding database...')

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

    # ── Demo project ─────────────────────────────────────────────
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

    # ── Label classes with ICD-10 codes ─────────────────────────
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
    click.echo('✓ Admin user, project and 10 label classes seeded.')
    click.echo('  Login → admin@medimark.ai / demo1234')


@app.cli.command('create-admin')
@click.option('--email',    prompt='Email address')
@click.option('--name',     prompt='Full name')
@click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True)
@with_appcontext
def create_admin(email, name, password):
    """Create a new admin user interactively."""
    from backend.models.database import User
    from werkzeug.security import generate_password_hash
    import uuid

    if User.query.filter_by(email=email.lower().strip()).first():
        click.echo(f'✗  {email} already exists.')
        return

    u = User(
        id=str(uuid.uuid4()),
        email=email.lower().strip(),
        password_hash=generate_password_hash(password),
        full_name=name,
        role='admin',
        is_active=True,
        is_verified=True,
    )
    db.session.add(u)
    db.session.commit()
    click.echo(f'✓  Admin user {email} created.')


@app.cli.command('purge-uploads')
@click.option('--no-dry-run', is_flag=True, default=False,
              help='Actually delete files (default is dry-run)')
@with_appcontext
def purge_uploads(no_dry_run):
    """List or remove upload files not referenced in the database."""
    import os
    from flask import current_app
    from backend.models.database import MedicalImage

    folders = [
        current_app.config['UPLOAD_FOLDER'],
        current_app.config['PROCESSED_FOLDER'],
    ]
    db_files = {
        os.path.basename(img.file_path)
        for img in MedicalImage.query.all()
        if img.file_path
    }
    removed = 0
    for folder in folders:
        if not os.path.exists(folder):
            continue
        for fname in os.listdir(folder):
            fpath = os.path.join(folder, fname)
            if not os.path.isfile(fpath):
                continue
            if fname not in db_files:
                if no_dry_run:
                    os.remove(fpath)
                    click.echo(f'  Removed: {fpath}')
                else:
                    click.echo(f'  [dry-run] Would remove: {fpath}')
                removed += 1

    action = 'Removed' if no_dry_run else 'Would remove'
    click.echo(f'✓ {action} {removed} orphaned file(s).')
    if not no_dry_run and removed:
        click.echo('  Re-run with --no-dry-run to actually delete.')


if __name__ == '__main__':
    app.run()
