"""office-tools service_modules seed (보고서/차트/다이어그램 3종, 멱등)

기존 운영 DB 에는 이미 기본 카드 행이 있어 ``_ensure_service_modules``(빈 테이블일 때만
시드)로는 새 카드가 들어가지 않는다. 그래서 여기서 ``WHERE NOT EXISTS`` 로 key 별 멱등
삽입한다. 컬럼값은 코드 시드(admin/api.py DEFAULT_SERVICE_MODULES)·프런트 fallback
(page.tsx FALLBACK_MODULES)과 반드시 일치시킨다(진실 원천 3자리 일치).

Leantime(is_external) 카드는 산출물 C(동거 통합) 단계에서 별도로 시드한다 — 이 스코프 밖.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260711_0010"
down_revision = "20260711_0009"
branch_labels = None
depends_on = None

_OFFICE_MODULES = [
    {
        'key': 'office-report',
        'title': '보고서 스튜디오',
        'description': 'Markdown 을 사내 표준 HTML 보고서로 변환.',
        'href': '/office-tools/report',
        'sort_order': 110,
    },
    {
        'key': 'office-chart',
        'title': '차트 스튜디오',
        'description': 'CSV·표 데이터를 ECharts 차트로 시각화.',
        'href': '/office-tools/chart',
        'sort_order': 120,
    },
    {
        'key': 'office-diagram',
        'title': '다이어그램 스튜디오',
        'description': '설명을 Mermaid 다이어그램으로 생성.',
        'href': '/office-tools/diagram',
        'sort_order': 130,
    },
]

_INSERT = sa.text(
    """
    INSERT INTO service_modules
        (key, title, description, href, section, status, badge, sort_order,
         is_enabled, is_external, visibility)
    SELECT :key, :title, :description, :href, 'Development', 'development', 'Active',
           :sort_order, :is_enabled, :is_external, 'admin'
    WHERE NOT EXISTS (SELECT 1 FROM service_modules WHERE key = :key)
    """
)


def upgrade() -> None:
    bind = op.get_bind()
    for row in _OFFICE_MODULES:
        bind.execute(_INSERT, {**row, 'is_enabled': True, 'is_external': False})


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text("DELETE FROM service_modules WHERE key IN ('office-report', 'office-chart', 'office-diagram')")
    )
