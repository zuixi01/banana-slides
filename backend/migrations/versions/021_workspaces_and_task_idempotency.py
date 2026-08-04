"""add local-first workspaces and task idempotency

Revision ID: 021_workspaces_tasks
Revises: 020_outline_versions
"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime


revision = '021_workspaces_tasks'
down_revision = '020_outline_versions'
branch_labels = None
depends_on = None

DEFAULT_USER_ID = '00000000-0000-0000-0000-000000000001'
DEFAULT_WORKSPACE_ID = '00000000-0000-0000-0000-000000000002'
DEFAULT_MEMBERSHIP_ID = '00000000-0000-0000-0000-000000000003'


def upgrade():
    users = op.create_table(
        'users',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('email', sa.String(255), nullable=False, unique=True),
        sa.Column('display_name', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    workspaces = op.create_table(
        'workspaces',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('slug', sa.String(100), nullable=False, unique=True),
        sa.Column('owner_user_id', sa.String(36), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['owner_user_id'], ['users.id']),
    )
    memberships = op.create_table(
        'memberships',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('workspace_id', sa.String(36), nullable=False),
        sa.Column('user_id', sa.String(36), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('workspace_id', 'user_id', name='uq_membership_workspace_user'),
        sa.CheckConstraint("role IN ('owner','editor','viewer')", name='ck_membership_role'),
    )
    now = datetime.utcnow()
    op.bulk_insert(users, [{
        'id': DEFAULT_USER_ID, 'email': 'local@banana.invalid',
        'display_name': 'Local User', 'created_at': now,
    }])
    op.bulk_insert(workspaces, [{
        'id': DEFAULT_WORKSPACE_ID, 'name': 'Local Workspace', 'slug': 'local',
        'owner_user_id': DEFAULT_USER_ID, 'created_at': now,
    }])
    op.bulk_insert(memberships, [{
        'id': DEFAULT_MEMBERSHIP_ID, 'workspace_id': DEFAULT_WORKSPACE_ID,
        'user_id': DEFAULT_USER_ID, 'role': 'owner', 'created_at': now,
    }])

    for table_name in ('projects', 'reference_files', 'materials', 'tasks'):
        with op.batch_alter_table(table_name) as batch:
            batch.add_column(sa.Column(
                'workspace_id', sa.String(36), nullable=False,
                server_default=DEFAULT_WORKSPACE_ID,
            ))
            batch.create_foreign_key(
                f'fk_{table_name}_workspace_id', 'workspaces', ['workspace_id'], ['id']
            )
        op.create_index(f'ix_{table_name}_workspace_id', table_name, ['workspace_id'])

    with op.batch_alter_table('tasks') as batch:
        batch.add_column(sa.Column('idempotency_key', sa.String(100), nullable=True))
    op.create_index(
        'uq_tasks_project_type_idempotency', 'tasks',
        ['project_id', 'task_type', 'idempotency_key'], unique=True,
    )


def downgrade():
    op.drop_index('uq_tasks_project_type_idempotency', table_name='tasks')
    with op.batch_alter_table('tasks') as batch:
        batch.drop_column('idempotency_key')
    for table_name in ('tasks', 'materials', 'reference_files', 'projects'):
        op.drop_index(f'ix_{table_name}_workspace_id', table_name=table_name)
        with op.batch_alter_table(table_name) as batch:
            batch.drop_constraint(f'fk_{table_name}_workspace_id', type_='foreignkey')
            batch.drop_column('workspace_id')
    op.drop_table('memberships')
    op.drop_table('workspaces')
    op.drop_table('users')
