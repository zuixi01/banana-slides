from models import db, Page, Project


def _project_with_pages(db_session):
    project = Project(idea_prompt='版本化大纲测试', creation_type='idea', status='OUTLINE_GENERATED')
    db_session.add(project)
    db_session.flush()
    for index, title in enumerate(('客户痛点决定优先级', '商业模式决定增长上限')):
        page = Page(project_id=project.id, order_index=index, status='DRAFT')
        page.set_outline_content({'title': title, 'points': [f'结论 {index + 1}', '证据']})
        db_session.add(page)
    db_session.commit()
    return project


def test_list_creates_v1_and_confirm_unlocks_description_gate(client):
    project = _project_with_pages(db.session)
    listed = client.get(f'/api/projects/{project.id}/outline-versions')
    assert listed.status_code == 200
    version = listed.get_json()['data']['versions'][0]
    assert version['version'] == 1
    assert version['status'] == 'draft'

    blocked = client.post(f'/api/projects/{project.id}/generate/descriptions', json={})
    assert blocked.status_code == 409
    assert blocked.get_json()['error']['code'] == 'OUTLINE_CONFIRMATION_REQUIRED'

    confirmed = client.post(f"/api/projects/{project.id}/outline-versions/{version['id']}/confirm")
    assert confirmed.status_code == 200
    assert confirmed.get_json()['data']['version']['status'] == 'confirmed'


def test_new_snapshot_keeps_parent_and_diff(db_session):
    from services.outline_version_service import ensure_current_version, create_version

    project = _project_with_pages(db_session)
    first = ensure_current_version(project.id)
    db.session.commit()
    page = Page.query.filter_by(project_id=project.id).order_by(Page.order_index).first()
    page.set_outline_content({'title': '客户损失证明需求紧迫', 'points': ['损失可量化']})
    second = create_version(project.id, instruction='标题改成结论', parent=first, force=True)
    db.session.commit()

    assert second.version_number == 2
    assert second.parent_version_id == first.id
    assert second.diff()['changed_count'] == 1
    assert second.diff()['changed'][0]['before'] == '客户痛点决定优先级'
