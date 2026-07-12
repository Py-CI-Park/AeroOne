"""add composite indexes for self-activity query performance"""

from __future__ import annotations

from alembic import op

revision = "20260712_0010"
down_revision = "20260710_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_login_events_user_id_created_at",
        "login_events",
        ["user_id", "created_at"],
    )
    op.create_index(
        "ix_ai_request_logs_user_id_created_at",
        "ai_request_logs",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_ai_request_logs_user_id_created_at", table_name="ai_request_logs")
    op.drop_index("ix_login_events_user_id_created_at", table_name="login_events")
