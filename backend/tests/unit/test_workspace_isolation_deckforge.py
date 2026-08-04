from datetime import datetime

from models import db, Membership, Page, Project, Task, User


def _create_project(client, headers=None):
    response = client.post(
        '/api/projects',
        json={'creation_type': 'blank'},
        headers=headers or {},
    )
    assert response.status_code == 201
    return response.get_json()['data']['project_id']


def test_projects_are_isolated_between_workspaces(client):
    local_project_id = _create_project(client)
    created = client.post('/api/workspaces', json={
        'name': 'Second Workspace', 'slug': 'second-workspace',
    })
    assert created.status_code == 201
    second_workspace_id = created.get_json()['data']['id']
    second_headers = {'X-Workspace-ID': second_workspace_id}
    second_project_id = _create_project(client, second_headers)

    assert client.get(f'/api/projects/{local_project_id}', headers=second_headers).status_code == 404
    assert client.get(f'/api/projects/{second_project_id}').status_code == 404

    local_list = client.get('/api/projects').get_json()['data']['projects']
    second_list = client.get('/api/projects', headers=second_headers).get_json()['data']['projects']
    assert [item['project_id'] for item in local_list] == [local_project_id]
    assert [item['project_id'] for item in second_list] == [second_project_id]


def test_viewer_cannot_write_project(client):
    project_id = _create_project(client)
    workspace_id = Project.query.get(project_id).workspace_id
    added = client.post(
        f'/api/workspaces/{workspace_id}/members',
        json={'email': 'viewer@example.test', 'display_name': 'Viewer', 'role': 'viewer'},
    )
    assert added.status_code == 200
    user_id = added.get_json()['data']['user_id']

    denied = client.put(
        f'/api/projects/{project_id}',
        json={'project_title': 'should not change'},
        headers={'X-User-ID': user_id, 'X-Workspace-ID': workspace_id},
    )
    assert denied.status_code == 403
    assert denied.get_json()['error']['code'] == 'EDITOR_REQUIRED'


def test_generate_images_replays_existing_idempotent_task(client):
    project_id = _create_project(client)
    project = Project.query.get(project_id)
    project.template_style = 'minimal board presentation'
    project.descriptions_confirmed_at = datetime.utcnow()
    page = Page(project_id=project_id, order_index=0, status='DESCRIPTION_GENERATED')
    page.set_outline_content({'title': 'One conclusion', 'points': ['One proof']})
    page.set_description_content({'text': 'One conclusion'})
    db.session.add(page)
    task = Task(
        project_id=project_id,
        task_type='GENERATE_IMAGES',
        idempotency_key='same-request',
        status='PROCESSING',
    )
    task.set_progress({'total': 1, 'completed': 0, 'failed': 0})
    db.session.add(task)
    db.session.commit()

    replay = client.post(
        f'/api/projects/{project_id}/generate/images',
        json={},
        headers={'Idempotency-Key': 'same-request'},
    )
    assert replay.status_code == 202
    data = replay.get_json()['data']
    assert data['task_id'] == task.id
    assert data['idempotent_replay'] is True
    assert Task.query.filter_by(project_id=project_id).count() == 1
