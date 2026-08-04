"""Versioned outline snapshots layered on Banana Slides' editable pages."""
import json
from datetime import datetime

from models import db, OutlineVersion, Page, Project


def snapshot_pages(project_id):
    pages = Page.query.filter_by(project_id=project_id).order_by(Page.order_index).all()
    return [
        {
            'page_id': page.id,
            'order_index': page.order_index,
            'part': page.part,
            'outline_content': page.get_outline_content() or {},
        }
        for page in pages
    ]


def _title(item):
    return str((item.get('outline_content') or {}).get('title') or '')


def build_diff(previous, current):
    previous_by_id = {item.get('page_id'): item for item in previous if item.get('page_id')}
    current_by_id = {item.get('page_id'): item for item in current if item.get('page_id')}
    added = [item for key, item in current_by_id.items() if key not in previous_by_id]
    removed = [item for key, item in previous_by_id.items() if key not in current_by_id]
    changed = []
    moved = []
    for key in previous_by_id.keys() & current_by_id.keys():
        before, after = previous_by_id[key], current_by_id[key]
        if before.get('outline_content') != after.get('outline_content') or before.get('part') != after.get('part'):
            changed.append({'page_id': key, 'before': _title(before), 'after': _title(after)})
        if before.get('order_index') != after.get('order_index'):
            moved.append({'page_id': key, 'from': before.get('order_index'), 'to': after.get('order_index')})
    return {
        'added': [{'page_id': i.get('page_id'), 'title': _title(i)} for i in added],
        'removed': [{'page_id': i.get('page_id'), 'title': _title(i)} for i in removed],
        'changed': changed,
        'moved': moved,
        'changed_count': len(added) + len(removed) + len(changed) + len(moved),
    }


def latest_version(project_id):
    return OutlineVersion.query.filter_by(project_id=project_id).order_by(OutlineVersion.version_number.desc()).first()


def create_version(project_id, instruction=None, parent=None, force=False):
    project = Project.query.get(project_id)
    if not project:
        raise ValueError('PROJECT_NOT_FOUND')
    current = snapshot_pages(project_id)
    latest = parent or latest_version(project_id)
    if latest and not force and latest.outline() == current:
        project.current_outline_version_id = latest.id
        return latest
    diff = build_diff(latest.outline() if latest else [], current)
    version = OutlineVersion(
        project_id=project_id,
        version_number=(latest.version_number + 1) if latest else 1,
        parent_version_id=latest.id if latest else None,
        status='draft',
        instruction=instruction,
        outline_json=json.dumps(current, ensure_ascii=False),
        diff_json=json.dumps(diff, ensure_ascii=False),
    )
    db.session.add(version)
    db.session.flush()
    project.current_outline_version_id = version.id
    if project.confirmed_outline_version_id and project.confirmed_outline_version_id != version.id:
        project.descriptions_confirmed_at = None
        affected_ids = {
            item.get('page_id')
            for group in ('added', 'changed', 'moved')
            for item in diff.get(group, [])
        }
        for page in project.pages:
            if page.id in affected_ids and (page.description_content or page.generated_image_path):
                page.status = 'STALE'
    return version


def ensure_current_version(project_id):
    return create_version(project_id)


def confirm_version(project_id, version_id):
    project = Project.query.get(project_id)
    version = OutlineVersion.query.filter_by(id=version_id, project_id=project_id).first()
    if not project or not version:
        raise ValueError('OUTLINE_VERSION_NOT_FOUND')
    OutlineVersion.query.filter_by(project_id=project_id, status='confirmed').update({'status': 'superseded'})
    version.status = 'confirmed'
    version.confirmed_at = datetime.utcnow()
    project.current_outline_version_id = version.id
    project.confirmed_outline_version_id = version.id
    return version
