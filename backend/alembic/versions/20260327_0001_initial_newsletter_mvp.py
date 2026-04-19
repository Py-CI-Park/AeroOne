"""initial newsletter mvp schema"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260327_0001"
down_revision = None
branch_labels = None
depends_on = None

source_type_enum = sa.Enum("html", "pdf", "markdown", name="sourcetype")
asset_type_enum = sa.Enum("html", "pdf", "markdown", name="assettype")

def upgrade() -> None:
    bind = op.get_bind()
    source_type_enum.create(bind, checkfirst=True)
    asset_type_enum.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=100), nullable=False, unique=True),
        sa.Column("email", sa.String(length=255), nullable=True, unique=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False, server_default="admin"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False, unique=True),
        sa.Column("slug", sa.String(length=160), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "tags",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False, unique=True),
        sa.Column("slug", sa.String(length=160), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "newsletters",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("source_type", source_type_enum, nullable=False),
        sa.Column("source_file_path", sa.String(length=500), nullable=True),
        sa.Column("markdown_file_path", sa.String(length=500), nullable=True),
        sa.Column("thumbnail_path", sa.String(length=500), nullable=True),
        sa.Column("source_identifier", sa.String(length=120), nullable=False, unique=True),
        sa.Column("source_checksum", sa.String(length=128), nullable=True),
        sa.Column("source_mtime", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_newsletters_published_at", "newsletters", ["published_at"])

    op.create_table(
        "newsletter_assets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("newsletter_id", sa.Integer(), sa.ForeignKey("newsletters.id", ondelete="CASCADE"), nullable=False),
        sa.Column("asset_type", asset_type_enum, nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("checksum", sa.String(length=128), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("newsletter_id", "asset_type", name="uq_newsletter_asset_type"),
    )

    op.create_table(
        "newsletter_tags",
        sa.Column("newsletter_id", sa.Integer(), sa.ForeignKey("newsletters.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("tag_id", sa.Integer(), sa.ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
    )

def downgrade() -> None:
    op.drop_table("newsletter_tags")
    op.drop_table("newsletter_assets")
    op.drop_index("ix_newsletters_published_at", table_name="newsletters")
    op.drop_table("newsletters")
    op.drop_table("tags")
    op.drop_table("categories")
    op.drop_table("users")
    bind = op.get_bind()
    asset_type_enum.drop(bind, checkfirst=True)
    source_type_enum.drop(bind, checkfirst=True)
