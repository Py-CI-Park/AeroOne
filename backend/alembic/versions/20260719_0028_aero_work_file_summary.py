"""aero work file summary: 지식 파일 LLM 요약 컬럼

gongmuwon 위키 문서 카드(§6.5)의 요약을 저장한다(재계산 회피). batch_alter 로 SQLite 안전.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260719_0028"
down_revision = "20260719_0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('aero_work_knowledge_files') as batch:
        batch.add_column(sa.Column('summary', sa.Text(), nullable=False, server_default=''))


def downgrade() -> None:
    with op.batch_alter_table('aero_work_knowledge_files') as batch:
        batch.drop_column('summary')
