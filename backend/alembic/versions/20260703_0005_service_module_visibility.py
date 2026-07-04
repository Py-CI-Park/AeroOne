"""service module visibility and english development section"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260703_0005"
down_revision = "20260703_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('service_modules', sa.Column('visibility', sa.String(length=20), nullable=False, server_default='public'))
    bind = op.get_bind()
    # Development/coming-soon modules are operator-only surfaces.
    bind.execute(sa.text("UPDATE service_modules SET visibility = 'admin' WHERE status IN ('development', 'coming_soon')"))
    # Rename the Korean development section label to English.
    bind.execute(sa.text("UPDATE service_modules SET section = 'Development' WHERE section = '개발중'"))


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("UPDATE service_modules SET section = '개발중' WHERE section = 'Development'"))
    op.drop_column('service_modules', 'visibility')
