from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class NewsletterReadEvent(Base):
    """뉴스레터 1건을 특정 접속 IP 가 읽은 사실의 집계 행.

    (newsletter_id, client_ip) 1쌍당 1행을 유지하는 upsert 모델이다. 같은 IP 가
    같은 글을 다시 열면 새 행을 만들지 않고 ``last_seen_at`` 을 갱신하며, 마지막
    기록이 디바운스 윈도(30분) 보다 오래됐을 때만 ``read_count`` 를 1 늘린다.
    그래서 read_count 는 "조회수"가 아니라 "해당 IP 의 30분 이상 간격 열람 세션 수"다.

    시각 컬럼은 전적으로 DB 측 ``func.now()`` 로 채운다. SQLite 는 timezone 을
    저장하지 못해 재로딩 시 naive 가 되므로, 애플리케이션 코드에서 tz-aware
    datetime 을 만들어 넣으면 aware/naive 비교 오류가 난다(newsletter_autosync
    선례). 이 모델은 그 함정을 DB-side 기본값으로 회피한다.
    """

    __tablename__ = 'newsletter_read_events'
    __table_args__ = (
        UniqueConstraint('newsletter_id', 'client_ip', name='uq_read_event_newsletter_ip'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    newsletter_id: Mapped[int] = mapped_column(
        ForeignKey('newsletters.id', ondelete='CASCADE'), index=True, nullable=False
    )
    client_ip: Mapped[str] = mapped_column(String(45), index=True, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    read_count: Mapped[int] = mapped_column(
        Integer, server_default=text('1'), default=1, nullable=False
    )
