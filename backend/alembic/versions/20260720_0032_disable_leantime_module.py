"""Leantime 동거 카드를 폐쇄망 릴리스에서 비활성(삭제)한다

운영자 결정으로 이번 폐쇄망 릴리스에서는 Leantime 동거 기능을 제외한다. 대시보드
service_modules 의 ``leantime`` 카드를 삭제해 어떤 사용자에게도 노출되지 않게 한다
(프런트 ``/leantime`` 라우트·office-tools leantime 컴포넌트·``scripts/leantime`` 은
오프라인 패키지 정책 denylist 로 함께 제외된다).

Leantime 은 흡수 UI 가 아니라 링크+상태확인만 하던 admin 전용 실험 카드였고, 폐쇄망
시작 경로(``setup_offline.bat``/``start_offline.bat``)와 오프라인 빌더에는 결합이 없었다.
백엔드 ``app/modules/leantime`` 라우터는 그대로 두되(카드가 없어 UI 로 도달 불가), 사용자
노출면만 제거한다. 되돌릴 때는 downgrade 가 0011+0014 최종 상태(내부 안내 페이지)로 재삽입한다.

진실 원천 3자리 정합: 본 마이그레이션(삭제) · 프런트 ``page.tsx`` FALLBACK(항목 제거) ·
``home-page.test.tsx``(카드 부재 단언).
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260720_0032"
down_revision = "20260719_0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DELETE FROM service_modules WHERE key = 'leantime'"))


def downgrade() -> None:
    # 0011(삽입)+0014(내부 안내 페이지로 갱신) 이후의 최종 상태로 되돌린다(멱등).
    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            INSERT INTO service_modules
                (key, title, description, href, section, status, badge, sort_order,
                 is_enabled, is_external, visibility)
            SELECT 'leantime', 'Leantime', '프로젝트·업무 관리(동거 앱). 안내·열기 페이지.',
                   '/leantime', 'Development', 'development', 'Active', 140, 1, 0, 'admin'
            WHERE NOT EXISTS (SELECT 1 FROM service_modules WHERE key = 'leantime')
            """
        )
    )
