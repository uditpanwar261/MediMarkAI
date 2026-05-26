"""
MediMark AI — Annotation Route Tests
"""

import pytest
import io
import numpy as np


def _make_image(client, headers):
    import cv2
    img = np.full((64, 64, 3), 100, dtype=np.uint8)
    _, buf = cv2.imencode('.png', img)
    data = {
        'file':     (io.BytesIO(buf.tobytes()), 'ann_test.png'),
        'modality': 'CT',
    }
    resp = client.post('/api/images/upload',
                       data=data, content_type='multipart/form-data',
                       headers={k: v for k, v in headers.items()
                                 if k != 'Content-Type'})
    return resp.get_json()['image']['id']


class TestAnnotations:

    def test_create_bbox(self, client, auth_headers):
        img_id = _make_image(client, auth_headers)
        resp = client.post('/api/annotations/', json={
            'image_id':        img_id,
            'label_name':      'Pulmonary Nodule',
            'annotation_type': 'bounding_box',
            'x_min': 0.1, 'y_min': 0.1,
            'x_max': 0.4, 'y_max': 0.4,
        }, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['annotation']['label_name'] == 'Pulmonary Nodule'

    def test_create_segmentation(self, client, auth_headers):
        img_id = _make_image(client, auth_headers)
        resp = client.post('/api/annotations/', json={
            'image_id':        img_id,
            'label_name':      'Mass Lesion',
            'annotation_type': 'segmentation',
            'segmentation_data': {
                'polygon_points':    [[10, 10], [50, 10], [50, 50], [10, 50]],
                'normalized_points': [[0.1, 0.1], [0.5, 0.1], [0.5, 0.5], [0.1, 0.5]]
            }
        }, headers=auth_headers)
        assert resp.status_code == 201

    def test_create_requires_label(self, client, auth_headers):
        img_id = _make_image(client, auth_headers)
        resp = client.post('/api/annotations/', json={
            'image_id':        img_id,
            'annotation_type': 'bounding_box',
        }, headers=auth_headers)
        assert resp.status_code == 400

    def test_list_annotations(self, client, auth_headers):
        img_id = _make_image(client, auth_headers)
        client.post('/api/annotations/', json={
            'image_id': img_id, 'label_name': 'Test', 'annotation_type': 'bounding_box'
        }, headers=auth_headers)
        resp = client.get(f'/api/annotations/image/{img_id}', headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.get_json()['annotations'], list)

    def test_update_annotation(self, client, auth_headers):
        img_id = _make_image(client, auth_headers)
        create = client.post('/api/annotations/', json={
            'image_id': img_id, 'label_name': 'Old Label',
            'annotation_type': 'bounding_box'
        }, headers=auth_headers).get_json()
        ann_id = create['annotation']['id']

        resp = client.put(f'/api/annotations/{ann_id}', json={
            'label_name': 'New Label', 'is_verified': True
        }, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()['annotation']['label_name'] == 'New Label'
        assert resp.get_json()['annotation']['is_verified'] is True

    def test_delete_annotation(self, client, auth_headers):
        img_id = _make_image(client, auth_headers)
        create = client.post('/api/annotations/', json={
            'image_id': img_id, 'label_name': 'To Delete',
            'annotation_type': 'classification'
        }, headers=auth_headers).get_json()
        ann_id = create['annotation']['id']

        resp = client.delete(f'/api/annotations/{ann_id}', headers=auth_headers)
        assert resp.status_code == 200

    def test_approve_all(self, client, auth_headers):
        img_id = _make_image(client, auth_headers)
        for label in ['Nodule A', 'Nodule B']:
            client.post('/api/annotations/', json={
                'image_id': img_id, 'label_name': label,
                'annotation_type': 'bounding_box'
            }, headers=auth_headers)

        resp = client.post(f'/api/annotations/image/{img_id}/approve',
                           headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()['image_status'] == 'approved'

    def test_export_coco(self, client, auth_headers):
        img_id = _make_image(client, auth_headers)
        client.post('/api/annotations/', json={
            'image_id': img_id, 'label_name': 'ExportTest',
            'annotation_type': 'bounding_box',
            'x_min': 0.1, 'y_min': 0.1, 'x_max': 0.5, 'y_max': 0.5
        }, headers=auth_headers)
        client.post(f'/api/annotations/image/{img_id}/approve',
                    headers=auth_headers)
        resp = client.get(f'/api/annotations/export/{img_id}?format=coco',
                          headers=auth_headers)
        assert resp.status_code == 200

    def test_export_yolo(self, client, auth_headers):
        img_id = _make_image(client, auth_headers)
        client.post('/api/annotations/', json={
            'image_id': img_id, 'label_name': 'YoloTest',
            'annotation_type': 'bounding_box',
            'x_min': 0.1, 'y_min': 0.1, 'x_max': 0.5, 'y_max': 0.5
        }, headers=auth_headers)
        client.post(f'/api/annotations/image/{img_id}/approve',
                    headers=auth_headers)
        resp = client.get(f'/api/annotations/export/{img_id}?format=yolo',
                          headers=auth_headers)
        assert resp.status_code == 200
