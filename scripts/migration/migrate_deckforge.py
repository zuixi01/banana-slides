#!/usr/bin/env python3
"""Idempotently import a copied Deckforge data directory into Banana Slides."""
from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import re
import shutil
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

from scan_deckforge import discover, load_json


NAMESPACE = uuid.UUID('3af6891a-7e02-4c7c-af99-69d34fdcd3de')


def stable_id(kind, source_id):
    return str(uuid.uuid5(NAMESPACE, f'{kind}:{source_id}'))


def canonical_checksum(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def timestamp(value=None):
    if isinstance(value, str) and value.strip():
        return value.replace('Z', '+00:00')
    return datetime.utcnow().isoformat()


def safe_name(value, fallback):
    name = Path(str(value or fallback)).name
    return re.sub(r'[^\w.()\-\u4e00-\u9fff]+', '_', name)[:180] or fallback


def structured_description(slide, outline_slide=None):
    outline_slide = outline_slide or {}
    title = str(slide.get('title') or outline_slide.get('title') or '').strip()
    subtitle = str(slide.get('subtitle') or outline_slide.get('keyMessage') or '').strip()
    body = slide.get('body') or outline_slide.get('keyPoints') or []
    if isinstance(body, str):
        body = [line.strip() for line in body.splitlines() if line.strip()]
    body = [str(item).strip() for item in body if str(item).strip()]
    screen_lines = [item for item in [title, subtitle, *body] if item]
    visual = slide.get('creativeSpec') or outline_slide.get('visualSuggestion') or {}
    visual_instruction = json.dumps(visual, ensure_ascii=False) if isinstance(visual, dict) and visual else str(visual or '')
    layout = slide.get('layout') or visual.get('layoutIntent') if isinstance(visual, dict) else slide.get('layout')
    return {
        'schema_version': 2,
        'text': '--- 页面文字 ---\n' + '\n'.join(screen_lines) + '\n--- 页面文字结束 ---',
        'screenText': {'title': title, 'subtitle': subtitle, 'body': body, 'dataLabels': []},
        'visualAssets': ([{'type': str(visual.get('assetType') or 'diagram') if isinstance(visual, dict) else 'diagram', 'instruction': visual_instruction, 'materialIds': []}] if visual_instruction else []),
        'layout': {'structure': str(layout or ''), 'emphasis': str(outline_slide.get('keyMessage') or title), 'density': 'medium'},
        'speakerNotes': str(slide.get('speakerNotes') or outline_slide.get('speakerNoteHint') or ''),
        'brandConstraints': [],
        'extra_fields': {
            '版式与重点': str(layout or ''),
            '配图与素材': visual_instruction,
            '演讲者备注': str(slide.get('speakerNotes') or outline_slide.get('speakerNoteHint') or ''),
        },
    }


def ledger_row(connection, kind, source_id):
    return connection.execute(
        'SELECT target_id, checksum, status FROM deckforge_migration_records WHERE source_kind=? AND source_id=?',
        (kind, source_id),
    ).fetchone()


def write_ledger(connection, kind, source_id, target_id, checksum, status, details):
    connection.execute(
        '''INSERT INTO deckforge_migration_records
           (id, source_kind, source_id, target_id, checksum, status, details_json, migrated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
        (stable_id('ledger', f'{kind}:{source_id}'), kind, source_id, target_id, checksum,
         status, json.dumps(details, ensure_ascii=False), datetime.utcnow().isoformat()),
    )


def ensure_workspace(connection, source_workspace_id):
    workspace_id = source_workspace_id if re.fullmatch(r'[0-9a-fA-F-]{36}', source_workspace_id) else stable_id('workspace', source_workspace_id)
    owner_id = stable_id('user', f'owner:{source_workspace_id}')
    connection.execute(
        'INSERT OR IGNORE INTO users (id,email,display_name,created_at) VALUES (?,?,?,?)',
        (owner_id, f'deckforge+{owner_id[:12]}@migration.invalid', 'Deckforge migrated owner', datetime.utcnow().isoformat()),
    )
    connection.execute(
        'INSERT OR IGNORE INTO workspaces (id,name,slug,owner_user_id,created_at) VALUES (?,?,?,?,?)',
        (workspace_id, f'Deckforge {source_workspace_id[:8]}', f'deckforge-{workspace_id[:12]}', owner_id, datetime.utcnow().isoformat()),
    )
    connection.execute(
        'INSERT OR IGNORE INTO memberships (id,workspace_id,user_id,role,created_at) VALUES (?,?,?,?,?)',
        (stable_id('membership', f'{workspace_id}:{owner_id}'), workspace_id, owner_id, 'owner', datetime.utcnow().isoformat()),
    )
    return workspace_id


def import_deck(connection, source_workspace_id, workspace_id, deck, report):
    source_deck_id = str(deck.get('id') or canonical_checksum(deck)[:20])
    source_key = f'{source_workspace_id}:{source_deck_id}'
    checksum = canonical_checksum(deck)
    existing = ledger_row(connection, 'project', source_key)
    if existing:
        if existing[1] == checksum:
            report['skipped'] += 1
            return existing[0]
        report['conflicts'].append({'kind': 'project', 'source_id': source_key, 'reason': 'source changed after prior migration'})
        return existing[0]

    project_id = stable_id('project', source_key)
    slides = deck.get('slides') or []
    versions = deck.get('outlineVersions') or []
    active_version = next((v for v in versions if str(v.get('id')) == str(deck.get('activeOutlineVersionId'))), None)
    confirmed_version = next((v for v in versions if str(v.get('id')) == str(deck.get('confirmedOutlineVersionId'))), None)
    fallback_outline_slides = (confirmed_version or active_version or (versions[-1] if versions else {})).get('slides') or []
    page_sources = slides or fallback_outline_slides
    current_version_id = stable_id('outline-version', f"{source_key}:{deck.get('activeOutlineVersionId')}") if deck.get('activeOutlineVersionId') else None
    confirmed_version_id = stable_id('outline-version', f"{source_key}:{deck.get('confirmedOutlineVersionId')}") if deck.get('confirmedOutlineVersionId') else None
    created_at = timestamp(deck.get('createdAt'))
    updated_at = timestamp(deck.get('updatedAt'))
    descriptions_confirmed = updated_at if slides and confirmed_version_id else None
    project_status = 'DESCRIPTIONS_CONFIRMED' if descriptions_confirmed else ('OUTLINE_GENERATED' if page_sources else 'DRAFT')
    connection.execute(
        '''INSERT INTO projects
           (id,workspace_id,project_title,idea_prompt,extra_requirements,creation_type,template_style,
            template_mode,export_extractor_method,export_inpaint_method,export_allow_partial,
            enable_icon_subject_extraction,image_aspect_ratio,status,current_outline_version_id,
            confirmed_outline_version_id,descriptions_confirmed_at,created_at,updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
        (project_id, workspace_id, deck.get('name'), deck.get('prompt'),
         '\n'.join(filter(None, [deck.get('audience'), deck.get('objective')])), 'blank',
         f"Migrated Deckforge theme: {deck.get('theme') or 'default'}", 'single', 'hybrid', 'hybrid',
         0, 1, '16:9', project_status, current_version_id, confirmed_version_id,
         descriptions_confirmed, created_at, updated_at),
    )

    outline_by_id = {
        str(item.get('id')): item for version in versions for item in (version.get('slides') or [])
    }
    actual_page_ids = {}
    for index, item in enumerate(page_sources):
        source_slide_id = str(item.get('id') or index)
        page_id = stable_id('page', f'{source_key}:{source_slide_id}')
        outline_item = outline_by_id.get(str(item.get('outlineSlideId'))) or item
        actual_page_ids[str(item.get('outlineSlideId') or source_slide_id)] = page_id
        title = item.get('title') or outline_item.get('title') or f'Page {index + 1}'
        points = item.get('body') or outline_item.get('keyPoints') or []
        if isinstance(points, str):
            points = [line.strip() for line in points.splitlines() if line.strip()]
        outline_content = {'title': str(title), 'points': [str(point) for point in points]}
        description = structured_description(item, outline_item) if slides else None
        connection.execute(
            '''INSERT INTO pages
               (id,project_id,order_index,part,outline_content,description_content,image_stale,status,created_at,updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)''',
            (page_id, project_id, index, None, json.dumps(outline_content, ensure_ascii=False),
             json.dumps(description, ensure_ascii=False) if description else None, 0,
             'DESCRIPTION_GENERATED' if description else 'DRAFT', created_at, updated_at),
        )
        report['pages'] += 1

    for version in versions:
        source_version_id = str(version.get('id') or version.get('version') or canonical_checksum(version)[:12])
        version_id = stable_id('outline-version', f'{source_key}:{source_version_id}')
        snapshots = []
        for index, item in enumerate(version.get('slides') or []):
            source_slide_id = str(item.get('id') or index)
            page_id = actual_page_ids.get(source_slide_id) or stable_id('page', f'{source_key}:{source_slide_id}')
            snapshots.append({
                'page_id': page_id,
                'order_index': index,
                'part': None,
                'outline_content': {
                    'title': str(item.get('title') or f'Page {index + 1}'),
                    'points': [str(point) for point in (item.get('keyPoints') or [])],
                },
            })
        status = 'confirmed' if source_version_id == str(deck.get('confirmedOutlineVersionId')) else (
            'draft' if source_version_id == str(deck.get('activeOutlineVersionId')) else 'superseded'
        )
        connection.execute(
            '''INSERT INTO outline_versions
               (id,project_id,version_number,parent_version_id,status,instruction,outline_json,diff_json,created_at,confirmed_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)''',
            (version_id, project_id, int(version.get('version') or version.get('revision') or 1), None,
             status, 'Imported from Deckforge', json.dumps(snapshots, ensure_ascii=False),
             json.dumps({'imported': True, 'changed_count': len(snapshots)}, ensure_ascii=False),
             timestamp(version.get('createdAt')), timestamp(version.get('confirmedAt')) if status == 'confirmed' else None),
        )
        report['outline_versions'] += 1

    write_ledger(connection, 'project', source_key, project_id, checksum, 'completed', {
        'pages': len(page_sources), 'outline_versions': len(versions),
    })
    report['projects'] += 1
    return project_id


def import_files(connection, source_workspace_id, workspace_id, files_path, blob_dir, uploads, report):
    if not files_path.exists():
        return
    payload = load_json(files_path)
    for item in payload.get('files', []) if isinstance(payload, dict) else []:
        source_file_id = str(item.get('id') or canonical_checksum(item)[:20])
        source_key = f'{source_workspace_id}:{source_file_id}'
        checksum = canonical_checksum(item)
        existing = ledger_row(connection, 'file', source_key)
        if existing:
            if existing[1] == checksum:
                report['skipped'] += 1
            else:
                report['conflicts'].append({'kind': 'file', 'source_id': source_key, 'reason': 'metadata changed after prior migration'})
            continue
        blob = blob_dir / f'{source_file_id}.blob'
        if not blob.exists():
            report['errors'].append({'kind': 'file', 'source_id': source_key, 'reason': 'blob missing'})
            continue
        filename = safe_name(item.get('originalName'), f'{source_file_id}.bin')
        destination = uploads / 'migrated-deckforge' / workspace_id / source_file_id / filename
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(blob, destination)
        target_id = stable_id('reference-file', source_key)
        relative_path = destination.relative_to(uploads).as_posix()
        suffix = Path(filename).suffix.lower().lstrip('.')
        connection.execute(
            '''INSERT INTO reference_files
               (id,workspace_id,project_id,filename,file_path,file_size,file_type,parse_status,error_message,created_at,updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
            (target_id, workspace_id, None, filename, relative_path, destination.stat().st_size,
             suffix or mimetypes.guess_extension(item.get('mimeType') or '') or 'bin', 'pending',
             'Imported from Deckforge; attach to a project and reparse when needed.',
             timestamp(item.get('createdAt')), timestamp(item.get('createdAt'))),
        )
        write_ledger(connection, 'file', source_key, target_id, checksum, 'completed', {'path': relative_path})
        report['files'] += 1


def migrate(source, database, uploads, include_smoke=False):
    report = {'source': str(source.resolve()), 'database': str(database.resolve()), 'projects': 0, 'pages': 0,
              'outline_versions': 0, 'files': 0, 'skipped': 0, 'conflicts': [], 'errors': [], 'validation': {}}
    connection = sqlite3.connect(database)
    connection.execute('PRAGMA foreign_keys=ON')
    required = {'projects', 'pages', 'outline_versions', 'workspaces', 'deckforge_migration_records'}
    present = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    missing = required - present
    if missing:
        raise RuntimeError(f'target database is not migrated; missing tables: {sorted(missing)}')
    try:
        with connection:
            for source_workspace_id, projects_path, files_path, blob_dir in discover(source, include_smoke):
                workspace_id = ensure_workspace(connection, source_workspace_id)
                payload = load_json(projects_path)
                for deck in payload.get('decks', []) if isinstance(payload, dict) else []:
                    import_deck(connection, source_workspace_id, workspace_id, deck, report)
                import_files(connection, source_workspace_id, workspace_id, files_path, blob_dir, uploads, report)
        report['validation'] = {
            'mapped_projects': connection.execute("SELECT count(*) FROM deckforge_migration_records WHERE source_kind='project' AND status='completed'").fetchone()[0],
            'mapped_files': connection.execute("SELECT count(*) FROM deckforge_migration_records WHERE source_kind='file' AND status='completed'").fetchone()[0],
            'orphan_pages': connection.execute('SELECT count(*) FROM pages p LEFT JOIN projects d ON d.id=p.project_id WHERE d.id IS NULL').fetchone()[0],
            'orphan_outline_versions': connection.execute('SELECT count(*) FROM outline_versions v LEFT JOIN projects d ON d.id=v.project_id WHERE d.id IS NULL').fetchone()[0],
        }
    finally:
        connection.close()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path, help='Copied Deckforge data directory')
    parser.add_argument('--database', required=True, type=Path, help='Banana Slides SQLite database')
    parser.add_argument('--uploads', required=True, type=Path, help='Banana Slides upload directory')
    parser.add_argument('--report', required=True, type=Path)
    parser.add_argument('--confirm-source-is-copy', action='store_true', help='Required safety acknowledgement')
    parser.add_argument('--apply', action='store_true', help='Required to mutate the target database')
    parser.add_argument('--include-smoke', action='store_true')
    args = parser.parse_args()
    if not args.confirm_source_is_copy:
        parser.error('--confirm-source-is-copy is required; never migrate from the live legacy data directory')
    if not args.apply:
        parser.error('--apply is required (use scan_deckforge.py for a read-only preview)')
    if not args.source.is_dir() or not args.database.is_file():
        parser.error('source directory and target database must exist')
    args.uploads.mkdir(parents=True, exist_ok=True)
    report = migrate(args.source, args.database, args.uploads, args.include_smoke)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(rendered + '\n', encoding='utf-8')
    print(rendered)


if __name__ == '__main__':
    main()
