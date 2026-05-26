"""
MediMark AI — Auth Route Tests
"""

import pytest


class TestAuth:

    def test_register_success(self, client, db):
        resp = client.post('/api/auth/register', json={
            'email':     'newdoc@test.com',
            'password':  'securepass1',
            'full_name': 'Dr New',
            'role':      'radiologist'
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert 'access_token' in data
        assert data['user']['email'] == 'newdoc@test.com'

    def test_register_duplicate_email(self, client, user):
        resp = client.post('/api/auth/register', json={
            'email':     'doc@test.com',
            'password':  'pass1234',
            'full_name': 'Dr Dup',
            'role':      'radiologist'
        })
        assert resp.status_code == 409

    def test_register_missing_field(self, client):
        resp = client.post('/api/auth/register', json={
            'email': 'noname@test.com',
            'password': 'pass1234'
            # full_name missing
        })
        assert resp.status_code == 400

    def test_login_success(self, client, user):
        resp = client.post('/api/auth/login', json={
            'email':    'doc@test.com',
            'password': 'test1234'
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'access_token' in data
        assert 'refresh_token' in data

    def test_login_wrong_password(self, client, user):
        resp = client.post('/api/auth/login', json={
            'email':    'doc@test.com',
            'password': 'wrongpass'
        })
        assert resp.status_code == 401

    def test_login_unknown_email(self, client):
        resp = client.post('/api/auth/login', json={
            'email':    'nobody@test.com',
            'password': 'pass1234'
        })
        assert resp.status_code == 401

    def test_me_authenticated(self, client, auth_headers):
        resp = client.get('/api/auth/me', headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()['email'] == 'doc@test.com'

    def test_me_unauthenticated(self, client):
        resp = client.get('/api/auth/me')
        assert resp.status_code == 401

    def test_token_refresh(self, client, user):
        login = client.post('/api/auth/login', json={
            'email': 'doc@test.com', 'password': 'test1234'
        })
        refresh_token = login.get_json()['refresh_token']
        resp = client.post('/api/auth/refresh',
                           headers={'Authorization': f'Bearer {refresh_token}'})
        assert resp.status_code == 200
        assert 'access_token' in resp.get_json()
