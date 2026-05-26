"""
MediMark AI — AI Inference Tests
Tests the mock inference pipeline end-to-end.
"""

import pytest
import io
import numpy as np


def _upload_img(client, headers):
    import cv2
    img = np.random.randint(50, 200, (128, 128, 3), dtype=np.uint8)
    _, buf = cv2.imencode('.jpg', img)
    data = {
        'file':     (io.BytesIO(buf.tobytes()), 'ai_test.jpg'),
        'modality': 'X-Ray',
    }
    resp = client.post('/api/images/upload', data=data,
                       content_type='multipart/form-data',
                       headers={k: v for k, v in headers.items()
                                 if k != 'Content-Type'})
    return resp.get_json()['image']['id']


class TestAIInference:

    def test_model_status(self, client, auth_headers):
        resp = client.get('/api/ai/models/status', headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'yolo' in data
        assert 'unet' in data
        assert 'status' in data['yolo']
        assert 'status' in data['unet']

    def test_analyze_image(self, client, auth_headers):
        img_id = _upload_img(client, auth_headers)
        resp   = client.post(f'/api/ai/analyze/{img_id}',
                             json={}, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'result' in data
        assert 'annotations_created' in data
        assert data['annotations_created'] >= 0

    def test_analyze_creates_annotations(self, client, auth_headers):
        img_id = _upload_img(client, auth_headers)
        client.post(f'/api/ai/analyze/{img_id}', json={}, headers=auth_headers)
        resp = client.get(f'/api/annotations/image/{img_id}',
                          headers=auth_headers)
        assert resp.status_code == 200
        anns = resp.get_json()['annotations']
        assert isinstance(anns, list)
        # Mock backend always produces detections
        assert len(anns) > 0

    def test_analyze_cached(self, client, auth_headers):
        img_id = _upload_img(client, auth_headers)
        client.post(f'/api/ai/analyze/{img_id}', json={}, headers=auth_headers)
        # Second call — should return cached
        resp = client.post(f'/api/ai/analyze/{img_id}',
                           json={}, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get('cached') is True

    def test_analyze_force_rerun(self, client, auth_headers):
        img_id = _upload_img(client, auth_headers)
        client.post(f'/api/ai/analyze/{img_id}', json={}, headers=auth_headers)
        resp = client.post(f'/api/ai/analyze/{img_id}',
                           json={'force_rerun': True}, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get('cached') is not True

    def test_get_inference_results(self, client, auth_headers):
        img_id = _upload_img(client, auth_headers)
        client.post(f'/api/ai/analyze/{img_id}', json={}, headers=auth_headers)
        resp = client.get(f'/api/ai/results/{img_id}', headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'results' in data
        assert len(data['results']) >= 1

    def test_analyze_not_found(self, client, auth_headers):
        resp = client.post('/api/ai/analyze/00000000-0000-0000-0000-000000000000',
                           json={}, headers=auth_headers)
        assert resp.status_code == 404
