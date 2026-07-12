"""Leantime 동거 대시보드 카드 시드 검증(코드 DEFAULT + 멱등성).

빈 테이블 시드(``_ensure_service_modules``)에 Leantime 카드가 포함되고, 설치 안 돼도 빈
화면이 안 나오도록 외부 데드링크(:8081) 대신 내부 안내 페이지(/leantime)로 연결하며
``is_external=False``·``visibility='admin'``·``section='Development'`` 임을 확인한다. 재실행
시 중복이 생기지 않는다. 컬럼값은 마이그레이션(0011·0014)·프런트 fallback(page.tsx)과
일치해야 한다(진실 원천 3자리 일치).
"""

from __future__ import annotations

from sqlalchemy import func, select

from app.modules.admin.api import _ensure_service_modules
from app.modules.admin.models import ServiceModule


def test_leantime_card_seeded_as_internal_landing(app) -> None:
    with app.state.db.session() as session:
        _ensure_service_modules(session)
        rows = session.execute(select(ServiceModule)).scalars().all()
        by_key = {row.key: row for row in rows}

    assert 'leantime' in by_key
    card = by_key['leantime']
    assert card.visibility == 'admin'
    assert card.section == 'Development'
    assert card.is_external is False
    assert card.is_enabled is True
    assert card.href == '/leantime'
    assert card.sort_order == 140


def test_leantime_seed_is_idempotent(app) -> None:
    with app.state.db.session() as session:
        _ensure_service_modules(session)
        _ensure_service_modules(session)
        count = session.execute(
            select(func.count(ServiceModule.id)).where(ServiceModule.key == 'leantime')
        ).scalar_one()
    assert count == 1
