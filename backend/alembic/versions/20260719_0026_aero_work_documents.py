"""aero work documents: 문서 최종 저장 승인 상태기계 테이블

gongmuwon 승인형 정책(§11) — 되돌리기 어려운 '최종 저장'은 대기 승인(pending)을 거쳐
approved 가 된 뒤에만 HWPX 로 내려받을 수 있다.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260719_0026"
down_revision = "20260719_0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'aero_work_documents',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=300), nullable=False),
        sa.Column('format', sa.String(length=20), nullable=False, server_default='onepage'),
        sa.Column('body', sa.Text(), nullable=False, server_default=''),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_aero_work_documents_user_id', 'aero_work_documents', ['user_id'])
    op.create_index('ix_aero_work_documents_created_at', 'aero_work_documents', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_aero_work_documents_created_at', table_name='aero_work_documents')
    op.drop_index('ix_aero_work_documents_user_id', table_name='aero_work_documents')
    op.drop_table('aero_work_documents')
