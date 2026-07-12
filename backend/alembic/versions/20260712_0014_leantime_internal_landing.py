"""Leantime 카드를 외부 링크에서 내부 안내 페이지(/leantime)로 변경

Leantime 은 동거 앱이라 별도 포트(8081)에서 도는데, 설치·기동이 안 된 상태에서 외부
링크(is_external, http://localhost:8081)를 누르면 빈 화면/연결 오류가 났다. 카드를 내부
안내 페이지(/leantime)로 돌려, 무엇을 어떻게 설치·기동하는지 설명하고 '열기' 버튼(현재
접속 호스트 기준 8081)을 제공한다. is_external=0 으로 바꿔 same-tab 내부 이동시킨다.

컬럼값은 코드 DEFAULT_SERVICE_MODULES·프런트 FALLBACK_MODULES 와 3자리 일치.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260712_0014"
down_revision = "20260712_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE service_modules SET href = '/leantime', is_external = 0, badge = 'Active', "
            "description = '프로젝트·업무 관리(동거 앱). 안내·열기 페이지.' WHERE key = 'leantime'"
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE service_modules SET href = 'http://localhost:8081', is_external = 1, badge = 'External', "
            "description = '프로젝트 관리(외부 폐쇄망 앱). 운영자 설치 필요.' WHERE key = 'leantime'"
        )
    )
