"""aero work knowledge embedding model provenance 추가.

기존 청크는 NULL로 보존한다. 런타임은 NULL을 기존 Ollama 벡터로만 취급해
서로 다른 임베딩 공간을 의미 검색에서 혼합하지 않는다.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = '20260720_0033'
down_revision = '20260720_0032'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('aero_work_knowledge_chunks') as batch_op:
        batch_op.add_column(sa.Column('embed_model', sa.String(length=200), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('aero_work_knowledge_chunks') as batch_op:
        batch_op.drop_column('embed_model')
