from __future__ import annotations
import asyncio
import json

from datetime import UTC, datetime
import os
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings, reset_settings_cache
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import reset_db_caches
from app.main import create_app
from app.modules.auth.repositories import UserRepository
from app.modules.office_tools.upload_limits import (
    OfficeMultipartIngressLimitMiddleware,
    OfficeMultipartLimits,
)
from app.modules.newsletter.models.category import Category
from app.modules.newsletter.models.newsletter import AssetType, Newsletter, NewsletterAsset, SourceType
from app.modules.newsletter.models.tag import Tag


class OfficeIngressHarness:
    @staticmethod
    def multipart_body(
        parts: list[tuple[bytes, bytes]],
        *,
        boundary: bytes,
        content_type: bytes,
    ) -> bytes:
        body = bytearray()
        for content_disposition, payload in parts:
            body.extend(b'--' + boundary + b'\r\n')
            body.extend(content_disposition + b'\r\nContent-Type: ' + content_type + b'\r\n\r\n')
            body.extend(payload)
            body.extend(b'\r\n')
        body.extend(b'--' + boundary + b'--\r\n')
        return bytes(body)

    @staticmethod
    def set_limits(app: FastAPI, limits_by_path: dict[str, OfficeMultipartLimits]) -> None:
        assert app.middleware_stack is None
        for middleware in app.user_middleware:
            if middleware.cls is OfficeMultipartIngressLimitMiddleware:
                middleware.kwargs['limits_by_path'] = limits_by_path
                return
        raise AssertionError('Office ingress middleware is not installed')

    @staticmethod
    def request(
        app: FastAPI,
        *,
        path: str,
        headers: list[tuple[bytes, bytes]],
        receive_messages: list[dict[str, object]],
    ) -> tuple[int, dict[str, object]]:
        sent: list[dict[str, object]] = []

        async def receive() -> dict[str, object]:
            if not receive_messages:
                raise AssertionError('application attempted to read beyond supplied ASGI messages')
            return receive_messages.pop(0)

        async def send(message: dict[str, object]) -> None:
            sent.append(message)

        asyncio.run(
            app(
                {
                    'type': 'http',
                    'asgi': {'version': '3.0'},
                    'http_version': '1.1',
                    'method': 'POST',
                    'scheme': 'http',
                    'path': path,
                    'raw_path': path.encode('ascii'),
                    'query_string': b'',
                    'headers': headers,
                    'client': ('testclient', 50000),
                    'server': ('testserver', 80),
                },
                receive,
                send,
            )
        )
        response_start = next(
            message for message in sent if message['type'] == 'http.response.start'
        )
        status_code = response_start.get('status')
        assert isinstance(status_code, int)
        response_body = b''.join(
            body
            for message in sent
            if message['type'] == 'http.response.body'
            if isinstance(body := message.get('body', b''), bytes)
        )
        decoded_body = json.loads(response_body)
        assert isinstance(decoded_body, dict)
        return status_code, decoded_body


@pytest.fixture()
def office_ingress_harness() -> OfficeIngressHarness:
    return OfficeIngressHarness()

def _write_pdf(path: Path) -> None:
    path.write_bytes(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF")


@pytest.fixture()
def test_paths(tmp_path: Path) -> dict[str, Path]:
    import_root = tmp_path / 'import_root'
    storage_root = tmp_path / 'storage'
    civil_aircraft_root = tmp_path / 'civil_aircraft'
    document_root = tmp_path / 'document'
    nsa_root = tmp_path / 'nsa'
    import_root.mkdir(parents=True)
    civil_aircraft_root.mkdir(parents=True)
    document_root.mkdir(parents=True)
    nsa_root.mkdir(parents=True)
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
    return {'import_root': import_root, 'storage_root': storage_root, 'civil_aircraft_root': civil_aircraft_root, 'document_root': document_root, 'nsa_root': nsa_root, 'db_path': db_path}


@pytest.fixture()
def settings(test_paths: dict[str, Path]) -> Settings:
    return Settings(
        app_env='test',
        database_url=f"sqlite:///{test_paths['db_path']}",
        newsletter_import_root_container=str(test_paths['import_root']),
        civil_aircraft_root=str(test_paths['civil_aircraft_root']),
        document_root=str(test_paths['document_root']),
        nsa_root=str(test_paths['nsa_root']),
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
    os.environ['CIVIL_AIRCRAFT_ROOT'] = str(settings.civil_aircraft_root_path)
    os.environ['DOCUMENT_ROOT'] = str(settings.document_root_path)
    os.environ['NSA_ROOT'] = str(settings.nsa_root_path)
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
