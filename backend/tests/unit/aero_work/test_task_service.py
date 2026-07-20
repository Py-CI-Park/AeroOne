"""Aero Work 할 일 서비스의 CRUD·상태·마감·소유권 단위 검증."""
from __future__ import annotations

from datetime import date

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.db.base import Base
from app.modules.aero_work import models as aero_work_models  # noqa: F401
from app.modules.aero_work.task_service import create_task, delete_task, list_tasks, update_task


@pytest.fixture()
def session() -> Session:
    engine = sa.create_engine('sqlite://')
    Base.metadata.create_all(bind=engine, tables=[
        Base.metadata.tables['aero_work_tasks'], Base.metadata.tables['aero_work_activities'],
    ])
    with Session(engine) as db:
        yield db


def test_crud_상태전이와_소유자격리(session: Session) -> None:
    task = create_task(session, 1, '예산 보고서', date(2026, 7, 21), '예산,보고')
    other = create_task(session, 2, '다른 사용자 업무')
    session.commit()

    assert [item.id for item in list_tasks(session, 1)] == [task.id]
    assert update_task(session, 2, task.id, status='done') is None
    assert delete_task(session, 2, task.id) is False

    completed = update_task(session, 1, task.id, status='done')
    assert completed is not None and completed.done_at is not None
    reopened = update_task(session, 1, task.id, status='doing')
    assert reopened is not None and reopened.done_at is None
    assert delete_task(session, 1, task.id) is True
    assert [item.id for item in list_tasks(session, 2)] == [other.id]


def test_overdue는_미완료_마감일만_반환한다(session: Session) -> None:
    late = create_task(session, 1, '지연', date(2026, 7, 19))
    create_task(session, 1, '오늘', date(2026, 7, 20))
    done = create_task(session, 1, '완료', date(2026, 7, 18))
    update_task(session, 1, done.id, status='done')
    session.commit()

    assert [item.id for item in list_tasks(session, 1, overdue=True, now=date(2026, 7, 20))] == [late.id]
