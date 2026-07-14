"""관리자 감사 이벤트 replay의 DB idempotency key를 추가한다.

Office JobStore의 durable pending-result receipt를 재생할 때 같은 감사 행을 두 번
기록하지 않도록 nullable unique key를 둔다. NULL은 일반(비-replay) 감사 이벤트에
계속 허용된다.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260713_0015"
down_revision = "20260712_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("admin_audit_events") as batch_op:
        batch_op.add_column(sa.Column("idempotency_key", sa.String(length=64), nullable=True))
        batch_op.create_unique_constraint(
            "uq_admin_audit_events_idempotency_key",
            ["idempotency_key"],
        )


def downgrade() -> None:
    with op.batch_alter_table("admin_audit_events") as batch_op:
        batch_op.drop_constraint("uq_admin_audit_events_idempotency_key", type_="unique")
        batch_op.drop_column("idempotency_key")
