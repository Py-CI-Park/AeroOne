"""aero work task taxonomy: 업무 분류체계 마법사(§6.6) 테이블 신설

Aero Work 분류체계 마법사 ③적용 단계가 쓰는 영속 테이블. 사용자별 업무 분류
(``aero_work_task_categories``)와 분류-색인파일 매핑(``aero_work_task_category_files``)을
둔다. 매핑은 복합 PK(category_id, file_id)로 중복 없이 다대다를 표현하며, 분류·파일 어느
쪽이 삭제돼도 CASCADE 로 매핑이 함께 정리된다.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260719_0029"
down_revision = "20260719_0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'aero_work_task_categories',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'user_id',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=False, server_default=''),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        'ix_aero_work_task_categories_user_id', 'aero_work_task_categories', ['user_id']
    )
    op.create_table(
        'aero_work_task_category_files',
        sa.Column(
            'category_id',
            sa.Integer(),
            sa.ForeignKey('aero_work_task_categories.id', ondelete='CASCADE'),
            primary_key=True,
        ),
        sa.Column(
            'file_id',
            sa.Integer(),
            sa.ForeignKey('aero_work_knowledge_files.id', ondelete='CASCADE'),
            primary_key=True,
        ),
    )


def downgrade() -> None:
    op.drop_table('aero_work_task_category_files')
    op.drop_index('ix_aero_work_task_categories_user_id', table_name='aero_work_task_categories')
    op.drop_table('aero_work_task_categories')
