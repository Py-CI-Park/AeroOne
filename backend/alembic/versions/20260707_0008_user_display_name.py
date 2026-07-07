"""add optional user display name"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260707_0008"
down_revision = "20260704_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('display_name', sa.String(length=120), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'display_name')
