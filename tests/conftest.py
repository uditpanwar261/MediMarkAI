"""
MediMark AI — Test Configuration & Fixtures
"""

import pytest
import os
import io
from app import create_app
from backend.extensions import db as _db
from backend.config import TestingConfig
from werkzeug.security import generate_password_hash


@pytest.fixture(scope='session')
def app():
    """Create application for the test session."""
    os.environ['TESTING'] = '1'
    application = create_app(TestingConfig)
    ctx = application.app_context()
    ctx.push()
    _db.create_all()
    yield application
    _db.drop_all()
    ctx.pop()


@pytest.fixture(scope='session')
def db(app):
    return _db


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def runner(app):
    return app.test_cli_runner()


# ── Seed helpers ──────────────────────────────────────────────
def _make_user(db, email='doc@test.com', role='radiologist', password='test1234'):
    from backend.models.database import User
    u = User(
        email=email,
        password_hash=generate_password_hash(password),
        full_name='Dr Test',
        role=role
    )
    db.session.add(u)
    db.session.commit()
    return u


@pytest.fixture()
def user(db):
    from backend.models.database import User
    u = User.query.filter_by(email='doc@test.com').first()
    if not u:
        u = _make_user(db)
    return u


@pytest.fixture()
def admin_user(db):
    from backend.models.database import User
    u = User.query.filter_by(email='admin@test.com').first()
    if not u:
        u = _make_user(db, email='admin@test.com', role='admin')
    return u


@pytest.fixture()
def auth_headers(client, user):
    resp = client.post('/api/auth/login', json={
        'email': 'doc@test.com',
        'password': 'test1234'
    })
    token = resp.get_json()['access_token']
    return {'Authorization': f'Bearer {token}'}


@pytest.fixture()
def admin_headers(client, admin_user):
    resp = client.post('/api/auth/login', json={
        'email': 'admin@test.com',
        'password': 'test1234'
    })
    token = resp.get_json()['access_token']
    return {'Authorization': f'Bearer {token}'}


@pytest.fixture()
def sample_image_file():
    """Return a minimal 1×1 PNG as BytesIO."""
    import struct, zlib
    def png_1x1(r, g, b):
        sig   = b'\x89PNG\r\n\x1a\n'
        ihdr  = struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0)
        ihdr_crc = zlib.crc32(b'IHDR' + ihdr) & 0xffffffff
        raw   = b'\x00' + bytes([r, g, b])
        idat  = zlib.compress(raw)
        idat_crc = zlib.crc32(b'IDAT' + idat) & 0xffffffff
        iend_crc = zlib.crc32(b'IEND') & 0xffffffff
        return (sig
                + struct.pack('>I', 13) + b'IHDR' + ihdr + struct.pack('>I', ihdr_crc)
                + struct.pack('>I', len(idat)) + b'IDAT' + idat + struct.pack('>I', idat_crc)
                + struct.pack('>I', 0) + b'IEND' + struct.pack('>I', iend_crc))
    return io.BytesIO(png_1x1(128, 128, 128))
