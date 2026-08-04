"""add Deckforge import idempotency ledger

Revision ID: 023_migration_ledger
Revises: 022_description_gate
"""
from alembic import op
import sqlalchemy as sa


revision = '023_migration_ledger'
down_revision = '022_description_gate'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'deckforge_migration_records',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('source_kind', sa.String(30), nullable=False),
        sa.Column('source_id', sa.String(255), nullable=False),
        sa.Column('target_id', sa.String(36), nullable=True),
        sa.Column('checksum', sa.String(64), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('details_json', sa.Text(), nullable=True),
        sa.Column('migrated_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('source_kind', 'source_id', name='uq_deckforge_migration_source'),
    )


def downgrade():
    op.drop_table('deckforge_migration_records')
