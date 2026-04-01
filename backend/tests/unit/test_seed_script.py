from __future__ import annotations

from app.core.config import reset_settings_cache
from app.db.session import Database, reset_db_caches
from app.modules.newsletter.repositories.newsletter_repository import NewsletterRepository
from scripts.seed import main


def test_seed_imports_external_newsletters(test_paths, monkeypatch) -> None:
    monkeypatch.setenv('APP_ENV', 'test')
    monkeypatch.setenv('DATABASE_URL', f"sqlite:///{test_paths['db_path']}")
    monkeypatch.setenv('NEWSLETTER_IMPORT_ROOT_CONTAINER', str(test_paths['import_root']))
    monkeypatch.setenv('STORAGE_ROOT', str(test_paths['storage_root']))
    monkeypatch.setenv('JWT_SECRET_KEY', 'test-secret')
    monkeypatch.setenv('ADMIN_USERNAME', 'admin')
    monkeypatch.setenv('ADMIN_PASSWORD', 'password')
    monkeypatch.setenv('CORS_ORIGINS', 'http://localhost:3000')
    reset_settings_cache()
    reset_db_caches()

    main()

    db = Database(f"sqlite:///{test_paths['db_path']}")
    with db.session() as session:
        repository = NewsletterRepository(session)
        imported = repository.get_by_source_identifier('20260206')
        markdown = repository.get_by_source_identifier('markdown-sample-welcome')

    assert imported is not None
    assert markdown is not None
    assert imported.source_file_path == 'newsletter_20260206.html'
    assert {asset.asset_type.value for asset in imported.assets} == {'html', 'pdf'}
