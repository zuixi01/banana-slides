"""add immutable outline versions

Revision ID: 020_outline_versions
Revises: 78475bbce762
"""
from alembic import op
import sqlalchemy as sa

revision = '020_outline_versions'
down_revision = '78475bbce762'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('projects') as batch:
        batch.add_column(sa.Column('current_outline_version_id', sa.String(length=36), nullable=True))
        batch.add_column(sa.Column('confirmed_outline_version_id', sa.String(length=36), nullable=True))
    op.create_table(
        'outline_versions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('parent_version_id', sa.String(length=36), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('instruction', sa.Text(), nullable=True),
        sa.Column('outline_json', sa.Text(), nullable=False),
        sa.Column('diff_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('confirmed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['parent_version_id'], ['outline_versions.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', 'version_number', name='uq_outline_version_project_number'),
    )
    op.create_index('ix_outline_versions_project_id', 'outline_versions', ['project_id'])


def downgrade():
    op.drop_index('ix_outline_versions_project_id', table_name='outline_versions')
    op.drop_table('outline_versions')
    with op.batch_alter_table('projects') as batch:
        batch.drop_column('confirmed_outline_version_id')
        batch.drop_column('current_outline_version_id')
