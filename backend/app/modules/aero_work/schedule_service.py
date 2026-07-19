"""Aero Work 일정 서비스 — 사용자별 이벤트 CRUD + 기간 조회.

시각은 저장 전 naive(UTC 기준)로 정규화한다(SQLite timezone 미보존 → aware/naive 혼용 비교
오류 방지). 조회는 소유자(user_id) 스코프이며, 기간이 주어지면 겹치는(overlap) 이벤트만 반환한다.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.aero_work.models import AeroWorkEvent


class ScheduleError(RuntimeError):
    """일정 작업 실패(제목 없음·기간 역전 등)."""


def normalize_dt(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


class ScheduleService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_events(
        self, user_id: int, *, start: datetime | None = None, end: datetime | None = None
    ) -> list[AeroWorkEvent]:
        start = normalize_dt(start)
        end = normalize_dt(end)
        stmt = select(AeroWorkEvent).where(AeroWorkEvent.user_id == user_id)
        if end is not None:
            stmt = stmt.where(AeroWorkEvent.starts_at < end)
        if start is not None:
            # 종료가 없으면 시작 기준, 있으면 종료가 start 이후인 것(구간 겹침)
            stmt = stmt.where(func.coalesce(AeroWorkEvent.ends_at, AeroWorkEvent.starts_at) >= start)
        return list(self.db.execute(stmt.order_by(AeroWorkEvent.starts_at)).scalars().all())

    def get_event(self, user_id: int, event_id: int) -> AeroWorkEvent | None:
        event = self.db.get(AeroWorkEvent, event_id)
        if event is None or event.user_id != user_id:
            return None
        return event

    def create_event(
        self,
        user_id: int,
        *,
        title: str,
        starts_at: datetime,
        ends_at: datetime | None,
        all_day: bool,
        location: str,
        notes: str,
    ) -> AeroWorkEvent:
        title = (title or '').strip()
        if not title:
            raise ScheduleError('제목은 비울 수 없습니다.')
        starts_at = normalize_dt(starts_at)
        ends_at = normalize_dt(ends_at)
        if ends_at is not None and starts_at is not None and ends_at < starts_at:
            raise ScheduleError('종료 시각이 시작 시각보다 앞설 수 없습니다.')
        event = AeroWorkEvent(
            user_id=user_id,
            title=title,
            starts_at=starts_at,
            ends_at=ends_at,
            all_day=all_day,
            location=(location or '').strip(),
            notes=(notes or '').strip(),
        )
        self.db.add(event)
        self.db.flush()
        return event

    def update_event(self, user_id: int, event_id: int, fields: dict) -> AeroWorkEvent | None:
        event = self.get_event(user_id, event_id)
        if event is None:
            return None
        if 'title' in fields:
            title = (fields['title'] or '').strip()
            if not title:
                raise ScheduleError('제목은 비울 수 없습니다.')
            event.title = title
        if 'starts_at' in fields:
            event.starts_at = normalize_dt(fields['starts_at'])
        if 'ends_at' in fields:
            event.ends_at = normalize_dt(fields['ends_at'])
        if 'all_day' in fields:
            event.all_day = bool(fields['all_day'])
        if 'location' in fields:
            event.location = (fields['location'] or '').strip()
        if 'notes' in fields:
            event.notes = (fields['notes'] or '').strip()
        if event.ends_at is not None and event.ends_at < event.starts_at:
            raise ScheduleError('종료 시각이 시작 시각보다 앞설 수 없습니다.')
        self.db.flush()
        return event

    def delete_event(self, user_id: int, event_id: int) -> bool:
        event = self.get_event(user_id, event_id)
        if event is None:
            return False
        self.db.delete(event)
        self.db.flush()
        return True
