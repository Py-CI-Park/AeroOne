from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.newsletter.models.newsletter import Newsletter
from app.modules.read_tracking.repositories.read_event_repository import ReadEventRepository

def _is_loopback(client_ip: str) -> bool:
    # 관리자 화면의 "loopback 모드" 배너 판정. 실제 loopback 주소만 본다.
    return client_ip == '::1' or client_ip.startswith('127.')


class ReadTrackingService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = ReadEventRepository(db)

    def record(self, newsletter_id: int, client_ip: str) -> None:
        # 존재검증: 무인증 공개 엔드포인트이므로 임의 id 로 행이 생기지 않게 막는다.
        exists = self.db.execute(select(Newsletter.id).where(Newsletter.id == newsletter_id)).first()
        if exists is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Newsletter not found')
        self.repo.record_read(newsletter_id, client_ip)

    def admin_overview(self, newsletter_id: int | None = None, client_ip: str | None = None) -> dict:
        events = self.repo.list_events(newsletter_id=newsletter_id, client_ip=client_ip)
        summaries_raw = self.repo.summarize_by_newsletter()
        ids = [nid for nid, _total, _ips in summaries_raw]
        title_map: dict[int, tuple[str, str]] = {}
        if ids:
            rows = self.db.execute(
                select(Newsletter.id, Newsletter.title, Newsletter.slug).where(Newsletter.id.in_(ids))
            ).all()
            title_map = {int(row[0]): (row[1], row[2]) for row in rows}
        summaries = [
            {
                'newsletter_id': nid,
                'title': title_map.get(nid, (f'#{nid}', ''))[0],
                'slug': title_map.get(nid, ('', ''))[1],
                'total_reads': total,
                'unique_ips': ips,
            }
            for nid, total, ips in summaries_raw
        ]
        loopback_only = bool(events) and all(_is_loopback(event.client_ip) for event in events)
        return {'summaries': summaries, 'events': events, 'loopback_only': loopback_only}

    def purge(self, newsletter_id: int | None = None) -> int:
        return self.repo.purge(newsletter_id)
