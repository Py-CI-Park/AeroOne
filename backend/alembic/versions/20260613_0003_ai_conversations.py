"""ai conversations, messages, citations"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260613_0003"
down_revision = "20260603_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_conversations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("owner_session_id", sa.String(length=64), nullable=False),
        sa.Column("owner_ip", sa.String(length=45), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_ai_conversations_owner_session_id", "ai_conversations", ["owner_session_id"])
    op.create_index("ix_ai_conversations_owner_ip", "ai_conversations", ["owner_ip"])

    op.create_table(
        "ai_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.Integer(),
            sa.ForeignKey("ai_conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_ai_messages_conversation_id", "ai_messages", ["conversation_id"])

    op.create_table(
        "ai_message_citations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "message_id",
            sa.Integer(),
            sa.ForeignKey("ai_messages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("collection", sa.String(length=16), nullable=False),
        sa.Column("folder", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("name", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("path", sa.String(length=1000), nullable=False),
        sa.Column("snippet", sa.Text(), nullable=False, server_default=""),
        sa.Column("navigation_url", sa.String(length=1000), nullable=False, server_default=""),
    )
    op.create_index("ix_ai_message_citations_message_id", "ai_message_citations", ["message_id"])


def downgrade() -> None:
    op.drop_index("ix_ai_message_citations_message_id", table_name="ai_message_citations")
    op.drop_table("ai_message_citations")
    op.drop_index("ix_ai_messages_conversation_id", table_name="ai_messages")
    op.drop_table("ai_messages")
    op.drop_index("ix_ai_conversations_owner_ip", table_name="ai_conversations")
    op.drop_index("ix_ai_conversations_owner_session_id", table_name="ai_conversations")
    op.drop_table("ai_conversations")
