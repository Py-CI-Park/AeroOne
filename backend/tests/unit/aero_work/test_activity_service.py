"""Aero Work 실행기록 서비스 — 기록·최신순 조회·소유자 스코프·limit 단위 검증."""

from __future__ import annotations

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.db.base import Base
from app.modules.aero_work import models as aero_work_models  # noqa: F401  (register tables)
from app.modules.aero_work.activity_service import ActivityService, record_activity


@pytest.fixture()
def session() -> Session:
    engine = sa.create_engine('sqlite://')
    Base.metadata.create_all(bind=engine, tables=[Base.metadata.tables['aero_work_activities']])
    with Session(engine) as db:
        yield db


def test_record_and_list_newest_first(session: Session) -> None:
    record_activity(session, 1, 'knowledge.search', '검색 A')
    record_activity(session, 1, 'schedule.create', '일정 B')
    session.commit()
    items = ActivityService(session).list_activities(1)
    assert [item.summary for item in items] == ['일정 B', '검색 A']  # 최신순


def test_scoped_to_owner(session: Session) -> None:
    record_activity(session, 1, 'schedule.create', '내 것')
    record_activity(session, 2, 'schedule.create', '남의 것')
    session.commit()
    assert [item.summary for item in ActivityService(session).list_activities(1)] == ['내 것']


def test_limit_is_clamped(session: Session) -> None:
    for index in range(10):
        record_activity(session, 1, 'knowledge.search', f'검색 {index}')
    session.commit()
    assert len(ActivityService(session).list_activities(1, limit=3)) == 3


def test_long_fields_are_truncated(session: Session) -> None:
    activity = record_activity(session, 1, 'knowledge.search', 'x' * 500, 'y' * 5000)
    session.commit()
    assert len(activity.summary) == 400
    assert len(activity.detail) == 2000
