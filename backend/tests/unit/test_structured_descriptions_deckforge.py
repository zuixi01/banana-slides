from models import db, Page, Project


def _versioned_project():
    project = Project(
        creation_type='blank', status='OUTLINE_GENERATED',
        current_outline_version_id='outline-v1', confirmed_outline_version_id='outline-v1',
    )
    db.session.add(project)
    db.session.flush()
    page = Page(project_id=project.id, order_index=0, status='DRAFT')
    page.set_outline_content({'title': '结论标题', 'points': ['证据']})
    db.session.add(page)
    db.session.commit()
    return project, page


def test_legacy_description_is_normalized_and_confirmed(client):
    project, page = _versioned_project()
    updated = client.put(
        f'/api/projects/{project.id}/pages/{page.id}/description',
        json={'description_content': {
            'text': '--- 页面文字 ---\n结论标题\n证据一\n证据二\n--- 页面文字结束 ---',
            'extra_fields': {
                '配图与素材': '专业流程图',
                '版式与重点': '左文右图，突出结论',
                '演讲者备注': '解释证据来源',
            },
        }},
    )
    assert updated.status_code == 200
    content = updated.get_json()['data']['description_content']
    assert content['schema_version'] == 2
    assert content['screenText']['title'] == '结论标题'
    assert content['screenText']['body'] == ['证据一', '证据二']
    assert content['visualAssets'][0]['instruction'] == '专业流程图'
    assert content['speakerNotes'] == '解释证据来源'

    confirmed = client.post(f'/api/projects/{project.id}/descriptions/confirm')
    assert confirmed.status_code == 200
    assert confirmed.get_json()['data']['page_count'] == 1


def test_description_edit_keeps_rollback_snapshot_and_marks_image_stale(client):
    project, page = _versioned_project()
    page.set_description_content({'text': '第一版'})
    page.generated_image_path = f'{project.id}/pages/v1.png'
    db.session.commit()
    client.post(f'/api/projects/{project.id}/descriptions/confirm')

    edited = client.put(
        f'/api/projects/{project.id}/pages/{page.id}/description',
        json={'description_content': {'text': '第二版'}},
    )
    assert edited.status_code == 200
    assert edited.get_json()['data']['has_description_snapshot'] is True
    assert edited.get_json()['data']['image_stale'] is True
    assert Project.query.get(project.id).descriptions_confirmed_at is None

    restored = client.post(f'/api/projects/{project.id}/pages/{page.id}/description/restore')
    assert restored.status_code == 200
    assert restored.get_json()['data']['description_content']['text'] == '第一版'
