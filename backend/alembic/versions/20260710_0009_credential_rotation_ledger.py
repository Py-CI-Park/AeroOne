"""add credential rotation identity and ledger"""

from __future__ import annotations

from uuid import uuid4

from alembic import op
import sqlalchemy as sa

revision = "20260710_0009"
down_revision = "20260707_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    database_state = op.create_table(
        "credential_rotation_database_state",
        sa.Column("singleton_id", sa.Integer(), nullable=False),
        sa.Column("database_id", sa.String(length=36), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("singleton_id = 1", name="ck_credential_rotation_database_singleton"),
        sa.PrimaryKeyConstraint("singleton_id"),
        sa.UniqueConstraint("database_id"),
    )
    op.bulk_insert(database_state, [{"singleton_id": 1, "database_id": str(uuid4())}])
    _ = op.create_table(
        "credential_rotation_ledger",
        sa.Column("rotation_id", sa.String(length=36), nullable=False),
        sa.Column("database_id", sa.String(length=36), nullable=False),
        sa.Column("material_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("user_set_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("pre_state_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("post_state_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("user_count_before", sa.Integer(), nullable=False),
        sa.Column("user_count_after", sa.Integer(), nullable=False),
        sa.Column("password_count_changed", sa.Integer(), nullable=False),
        sa.Column("session_count_before", sa.Integer(), nullable=False),
        sa.Column("session_count_after", sa.Integer(), nullable=False),
        sa.Column(
            "committed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "user_count_before = user_count_after",
            name="ck_credential_rotation_user_count_preserved",
        ),
        sa.CheckConstraint(
            "user_count_after = password_count_changed",
            name="ck_credential_rotation_password_count",
        ),
        sa.CheckConstraint(
            "session_count_after = 0",
            name="ck_credential_rotation_sessions_cleared",
        ),
        sa.ForeignKeyConstraint(
            ["database_id"],
            ["credential_rotation_database_state.database_id"],
        ),
        sa.PrimaryKeyConstraint("rotation_id"),
        sa.UniqueConstraint(
            "database_id",
            "material_fingerprint",
            name="uq_credential_rotation_database_material",
        ),
    )


def downgrade() -> None:
    op.drop_table("credential_rotation_ledger")
    op.drop_table("credential_rotation_database_state")
