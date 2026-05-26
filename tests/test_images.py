"""
MediMark AI — Image Route Tests
"""

import pytest
import io


def _upload(client, headers, file_bytes=None, filename='test.png',
            modality='X-Ray', body_part='Chest'):
    if file_bytes is None:
        # Minimal valid PNG (8×8 grey)
        import numpy as np, cv2
        img  = np.full((8, 8, 3), 128, dtype=np.uint8)
        _, buf = cv2.imencode('.png', img)
        file_bytes = buf.tobytes()

    data = {
        'file':      (io.BytesIO(file_bytes), filename),
        'modality':  modality,
        'body_part': body_part,
    }
    return client.post('/api/images/upload',
                       data=data,
                       content_type='multipart/form-data',
                       headers={k: v for k, v in headers.items()
                                 if k != 'Content-Type'})


class TestImages:

    def test_upload_png(self, client, auth_headers):
        resp = _upload(client, auth_headers)
        assert resp.status_code == 201
        data = resp.get_json()
        assert 'image' in data
        assert data['image']['modality'] == 'X-Ray'

    def test_upload_invalid_extension(self, client, auth_headers):
        resp = _upload(client, auth_headers,
                       file_bytes=b'fake', filename='doc.pdf')
        assert resp.status_code == 400

    def test_upload_requires_auth(self, client):
        resp = _upload(client, {})
        assert resp.status_code == 401

    def test_list_images(self, client, auth_headers):
        _upload(client, auth_headers)
        resp = client.get('/api/images/', headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'images' in data
        assert isinstance(data['images'], list)
        assert 'total' in data

    def test_list_images_filter_status(self, client, auth_headers):
        resp = client.get('/api/images/?status=uploaded', headers=auth_headers)
        assert resp.status_code == 200

    def test_get_image(self, client, auth_headers):
        up = _upload(client, auth_headers).get_json()
        img_id = up['image']['id']
        resp = client.get(f'/api/images/{img_id}', headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()['id'] == img_id

    def test_get_image_not_found(self, client, auth_headers):
        resp = client.get('/api/images/00000000-0000-0000-0000-000000000000',
                          headers=auth_headers)
        assert resp.status_code == 404

    def test_stats(self, client, auth_headers):
        resp = client.get('/api/images/stats', headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'total_images' in data
        assert 'total_annotations' in data

    def test_delete_image(self, client, auth_headers):
        up = _upload(client, auth_headers).get_json()
        img_id = up['image']['id']
        resp = client.delete(f'/api/images/{img_id}', headers=auth_headers)
        assert resp.status_code == 200
        # Should 404 now
        resp2 = client.get(f'/api/images/{img_id}', headers=auth_headers)
        assert resp2.status_code == 404
