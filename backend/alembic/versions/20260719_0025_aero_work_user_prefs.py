"""aero work user prefs: 사용자별 LLM 프로필(default/local) 테이블

gongmuwon 환경설정 "LLM 프로필 전환"(§8.2). default=관리자 선택 provider 따름,
local=이 사용자만 로컬 Ollama 강제. 연결 등록의 진실 원천은 관리자 콘솔 유지.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260719_0025"
down_revision = "20260719_0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'aero_work_user_prefs',
        sa.Column('user_id', sa.Integer(), primary_key=True),
        sa.Column('llm_mode', sa.String(length=20), nullable=False, server_default='default'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('aero_work_user_prefs')
