from __future__ import annotations

from datetime import UTC, datetime
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, reset_settings_cache
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import reset_db_caches
from app.main import create_app
from app.modules.auth.repositories import UserRepository
from app.modules.newsletter.models.category import Category
from app.modules.newsletter.models.newsletter import AssetType, Newsletter, NewsletterAsset, SourceType
from app.modules.newsletter.models.tag import Tag


def _write_pdf(path: Path) -> None:
    path.write_bytes(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF")


@pytest.fixture()
def test_paths(tmp_path: Path) -> dict[str, Path]:
    import_root = tmp_path / 'import_root'
    storage_root = tmp_path / 'storage'
    import_root.mkdir(parents=True)
    (storage_root / 'markdown' / 'newsletters').mkdir(parents=True)
    (storage_root / 'thumbnails').mkdir(parents=True)
    (storage_root / 'attachments').mkdir(parents=True)
    (import_root / 'newsletter_20260206.html').write_text(
        '<html><head><title>테스트 뉴스레터</title></head><body><script>alert(1)</script><a href="https://example.com">link</a><img src="image.png"/></body></html>',
        encoding='utf-8',
    )
    _write_pdf(import_root / 'Aerospace Daily News_20260206.pdf')
    (import_root / 'Aerospace Daily News_20260206_debug.html').write_text('<html>debug</html>', encoding='utf-8')
    (storage_root / 'markdown' / 'newsletters' / 'sample-welcome.md').write_text('# Welcome\n\nSample markdown body.', encoding='utf-8')
    db_path = tmp_path / 'test.db'
    return {'import_root': import_root, 'storage_root': storage_root, 'db_path': db_path}


@pytest.fixture()
def settings(test_paths: dict[str, Path]) -> Settings:
    return Settings(
        app_env='test',
        database_url=f"sqlite:///{test_paths['db_path']}",
        newsletter_import_root_container=str(test_paths['import_root']),
        storage_root=str(test_paths['storage_root']),
        jwt_secret_key='test-secret',
        admin_username='admin',
        admin_password='password',
        cors_origins='http://localhost:3000',
    )


@pytest.fixture()
def app(settings: Settings):
    settings.ensure_directories()
    os.environ['APP_ENV'] = settings.app_env
    os.environ['DATABASE_URL'] = settings.database_url
    os.environ['NEWSLETTER_IMPORT_ROOT_CONTAINER'] = str(settings.import_root)
    os.environ['STORAGE_ROOT'] = str(settings.managed_storage_root)
    os.environ['JWT_SECRET_KEY'] = settings.jwt_secret_key
    os.environ['ADMIN_USERNAME'] = settings.admin_username
    os.environ['ADMIN_PASSWORD'] = settings.admin_password
    os.environ['CORS_ORIGINS'] = settings.cors_origins
    reset_settings_cache()
    reset_db_caches()
    app = create_app()
    Base.metadata.create_all(bind=app.state.db.engine)
    with app.state.db.session() as session:
        user_repo = UserRepository(session)
        user_repo.create(username='admin', password_hash=hash_password('password'))
        category = Category(name='브리핑', slug='briefing', description='기본 카테고리')
        tag = Tag(name='항공우주', slug='aerospace')
        session.add_all([category, tag])
        session.flush()
        markdown_newsletter = Newsletter(
            title='Markdown Welcome',
            slug='markdown-welcome',
            description='Sample markdown entry',
            summary='Markdown summary',
            source_type=SourceType.MARKDOWN,
            source_identifier='markdown-sample-welcome',
            markdown_file_path='markdown/newsletters/sample-welcome.md',
            published_at=datetime(2026, 3, 27, tzinfo=UTC),
            category=category,
            is_active=True,
        )
        markdown_newsletter.tags.append(tag)
        markdown_newsletter.assets.append(NewsletterAsset(asset_type=AssetType.MARKDOWN, file_path='markdown/newsletters/sample-welcome.md', is_primary=True))
        session.add(markdown_newsletter)
    yield app
    Base.metadata.drop_all(bind=app.state.db.engine)
    reset_settings_cache()
    reset_db_caches()


@pytest.fixture()
def client(app) -> TestClient:
    return TestClient(app)


@pytest.fixture()
def csrf_client(client: TestClient) -> TestClient:
    response = client.post('/api/v1/auth/login', json={'username': 'admin', 'password': 'password'})
    assert response.status_code == 200
    csrf_token = response.json()['csrf_token']
    client.headers.update({'x-csrf-token': csrf_token})
    return client
