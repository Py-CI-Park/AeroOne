from app.modules.newsletter.repositories.newsletter_repository import NewsletterRepository
from app.modules.newsletter.services.newsletter_autosync_service import AutoSyncState, NewsletterAutoSyncService


def test_first_call_syncs_then_unchanged_is_skipped(app, settings) -> None:
    state = AutoSyncState()
    with app.state.db.session() as session:
        service = NewsletterAutoSyncService(session, settings.import_root, state)

        first = service.refresh_if_changed()
        assert first is not None
        assert first.created == 1  # conftest import_root 의 20260206 발행호

        # 폴더가 그대로면 두 번째 호출은 sync 를 돌리지 않는다(시그니처 무변화).
        assert service.refresh_if_changed() is None


def test_new_file_is_detected_without_restart(app, settings) -> None:
    state = AutoSyncState()
    with app.state.db.session() as session:
        service = NewsletterAutoSyncService(session, settings.import_root, state)
        service.refresh_if_changed()  # baseline

        (settings.import_root / 'newsletter_20260207.html').write_text(
            '<html><head><title>새 발행호</title></head><body><p>hi</p></body></html>',
            encoding='utf-8',
        )

        result = service.refresh_if_changed()
        assert result is not None
        assert result.created == 1
        assert NewsletterRepository(session).get_by_source_identifier('20260207') is not None


def test_missing_import_root_does_not_sync(app, tmp_path) -> None:
    state = AutoSyncState()
    with app.state.db.session() as session:
        service = NewsletterAutoSyncService(session, tmp_path / 'missing-root', state)
        assert service.refresh_if_changed() is None
        assert state.signature is None  # 폴더가 없으면 파괴적 sync 없이 시그니처도 그대로
