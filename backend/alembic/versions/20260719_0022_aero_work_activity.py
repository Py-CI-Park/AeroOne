"""aero work activity: 실행기록 테이블 신설

Aero Work P4 실행기록 — 사용자가 워크스페이스에서 한 행위(지식 색인/검색, 일정 변경, 문서
생성 등)를 입력·결과 요약과 함께 남긴다. 조회는 소유자 스코프·최신순이라 user_id/created_at
인덱스를 둔다.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260719_0022"
down_revision = "20260719_0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'aero_work_activities',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('kind', sa.String(length=40), nullable=False),
        sa.Column('summary', sa.String(length=400), nullable=False),
        sa.Column('detail', sa.Text(), nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_aero_work_activities_user_id', 'aero_work_activities', ['user_id'])
    op.create_index('ix_aero_work_activities_created_at', 'aero_work_activities', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_aero_work_activities_created_at', table_name='aero_work_activities')
    op.drop_index('ix_aero_work_activities_user_id', table_name='aero_work_activities')
    op.drop_table('aero_work_activities')
