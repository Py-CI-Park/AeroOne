"""aero work chat sessions: 업무대화 세션 + 카드 최상단 승격

1. gongmuwon 세션 중심 IA(§4.1) — 업무대화를 세션 단위로 묶는 aero_work_chat_sessions 를
   만들고, chat_messages 에 session_id 를 붙인다(레거시 행은 NULL 허용).
2. 운영자 지시 — Aero Work 가 대시보드의 핵심이므로 Development 섹션 최상단(sort_order 42,
   Office Studio 45 앞)으로 승격한다. 프런트 FALLBACK(page.tsx)과 동기화.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260719_0027"
down_revision = "20260719_0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'aero_work_chat_sessions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=120), nullable=False, server_default='새 세션'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_aero_work_chat_sessions_user_id', 'aero_work_chat_sessions', ['user_id'])
    op.create_index('ix_aero_work_chat_sessions_updated_at', 'aero_work_chat_sessions', ['updated_at'])
    with op.batch_alter_table('aero_work_chat_messages') as batch:
        batch.add_column(sa.Column('session_id', sa.Integer(), nullable=True))
    op.create_index('ix_aero_work_chat_messages_session_id', 'aero_work_chat_messages', ['session_id'])
    op.get_bind().execute(sa.text("UPDATE service_modules SET sort_order = 42 WHERE key = 'aero-work'"))


def downgrade() -> None:
    op.get_bind().execute(sa.text("UPDATE service_modules SET sort_order = 65 WHERE key = 'aero-work'"))
    op.drop_index('ix_aero_work_chat_messages_session_id', table_name='aero_work_chat_messages')
    with op.batch_alter_table('aero_work_chat_messages') as batch:
        batch.drop_column('session_id')
    op.drop_index('ix_aero_work_chat_sessions_updated_at', table_name='aero_work_chat_sessions')
    op.drop_index('ix_aero_work_chat_sessions_user_id', table_name='aero_work_chat_sessions')
    op.drop_table('aero_work_chat_sessions')
