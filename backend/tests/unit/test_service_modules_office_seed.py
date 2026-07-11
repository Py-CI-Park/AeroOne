"""office-tools 대시보드 카드 시드 검증(코드 DEFAULT + 멱등성).

빈 테이블 시드(``_ensure_service_modules``)에 office 3종이 포함되고, visibility='admin',
section='Development' 이며 외부 링크가 아님을 확인한다. 재실행 시 중복이 생기지 않는다.
"""

from __future__ import annotations

from sqlalchemy import func, select

from app.modules.admin.api import _ensure_service_modules
from app.modules.admin.models import ServiceModule

_OFFICE_KEYS = {'office-report', 'office-chart', 'office-diagram'}


def test_office_cards_seeded_with_admin_visibility(app) -> None:
    with app.state.db.session() as session:
        _ensure_service_modules(session)
        rows = session.execute(select(ServiceModule)).scalars().all()
        by_key = {row.key: row for row in rows}

    assert _OFFICE_KEYS.issubset(by_key.keys())
    for key in _OFFICE_KEYS:
        card = by_key[key]
        assert card.visibility == 'admin'
        assert card.section == 'Development'
        assert card.is_external is False
        assert card.is_enabled is True
        assert card.href.startswith('/office-tools/')


def test_ensure_is_idempotent(app) -> None:
    with app.state.db.session() as session:
        _ensure_service_modules(session)
        _ensure_service_modules(session)
        count = session.execute(
            select(func.count(ServiceModule.id)).where(ServiceModule.key == 'office-report')
        ).scalar_one()
    assert count == 1
