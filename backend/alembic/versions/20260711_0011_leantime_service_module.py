"""Leantime 동거(co-deploy) 대시보드 카드 시드 (외부 링크, 멱등)

Leantime 은 PHP + MariaDB + IIS 로 구성된 완제품(AGPL)이라 AeroOne 백엔드로 흡수하지
않고 '동거'한다. 대시보드에는 외부 링크 카드(``is_external=True``) 한 장으로만 노출하고,
실제 앱은 운영자가 별도 포트(기본 8081)에 설치·기동한다. 카드 클릭 시 새 탭으로 이동한다.

기존 운영 DB 에는 이미 기본 카드 행이 있어 ``_ensure_service_modules``(빈 테이블일 때만
시드)로는 새 카드가 들어가지 않는다. 그래서 여기서 ``WHERE NOT EXISTS`` 로 key 멱등 삽입한다.
컬럼값은 코드 시드(admin/api.py DEFAULT_SERVICE_MODULES)·프런트 fallback
(page.tsx FALLBACK_MODULES)과 반드시 일치시킨다(진실 원천 3자리 일치).

office-tools 3종 시드(0010)의 뒤에 이어지는 별도 리비전으로, 산출물 C(Leantime 동거)
스코프를 office-tools 스코프와 분리해 추적 가능하게 한다.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260711_0011"
down_revision = "20260711_0010"
branch_labels = None
depends_on = None

_LEANTIME_MODULE = {
    'key': 'leantime',
    'title': 'Leantime',
    'description': '프로젝트 관리(외부 폐쇄망 앱). 운영자 설치 필요.',
    'href': 'http://localhost:8081',
    'sort_order': 140,
}

_INSERT = sa.text(
    """
    INSERT INTO service_modules
        (key, title, description, href, section, status, badge, sort_order,
         is_enabled, is_external, visibility)
    SELECT :key, :title, :description, :href, 'Development', 'development', 'External',
           :sort_order, 1, 1, 'admin'
    WHERE NOT EXISTS (SELECT 1 FROM service_modules WHERE key = :key)
    """
)


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(_INSERT, _LEANTIME_MODULE)


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DELETE FROM service_modules WHERE key = 'leantime'"))
