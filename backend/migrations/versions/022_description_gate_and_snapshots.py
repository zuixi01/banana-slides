"""add structured description gate, rollback snapshot, and stale flag

Revision ID: 022_description_gate
Revises: 021_workspaces_tasks
"""
from alembic import op
import sqlalchemy as sa
import json
import re


revision = '022_description_gate'
down_revision = '021_workspaces_tasks'
branch_labels = None
depends_on = None


def _normalize(data):
    if not isinstance(data, dict) or data.get('schema_version') == 2:
        return data
    result = dict(data)
    text = str(result.get('text') or '')
    text = re.sub(r'^\s*---\s*页面文字\s*---\s*|\s*---\s*页面文字结束\s*---\s*$', '', text, flags=re.M)
    lines = [line.strip() for line in text.splitlines() if line.strip() and line.strip() != '---']
    extra = result.get('extra_fields') if isinstance(result.get('extra_fields'), dict) else {}
    result.update({
        'schema_version': 2,
        'screenText': {
            'title': lines[0] if lines else '',
            'subtitle': lines[1] if len(lines) == 2 else '',
            'body': lines[1:] if len(lines) > 2 else [],
            'dataLabels': [],
        },
        'visualAssets': ([{
            'type': 'diagram',
            'instruction': str(extra.get('配图与素材') or extra.get('视觉元素') or ''),
            'materialIds': [],
        }] if (extra.get('配图与素材') or extra.get('视觉元素')) else []),
        'layout': {
            'structure': str(extra.get('版式与重点') or extra.get('排版布局') or ''),
            'emphasis': str(extra.get('视觉焦点') or ''),
            'density': 'medium',
        },
        'speakerNotes': str(extra.get('演讲者备注') or ''),
        'brandConstraints': [],
    })
    return result


def upgrade():
    with op.batch_alter_table('projects') as batch:
        batch.add_column(sa.Column('descriptions_confirmed_at', sa.DateTime(), nullable=True))
    with op.batch_alter_table('pages') as batch:
        batch.add_column(sa.Column('previous_description_content', sa.Text(), nullable=True))
        batch.add_column(sa.Column('image_stale', sa.Boolean(), nullable=False, server_default=sa.false()))

    bind = op.get_bind()
    rows = bind.execute(sa.text('SELECT id, description_content FROM pages WHERE description_content IS NOT NULL')).fetchall()
    for page_id, raw in rows:
        try:
            normalized = _normalize(json.loads(raw))
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        bind.execute(
            sa.text('UPDATE pages SET description_content = :content WHERE id = :id'),
            {'content': json.dumps(normalized, ensure_ascii=False), 'id': page_id},
        )


def downgrade():
    with op.batch_alter_table('pages') as batch:
        batch.drop_column('image_stale')
        batch.drop_column('previous_description_content')
    with op.batch_alter_table('projects') as batch:
        batch.drop_column('descriptions_confirmed_at')
