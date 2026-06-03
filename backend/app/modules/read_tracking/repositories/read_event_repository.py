from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.modules.read_tracking.models.read_event import NewsletterReadEvent

# 같은 IP 가 같은 글을 다시 열어도 이 윈도 안에서는 read_count 를 늘리지 않는다.
READ_DEBOUNCE = timedelta(minutes=30)


def _utcnow_naive() -> datetime:
    # SQLite 는 tz 를 저장하지 못해 저장된 last_seen_at 이 naive(UTC) 로 돌아온다.
    # 비교 양변을 naive UTC 로 맞춰 aware/naive 혼합 오류를 피한다.
    return datetime.now(UTC).replace(tzinfo=None)


class ReadEventRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, newsletter_id: int, client_ip: str) -> NewsletterReadEvent | None:
        stmt = select(NewsletterReadEvent).where(
            NewsletterReadEvent.newsletter_id == newsletter_id,
            NewsletterReadEvent.client_ip == client_ip,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def record_read(self, newsletter_id: int, client_ip: str) -> NewsletterReadEvent:
        row = self.get(newsletter_id, client_ip)
        if row is None:
            row = NewsletterReadEvent(newsletter_id=newsletter_id, client_ip=client_ip)
            self.db.add(row)
            self.db.flush()
            return row
        last_seen = row.last_seen_at
        if last_seen is not None and last_seen.tzinfo is not None:
            last_seen = last_seen.replace(tzinfo=None)
        if last_seen is None or (_utcnow_naive() - last_seen) >= READ_DEBOUNCE:
            row.read_count = row.read_count + 1
        # 윈도 안이든 밖이든 최근 열람 시각은 항상 갱신(읽음 recency 추적).
        row.last_seen_at = func.now()
        self.db.flush()
        return row

    def list_events(
        self,
        newsletter_id: int | None = None,
        client_ip: str | None = None,
        limit: int = 500,
        offset: int = 0,
    ) -> list[NewsletterReadEvent]:
        stmt = select(NewsletterReadEvent)
        if newsletter_id is not None:
            stmt = stmt.where(NewsletterReadEvent.newsletter_id == newsletter_id)
        if client_ip is not None:
            stmt = stmt.where(NewsletterReadEvent.client_ip == client_ip)
        stmt = (
            stmt.order_by(
                NewsletterReadEvent.read_count.desc(),
                NewsletterReadEvent.last_seen_at.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.execute(stmt).scalars().all())

    def summarize_by_newsletter(self) -> list[tuple[int, int, int]]:
        """글별 (newsletter_id, 총 read_count, 고유 IP 수)."""
        stmt = (
            select(
                NewsletterReadEvent.newsletter_id,
                func.coalesce(func.sum(NewsletterReadEvent.read_count), 0),
                func.count(func.distinct(NewsletterReadEvent.client_ip)),
            )
            .group_by(NewsletterReadEvent.newsletter_id)
            .order_by(func.sum(NewsletterReadEvent.read_count).desc())
        )
        return [(int(nid), int(total or 0), int(ips or 0)) for nid, total, ips in self.db.execute(stmt).all()]

    def purge(self, newsletter_id: int | None = None) -> int:
        stmt = delete(NewsletterReadEvent)
        if newsletter_id is not None:
            stmt = stmt.where(NewsletterReadEvent.newsletter_id == newsletter_id)
        result = self.db.execute(stmt)
        self.db.flush()
        return int(result.rowcount or 0)
