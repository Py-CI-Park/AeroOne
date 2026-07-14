"""dashboard section reorg: move AI apps to 'AI', misc to 'ETC'"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260714_0018"
down_revision = "20260714_0017"
branch_labels = None
depends_on = None

# AeroAI, Open WebUI, Notebook -> dedicated AI section.
_AI_KEYS = ("ai", "open-webui", "open-notebook")
# Ladder game and coming-soon placeholders -> miscellaneous ETC section.
_ETC_KEYS = ("ladder", "announcement", "schedule")


def upgrade() -> None:
    bind = op.get_bind()
    for key in _AI_KEYS:
        bind.execute(
            sa.text("UPDATE service_modules SET section = 'AI' WHERE key = :key"),
            {"key": key},
        )
    for key in _ETC_KEYS:
        bind.execute(
            sa.text("UPDATE service_modules SET section = 'ETC' WHERE key = :key"),
            {"key": key},
        )


def downgrade() -> None:
    bind = op.get_bind()
    for key in _AI_KEYS + _ETC_KEYS:
        bind.execute(
            sa.text("UPDATE service_modules SET section = 'Development' WHERE key = :key"),
            {"key": key},
        )
