"""office-tools 대시보드 카드 시드 검증(코드 DEFAULT + 멱등성).

보고서/차트/다이어그램은 대시보드 카드 한 장(``office-tools``)으로 통합돼 허브
페이지(``/office-tools``)로 들어간다. 빈 테이블 시드(``_ensure_service_modules``)에
이 허브 카드가 visibility='admin', section='Development', 내부 링크로 포함되고,
재실행 시 중복이 생기지 않음을 확인한다.
"""

from __future__ import annotations

from sqlalchemy import func, select

from app.modules.admin.api import _ensure_service_modules
from app.modules.admin.models import ServiceModule


def test_office_hub_card_seeded_with_admin_visibility(app) -> None:
    with app.state.db.session() as session:
        _ensure_service_modules(session)
        rows = session.execute(select(ServiceModule)).scalars().all()
        by_key = {row.key: row for row in rows}

    assert 'office-tools' in by_key
    card = by_key['office-tools']
    assert card.visibility == 'admin'
    assert card.section == 'Development'
    assert card.is_external is False
    assert card.is_enabled is True
    assert card.href == '/office-tools'
    # 3종을 하나로 합쳤으므로 개별 카드 키는 더 이상 시드되지 않는다.
    assert 'office-report' not in by_key
    assert 'office-chart' not in by_key
    assert 'office-diagram' not in by_key


def test_ensure_is_idempotent(app) -> None:
    with app.state.db.session() as session:
        _ensure_service_modules(session)
        _ensure_service_modules(session)
        count = session.execute(
            select(func.count(ServiceModule.id)).where(ServiceModule.key == 'office-tools')
        ).scalar_one()
    assert count == 1
