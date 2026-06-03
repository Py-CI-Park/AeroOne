from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.modules.newsletter.models.newsletter import Newsletter
from app.modules.read_tracking.repositories.read_event_repository import ReadEventRepository


def _newsletter_id(session) -> int:
    return session.execute(select(Newsletter.id)).scalars().first()


def test_first_read_inserts_count_one(app) -> None:
    with app.state.db.session() as session:
        nid = _newsletter_id(session)
        row = ReadEventRepository(session).record_read(nid, '192.168.1.50')
        assert row.read_count == 1
        assert row.client_ip == '192.168.1.50'


def test_same_ip_within_window_does_not_increment(app) -> None:
    with app.state.db.session() as session:
        nid = _newsletter_id(session)
        repo = ReadEventRepository(session)
        repo.record_read(nid, '192.168.1.50')
        row = repo.record_read(nid, '192.168.1.50')
        assert row.read_count == 1  # 30분 이내 재방문은 read_count 불변


def test_same_ip_after_window_increments(app) -> None:
    with app.state.db.session() as session:
        nid = _newsletter_id(session)
        repo = ReadEventRepository(session)
        row = repo.record_read(nid, '192.168.1.50')
        # 마지막 기록을 디바운스 윈도(30분) 밖으로 강제(naive UTC).
        row.last_seen_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=31)
        session.flush()
        updated = repo.record_read(nid, '192.168.1.50')
        assert updated.read_count == 2


def test_distinct_ips_create_distinct_rows(app) -> None:
    with app.state.db.session() as session:
        nid = _newsletter_id(session)
        repo = ReadEventRepository(session)
        repo.record_read(nid, '192.168.1.50')
        repo.record_read(nid, '192.168.1.51')
        rows = repo.list_events(newsletter_id=nid)
        assert len(rows) == 2
        assert {row.client_ip for row in rows} == {'192.168.1.50', '192.168.1.51'}


def test_summarize_by_newsletter(app) -> None:
    with app.state.db.session() as session:
        nid = _newsletter_id(session)
        repo = ReadEventRepository(session)
        repo.record_read(nid, '10.0.0.1')
        repo.record_read(nid, '10.0.0.2')
        summary = repo.summarize_by_newsletter()
        assert summary
        nid0, total, ips = summary[0]
        assert nid0 == nid
        assert total == 2
        assert ips == 2


def test_purge_scoped_and_all(app) -> None:
    with app.state.db.session() as session:
        nid = _newsletter_id(session)
        repo = ReadEventRepository(session)
        repo.record_read(nid, '10.0.0.1')
        repo.record_read(nid, '10.0.0.2')
        deleted = repo.purge(newsletter_id=nid)
        assert deleted == 2
        assert repo.list_events() == []
