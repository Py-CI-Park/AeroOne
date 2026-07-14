"""오피스 도구 3종 카드를 단일 허브 카드로 통합 (멱등)

보고서/차트/다이어그램을 대시보드 카드 3장으로 두면 진입점이 흩어진다. 운영자 요청에
따라 카드 한 장(``office-tools``, href ``/office-tools``)으로 모으고, 그 안에서 세 도구를
탭으로 전환하는 허브로 재구성한다. 이 마이그레이션은 기존 3행을 제거하고 허브 카드 1행을
멱등(``WHERE NOT EXISTS``) 삽입한다.

컬럼값은 코드 시드(admin/api.py DEFAULT_SERVICE_MODULES)·프런트 fallback
(page.tsx FALLBACK_MODULES)과 반드시 일치시킨다(진실 원천 3자리 일치). downgrade 는
허브 카드를 지우고 0010 이 심었던 3행을 되돌린다.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260712_0012"
down_revision = "20260711_0011"
branch_labels = None
depends_on = None

_HUB = {
    'key': 'office-tools',
    'title': '오피스 도구',
    'description': '보고서·차트·다이어그램을 한 곳에서 (샘플 예제 포함).',
    'href': '/office-tools',
    'sort_order': 110,
}

_INSERT_HUB = sa.text(
    """
    INSERT INTO service_modules
        (key, title, description, href, section, status, badge, sort_order,
         is_enabled, is_external, visibility)
    SELECT :key, :title, :description, :href, 'Development', 'development', 'Active',
           :sort_order, 1, 0, 'admin'
    WHERE NOT EXISTS (SELECT 1 FROM service_modules WHERE key = :key)
    """
)

_OFFICE_KEYS = "('office-report', 'office-chart', 'office-diagram')"

_LEGACY = [
    {'key': 'office-report', 'title': '보고서 스튜디오', 'description': 'Markdown 을 사내 표준 HTML 보고서로 변환.', 'href': '/office-tools/report', 'sort_order': 110},
    {'key': 'office-chart', 'title': '차트 스튜디오', 'description': 'CSV·표 데이터를 ECharts 차트로 시각화.', 'href': '/office-tools/chart', 'sort_order': 120},
    {'key': 'office-diagram', 'title': '다이어그램 스튜디오', 'description': '설명을 Mermaid 다이어그램으로 생성.', 'href': '/office-tools/diagram', 'sort_order': 130},
]

_INSERT_LEGACY = sa.text(
    """
    INSERT INTO service_modules
        (key, title, description, href, section, status, badge, sort_order,
         is_enabled, is_external, visibility)
    SELECT :key, :title, :description, :href, 'Development', 'development', 'Active',
           :sort_order, 1, 0, 'admin'
    WHERE NOT EXISTS (SELECT 1 FROM service_modules WHERE key = :key)
    """
)


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text(f"DELETE FROM service_modules WHERE key IN {_OFFICE_KEYS}"))
    bind.execute(_INSERT_HUB, _HUB)


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DELETE FROM service_modules WHERE key = 'office-tools'"))
    for row in _LEGACY:
        bind.execute(_INSERT_LEGACY, row)
