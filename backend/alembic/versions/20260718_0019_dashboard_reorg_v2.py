"""dashboard reorg v2: AeroAI/Notebook -> Development, Office Studio first, Open WebUI -> 'AI'

운영자 요청 반영:
- AeroAI(ai)·Notebook(open-notebook) 을 전용 'AI' 섹션에서 'Development' 섹션으로 되돌린다.
- Office Studio(office-tools) 를 Development 섹션의 맨 앞으로(sort_order 45) 올린다.
- Open WebUI(open-webui) 카드를 'AI' 로 개칭하고, 영문 런처 설명 문구를 제거한다.

진실 원천 3자리(마이그레이션 · 프런트 FALLBACK_MODULES · 회귀 테스트)를 함께 맞춘다.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260718_0019"
down_revision = "20260714_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    # AeroAI·Notebook 을 개발중(Development) 섹션으로 이동한다(전용 AI 섹션에서 빠짐).
    bind.execute(sa.text("UPDATE service_modules SET section = 'Development' WHERE key = 'ai'"))
    bind.execute(sa.text("UPDATE service_modules SET section = 'Development' WHERE key = 'open-notebook'"))
    # Office Studio 를 Development 섹션의 맨 앞으로 올린다(Viewer sort_order 50 보다 앞).
    bind.execute(sa.text("UPDATE service_modules SET sort_order = 45 WHERE key = 'office-tools'"))
    # Open WebUI 카드를 'AI' 로 개칭하고 영문 런처 문구를 제거한다.
    bind.execute(
        sa.text(
            "UPDATE service_modules SET title = 'AI', description = '' WHERE key = 'open-webui'"
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("UPDATE service_modules SET section = 'AI' WHERE key = 'ai'"))
    bind.execute(sa.text("UPDATE service_modules SET section = 'AI' WHERE key = 'open-notebook'"))
    bind.execute(sa.text("UPDATE service_modules SET sort_order = 110 WHERE key = 'office-tools'"))
    bind.execute(
        sa.text(
            "UPDATE service_modules SET title = 'Open WebUI', "
            "description = 'Same-origin AI chat console launcher (browser host port 8080).' "
            "WHERE key = 'open-webui'"
        )
    )
