"""aero work schedule: 개인 일정 이벤트 테이블 신설

Aero Work P4 일정 — 사용자별 캘린더 이벤트. 월/주/일 조회는 starts_at 인덱스 기반 기간
필터로 처리한다. 시각은 서비스에서 naive(UTC 기준)로 정규화해 저장한다.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260719_0021"
down_revision = "20260719_0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'aero_work_events',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=300), nullable=False),
        sa.Column('starts_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ends_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('all_day', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('location', sa.String(length=300), nullable=False, server_default=''),
        sa.Column('notes', sa.Text(), nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_aero_work_events_user_id', 'aero_work_events', ['user_id'])
    op.create_index('ix_aero_work_events_starts_at', 'aero_work_events', ['starts_at'])


def downgrade() -> None:
    op.drop_index('ix_aero_work_events_starts_at', table_name='aero_work_events')
    op.drop_index('ix_aero_work_events_user_id', table_name='aero_work_events')
    op.drop_table('aero_work_events')
