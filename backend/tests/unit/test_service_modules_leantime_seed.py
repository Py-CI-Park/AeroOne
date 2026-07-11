"""Leantime 동거 대시보드 카드 시드 검증(코드 DEFAULT + 멱등성).

빈 테이블 시드(``_ensure_service_modules``)에 Leantime 외부 링크 카드가 포함되고,
``is_external=True``·``visibility='admin'``·``section='Development'`` 이며 href 가 외부
포트(8081) 링크임을 확인한다. 재실행 시 중복이 생기지 않는다. 컬럼값은 마이그레이션
(0011)·프런트 fallback(page.tsx)과 일치해야 한다(진실 원천 3자리 일치).
"""

from __future__ import annotations

from sqlalchemy import func, select

from app.modules.admin.api import _ensure_service_modules
from app.modules.admin.models import ServiceModule


def test_leantime_card_seeded_as_external_admin(app) -> None:
    with app.state.db.session() as session:
        _ensure_service_modules(session)
        rows = session.execute(select(ServiceModule)).scalars().all()
        by_key = {row.key: row for row in rows}

    assert 'leantime' in by_key
    card = by_key['leantime']
    assert card.visibility == 'admin'
    assert card.section == 'Development'
    assert card.is_external is True
    assert card.is_enabled is True
    assert card.href == 'http://localhost:8081'
    assert card.sort_order == 140


def test_leantime_seed_is_idempotent(app) -> None:
    with app.state.db.session() as session:
        _ensure_service_modules(session)
        _ensure_service_modules(session)
        count = session.execute(
            select(func.count(ServiceModule.id)).where(ServiceModule.key == 'leantime')
        ).scalar_one()
    assert count == 1
