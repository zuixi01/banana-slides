#!/usr/bin/env python3
"""Read-only inventory scanner for Deckforge JSON workspaces."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def load_json(path: Path):
    with path.open('r', encoding='utf-8') as handle:
        return json.load(handle)


def discover(source: Path, include_smoke: bool = False):
    candidates = []
    root_projects = source / 'projects.json'
    if root_projects.exists():
        candidates.append(('legacy-root', root_projects, source / 'files.json', source / 'files'))
    workspaces = source / 'workspaces'
    if workspaces.exists():
        for directory in sorted(path for path in workspaces.iterdir() if path.is_dir()):
            projects = directory / 'projects.json'
            if projects.exists():
                candidates.append((directory.name, projects, directory / 'files.json', directory / 'files'))
    if include_smoke:
        smoke_workspaces = source / 'ui-image-smoke' / 'workspaces'
        if smoke_workspaces.exists():
            for directory in sorted(path for path in smoke_workspaces.iterdir() if path.is_dir()):
                projects = directory / 'projects.json'
                if projects.exists():
                    candidates.append((f'smoke-{directory.name}', projects, directory / 'files.json', directory / 'files'))
    return candidates


def inventory(source: Path, include_smoke: bool = False):
    report = {
        'source': str(source.resolve()),
        'read_only': True,
        'workspaces': [],
        'totals': {'workspaces': 0, 'projects': 0, 'slides': 0, 'outline_versions': 0, 'files': 0, 'file_bytes': 0},
        'warnings': [],
    }
    for workspace_id, projects_path, files_path, blob_dir in discover(source, include_smoke):
        try:
            payload = load_json(projects_path)
            decks = payload.get('decks', []) if isinstance(payload, dict) else []
        except Exception as exc:
            report['warnings'].append({'path': str(projects_path), 'error': f'{type(exc).__name__}: {exc}'})
            continue
        files = []
        if files_path.exists():
            try:
                file_payload = load_json(files_path)
                files = file_payload.get('files', []) if isinstance(file_payload, dict) else []
            except Exception as exc:
                report['warnings'].append({'path': str(files_path), 'error': f'{type(exc).__name__}: {exc}'})
        missing_blobs = []
        file_bytes = 0
        for item in files:
            blob = blob_dir / f"{item.get('id')}.blob"
            if blob.exists():
                file_bytes += blob.stat().st_size
            else:
                missing_blobs.append(str(item.get('id')))
        entry = {
            'workspace_id': workspace_id,
            'projects_file': str(projects_path.resolve()),
            'checksum': hashlib.sha256(projects_path.read_bytes()).hexdigest(),
            'projects': len(decks),
            'slides': sum(len(deck.get('slides') or []) for deck in decks if isinstance(deck, dict)),
            'outline_versions': sum(len(deck.get('outlineVersions') or []) for deck in decks if isinstance(deck, dict)),
            'files': len(files),
            'file_bytes': file_bytes,
            'missing_blob_ids': missing_blobs,
        }
        report['workspaces'].append(entry)
        for key in ('projects', 'slides', 'outline_versions', 'files', 'file_bytes'):
            report['totals'][key] += entry[key]
    report['totals']['workspaces'] = len(report['workspaces'])
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path, help='Deckforge data directory (read-only)')
    parser.add_argument('--report', type=Path, help='Optional JSON report output')
    parser.add_argument('--include-smoke', action='store_true')
    args = parser.parse_args()
    if not args.source.is_dir():
        parser.error(f'source directory does not exist: {args.source}')
    report = inventory(args.source, args.include_smoke)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered + '\n', encoding='utf-8')
    print(rendered)


if __name__ == '__main__':
    main()
