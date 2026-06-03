from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ReadBeaconResponse(BaseModel):
    recorded: bool


class ReadEventRow(BaseModel):
    newsletter_id: int
    client_ip: str
    read_count: int
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None

    class Config:
        from_attributes = True


class NewsletterReadSummary(BaseModel):
    newsletter_id: int
    title: str
    slug: str
    total_reads: int
    unique_ips: int


class ReadEventsResponse(BaseModel):
    summaries: list[NewsletterReadSummary]
    events: list[ReadEventRow]
    loopback_only: bool


class PurgeResponse(BaseModel):
    deleted: int
