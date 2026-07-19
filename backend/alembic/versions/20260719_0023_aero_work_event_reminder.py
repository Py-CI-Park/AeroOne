"""aero work event reminder: 일정 사전 알림 컬럼 추가

Aero Work F6 일정 사전 알림 — 이벤트에 remind_before_minutes(분 단위, nullable)를 추가한다.
없음/10/30/60/1440(하루) 등 클라이언트가 고른 리드타임을 저장한다. SQLite 안전을 위해
batch_alter_table 로 add/drop 한다.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260719_0023"
down_revision = "20260719_0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('aero_work_events') as batch:
        batch.add_column(sa.Column('remind_before_minutes', sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('aero_work_events') as batch:
        batch.drop_column('remind_before_minutes')
