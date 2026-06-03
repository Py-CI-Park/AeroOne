"""newsletter read tracking events"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260603_0002"
down_revision = "20260327_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "newsletter_read_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "newsletter_id",
            sa.Integer(),
            sa.ForeignKey("newsletters.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("client_ip", sa.String(length=45), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("read_count", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("newsletter_id", "client_ip", name="uq_read_event_newsletter_ip"),
    )
    op.create_index("ix_newsletter_read_events_newsletter_id", "newsletter_read_events", ["newsletter_id"])
    op.create_index("ix_newsletter_read_events_client_ip", "newsletter_read_events", ["client_ip"])


def downgrade() -> None:
    op.drop_index("ix_newsletter_read_events_client_ip", table_name="newsletter_read_events")
    op.drop_index("ix_newsletter_read_events_newsletter_id", table_name="newsletter_read_events")
    op.drop_table("newsletter_read_events")
