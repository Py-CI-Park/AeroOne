from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.modules.newsletter.models.newsletter import Newsletter, SourceType
from app.modules.read_tracking.repositories.read_event_repository import ReadEventRepository
from app.modules.read_tracking.services.read_tracking_service import ReadTrackingService


def _make_newsletter(session, *, slug: str) -> Newsletter:
    newsletter = Newsletter(
        title=f'뉴스레터 {slug}',
        slug=slug,
        source_type=SourceType.HTML,
        source_identifier=f'source-{slug}',
        is_active=True,
    )
    session.add(newsletter)
    session.flush()
    return newsletter


def test_recent_for_ip_returns_only_that_ip(app) -> None:
    with app.state.db.session() as session:
        a = _make_newsletter(session, slug='a')
        b = _make_newsletter(session, slug='b')
        repo = ReadEventRepository(session)
        repo.record_read(a.id, '10.0.0.1')
        repo.record_read(b.id, '10.0.0.1')
        repo.record_read(a.id, '10.0.0.2')

        service = ReadTrackingService(session)
        mine = service.recent_for_ip('10.0.0.1', 6)
        other = service.recent_for_ip('10.0.0.2', 6)

        assert {item['slug'] for item in mine} == {'a', 'b'}
        assert [item['slug'] for item in other] == ['a']


def test_recent_for_ip_orders_by_last_seen_desc(app) -> None:
    with app.state.db.session() as session:
        older = _make_newsletter(session, slug='older')
        newer = _make_newsletter(session, slug='newer')
        repo = ReadEventRepository(session)
        older_row = repo.record_read(older.id, '10.0.0.5')
        newer_row = repo.record_read(newer.id, '10.0.0.5')
        # older 를 확실히 더 과거로, newer 를 확실히 더 최근으로 강제한다.
        now = datetime.now(UTC).replace(tzinfo=None)
        older_row.last_seen_at = now - timedelta(hours=2)
        newer_row.last_seen_at = now - timedelta(minutes=1)
        session.flush()

        service = ReadTrackingService(session)
        items = service.recent_for_ip('10.0.0.5', 6)

        assert [item['slug'] for item in items] == ['newer', 'older']


def test_recent_for_ip_clamps_limit(app) -> None:
    with app.state.db.session() as session:
        slugs = ['n1', 'n2', 'n3']
        repo = ReadEventRepository(session)
        for slug in slugs:
            newsletter = _make_newsletter(session, slug=slug)
            repo.record_read(newsletter.id, '10.0.0.9')

        service = ReadTrackingService(session)
        assert len(service.recent_for_ip('10.0.0.9', 0)) == 1  # 0 -> 1 로 클램프
        assert len(service.recent_for_ip('10.0.0.9', 1)) == 1
        assert len(service.recent_for_ip('10.0.0.9', 100)) == 3  # 100 -> 12 로 클램프되지만 실제 3건뿐


def test_recent_for_ip_excludes_deleted_newsletter(app) -> None:
    with app.state.db.session() as session:
        kept = _make_newsletter(session, slug='kept')
        gone = _make_newsletter(session, slug='gone')
        repo = ReadEventRepository(session)
        repo.record_read(kept.id, '10.0.0.7')
        repo.record_read(gone.id, '10.0.0.7')

        # 뉴스레터 실제 삭제(FK CASCADE 로 read_event 도 함께 사라짐) 시나리오.
        session.execute(select(Newsletter).where(Newsletter.id == gone.id))
        session.delete(session.get(Newsletter, gone.id))
        session.flush()

        service = ReadTrackingService(session)
        items = service.recent_for_ip('10.0.0.7', 6)

        assert [item['slug'] for item in items] == ['kept']


def test_recent_for_ip_excludes_soft_deleted_and_unpublished_newsletters(app) -> None:
    # 제품 삭제는 soft-delete(archive, 행 존속)다 — 보관/비활성 뉴스레터는 스트립에 노출 금지.
    with app.state.db.session() as session:
        visible = _make_newsletter(session, slug='recent-visible')
        archived = _make_newsletter(session, slug='recent-archived')
        inactive = _make_newsletter(session, slug='recent-inactive')
        archived.status = 'archived'
        inactive.is_active = False
        session.flush()

        repo = ReadEventRepository(session)
        for target in (visible, archived, inactive):
            repo.record_read(target.id, '10.0.0.9')
        session.flush()

        items = ReadTrackingService(session).recent_for_ip('10.0.0.9', 12)
        assert [item['slug'] for item in items] == ['recent-visible']
