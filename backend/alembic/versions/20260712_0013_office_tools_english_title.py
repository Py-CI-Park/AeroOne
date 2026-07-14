"""오피스 도구 허브 카드 제목을 영문(Office Studio)으로 변경

허브 카드(0012)를 한국어 '오피스 도구'로 심었으나, 운영자 요청으로 대시보드 표기를
영문 'Office Studio' 로 통일한다. 이미 카드 행이 있는 DB 에서도 반영되도록 title 을
직접 UPDATE 한다(코드 DEFAULT_SERVICE_MODULES·프런트 FALLBACK 도 같은 값으로 맞춤).
downgrade 는 한국어 제목으로 되돌린다.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260712_0013"
down_revision = "20260712_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("UPDATE service_modules SET title = 'Office Studio' WHERE key = 'office-tools'"))


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("UPDATE service_modules SET title = '오피스 도구' WHERE key = 'office-tools'"))
