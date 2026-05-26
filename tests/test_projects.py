"""
MediMark AI — Projects Route Tests
"""


class TestProjects:

    def test_create_project(self, client, auth_headers):
        resp = client.post('/api/projects/', json={
            'name':             'Test Project',
            'description':      'A test annotation project',
            'modality':         'CT',
            'target_pathology': 'Lung Nodule',
            'label_classes': [
                {'name': 'Nodule', 'color': '#FF0000', 'icd_code': 'J98.4'}
            ]
        }, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['project']['name'] == 'Test Project'

    def test_create_project_missing_name(self, client, auth_headers):
        resp = client.post('/api/projects/', json={
            'description': 'No name given'
        }, headers=auth_headers)
        assert resp.status_code == 400

    def test_list_projects(self, client, auth_headers):
        client.post('/api/projects/', json={'name': 'List Me'},
                    headers=auth_headers)
        resp = client.get('/api/projects/', headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.get_json()['projects'], list)

    def test_get_project(self, client, auth_headers):
        create = client.post('/api/projects/', json={'name': 'Get Me'},
                             headers=auth_headers).get_json()
        pid  = create['project']['id']
        resp = client.get(f'/api/projects/{pid}', headers=auth_headers)
        assert resp.status_code == 200
        assert 'label_classes' in resp.get_json()

    def test_update_project(self, client, auth_headers):
        create = client.post('/api/projects/', json={'name': 'Update Me'},
                             headers=auth_headers).get_json()
        pid  = create['project']['id']
        resp = client.put(f'/api/projects/{pid}', json={
            'name': 'Updated Name', 'status': 'paused'
        }, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()['project']['name'] == 'Updated Name'

    def test_add_label_class(self, client, auth_headers):
        create = client.post('/api/projects/', json={'name': 'Label Me'},
                             headers=auth_headers).get_json()
        pid  = create['project']['id']
        resp = client.post(f'/api/projects/{pid}/label-classes', json={
            'name': 'Effusion', 'color': '#5352ED', 'icd_code': 'J90'
        }, headers=auth_headers)
        assert resp.status_code == 201
        assert resp.get_json()['label_class']['name'] == 'Effusion'

    def test_project_stats(self, client, auth_headers):
        create = client.post('/api/projects/', json={'name': 'Stats Me'},
                             headers=auth_headers).get_json()
        pid  = create['project']['id']
        resp = client.get(f'/api/projects/{pid}/stats', headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'total_images'    in data
        assert 'completion_pct'  in data
