"""aero work card + chat log: 대시보드 카드 노출 + 업무대화 영속화

검토(P1)에서 발견된 두 누락을 채운다:
1. service_modules 에 Aero Work 카드가 없어 대시보드에서 발견 불가 → Development 섹션
   sort_order 65(AeroAI 60 뒤)로 멱등 삽입. 컬럼값은 프런트 FALLBACK(page.tsx)과 일치
   (진실 원천 3자리 일치).
2. 업무대화(오케스트레이션) 교환이 클라이언트 상태뿐이라 새로고침 시 소실 →
   aero_work_chat_messages(발화 + 결과 JSON, 소유자 스코프)로 영속화.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260719_0024"
down_revision = "20260719_0023"
branch_labels = None
depends_on = None

_INSERT_CARD = sa.text(
    """
    INSERT INTO service_modules
        (key, title, description, href, section, status, badge, sort_order,
         is_enabled, is_external, visibility)
    SELECT 'aero-work', 'Aero Work',
           '대화 한 줄로 일정·문서(HWPX)·지식 검색을 잇는 업무 워크스페이스.',
           '/aero-work', 'Development', 'development', 'Active', 65, 1, 0, 'admin'
    WHERE NOT EXISTS (SELECT 1 FROM service_modules WHERE key = 'aero-work')
    """
)


def upgrade() -> None:
    op.get_bind().execute(_INSERT_CARD)
    op.create_table(
        'aero_work_chat_messages',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('utterance', sa.Text(), nullable=False),
        sa.Column('results_json', sa.Text(), nullable=False, server_default='[]'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_aero_work_chat_messages_user_id', 'aero_work_chat_messages', ['user_id'])
    op.create_index('ix_aero_work_chat_messages_created_at', 'aero_work_chat_messages', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_aero_work_chat_messages_created_at', table_name='aero_work_chat_messages')
    op.drop_index('ix_aero_work_chat_messages_user_id', table_name='aero_work_chat_messages')
    op.drop_table('aero_work_chat_messages')
    op.get_bind().execute(sa.text("DELETE FROM service_modules WHERE key = 'aero-work'"))
