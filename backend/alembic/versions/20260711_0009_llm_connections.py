"""llm connections registry"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260711_0009"
down_revision = "20260707_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'llm_connections',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('base_url', sa.String(length=500), nullable=False),
        sa.Column('api_key_encrypted', sa.Text(), nullable=False, server_default=''),
        sa.Column('default_model', sa.String(length=160), nullable=True),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('verify_tls', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('llm_connections')
