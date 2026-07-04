"""service module required permission gates"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260704_0006"
down_revision = "20260703_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('service_modules', sa.Column('required_permission', sa.String(length=120), nullable=True))
    op.add_column('service_modules', sa.Column('resource_type', sa.String(length=50), nullable=True))
    op.add_column('service_modules', sa.Column('resource_id', sa.String(length=255), nullable=True))
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE service_modules "
            "SET required_permission = 'collections.nsa.read', resource_type = 'collection', resource_id = 'nsa' "
            "WHERE key = 'nsa'"
        )
    )


def downgrade() -> None:
    op.drop_column('service_modules', 'resource_id')
    op.drop_column('service_modules', 'resource_type')
    op.drop_column('service_modules', 'required_permission')
