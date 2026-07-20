"""aero work 개인 할 일 추가."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = '20260720_0035'
down_revision = '20260720_0034'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'aero_work_tasks',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(length=300), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='todo'),
        sa.Column('due_date', sa.Date(), nullable=True),
        sa.Column('tags', sa.Text(), nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('done_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_aero_work_tasks_user_id', 'aero_work_tasks', ['user_id'])
    op.create_index('ix_aero_work_tasks_user_id_status', 'aero_work_tasks', ['user_id', 'status'])


def downgrade() -> None:
    op.drop_index('ix_aero_work_tasks_user_id_status', table_name='aero_work_tasks')
    op.drop_index('ix_aero_work_tasks_user_id', table_name='aero_work_tasks')
    op.drop_table('aero_work_tasks')
