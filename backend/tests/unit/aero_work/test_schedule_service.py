"""Aero Work 일정 서비스 — CRUD·기간 겹침·소유자 스코프·검증·시각 정규화 단위 검증."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.db.base import Base
from app.modules.aero_work import models as aero_work_models  # noqa: F401  (register tables)
from app.modules.aero_work.schedule_service import ScheduleError, ScheduleService, normalize_dt


@pytest.fixture()
def session() -> Session:
    engine = sa.create_engine('sqlite://')
    Base.metadata.create_all(bind=engine, tables=[Base.metadata.tables['aero_work_events']])
    with Session(engine) as db:
        yield db


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def test_create_scopes_to_owner(session: Session) -> None:
    svc = ScheduleService(session)
    mine = svc.create_event(1, title='회의', starts_at=_dt('2026-07-20T10:00'), ends_at=_dt('2026-07-20T11:00'), all_day=False, location='3층', notes='')
    svc.create_event(2, title='남의 일정', starts_at=_dt('2026-07-20T10:00'), ends_at=None, all_day=False, location='', notes='')
    session.commit()

    assert [event.title for event in svc.list_events(1)] == ['회의']
    assert svc.get_event(1, mine.id) is not None
    assert svc.get_event(2, mine.id) is None  # 소유자 아님 → None


def test_list_range_returns_overlapping(session: Session) -> None:
    svc = ScheduleService(session)
    svc.create_event(1, title='어제', starts_at=_dt('2026-07-18T09:00'), ends_at=_dt('2026-07-18T10:00'), all_day=False, location='', notes='')
    svc.create_event(1, title='자정걸침', starts_at=_dt('2026-07-19T23:00'), ends_at=_dt('2026-07-20T01:00'), all_day=False, location='', notes='')
    svc.create_event(1, title='내일낮', starts_at=_dt('2026-07-20T12:00'), ends_at=None, all_day=False, location='', notes='')
    session.commit()

    events = svc.list_events(1, start=_dt('2026-07-20T00:00'), end=_dt('2026-07-21T00:00'))
    titles = [event.title for event in events]
    assert '자정걸침' in titles
    assert '내일낮' in titles
    assert '어제' not in titles


def test_update_and_delete_respect_owner(session: Session) -> None:
    svc = ScheduleService(session)
    event = svc.create_event(1, title='초안', starts_at=_dt('2026-07-20T10:00'), ends_at=None, all_day=False, location='', notes='')
    session.commit()

    svc.update_event(1, event.id, {'title': '확정', 'location': '대회의실'})
    session.commit()
    refreshed = svc.get_event(1, event.id)
    assert refreshed is not None and refreshed.title == '확정' and refreshed.location == '대회의실'

    assert svc.update_event(2, event.id, {'title': 'x'}) is None  # 남의 것 수정 불가
    assert svc.delete_event(2, event.id) is False
    assert svc.delete_event(1, event.id) is True
    assert svc.get_event(1, event.id) is None


def test_validation_rejects_empty_title_and_reversed_range(session: Session) -> None:
    svc = ScheduleService(session)
    with pytest.raises(ScheduleError):
        svc.create_event(1, title='   ', starts_at=_dt('2026-07-20T10:00'), ends_at=None, all_day=False, location='', notes='')
    with pytest.raises(ScheduleError):
        svc.create_event(1, title='역전', starts_at=_dt('2026-07-20T12:00'), ends_at=_dt('2026-07-20T10:00'), all_day=False, location='', notes='')


def test_normalize_dt_converts_aware_to_naive_utc() -> None:
    kst = datetime(2026, 7, 20, 10, 0, tzinfo=timezone(timedelta(hours=9)))
    normalized = normalize_dt(kst)
    assert normalized is not None
    assert normalized.tzinfo is None
    assert normalized.hour == 1  # 10:00 KST → 01:00 UTC
    assert normalize_dt(None) is None
