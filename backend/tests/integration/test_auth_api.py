from fastapi.testclient import TestClient
import pytest

from app.core.config import reset_settings_cache
from app.db.base import Base
from app.db.session import reset_db_caches
from app.main import create_app


def _configure_production_env(monkeypatch, tmp_path, **overrides) -> None:
    values = {
        'APP_ENV': 'production',
        'DATABASE_URL': f"sqlite:///{tmp_path / 'prod.db'}",
        'NEWSLETTER_IMPORT_ROOT_CONTAINER': str(tmp_path / 'import_root'),
        'STORAGE_ROOT': str(tmp_path / 'storage'),
        'JWT_SECRET_KEY': 'production-secret-key-with-enough-entropy',
        'ADMIN_USERNAME': 'admin',
        'ADMIN_PASSWORD': 'production-admin-password',
        'CORS_ORIGINS': 'https://aeroone.example',
        **overrides,
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    reset_settings_cache()
    reset_db_caches()


def test_login_sets_session_and_csrf_cookie(client) -> None:
    response = client.post('/api/v1/auth/login', json={'username': 'admin', 'password': 'password'})

    assert response.status_code == 200
    assert 'csrf_token' in response.cookies
    set_cookie = response.headers.get('set-cookie', '')
    assert 'httponly' in set_cookie.lower()


def test_admin_route_requires_auth(client) -> None:
    response = client.get('/api/v1/admin/newsletters')
    assert response.status_code == 401


def test_production_rejects_default_auth_secrets(monkeypatch, tmp_path) -> None:
    _configure_production_env(
        monkeypatch,
        tmp_path,
        JWT_SECRET_KEY='change-me',
        ADMIN_PASSWORD='change-me',
    )

    try:
        with pytest.raises(ValueError, match='JWT_SECRET_KEY'):
            create_app()
    finally:
        reset_settings_cache()
        reset_db_caches()


def test_production_login_sets_secure_configured_csrf_cookie(monkeypatch, tmp_path) -> None:
    _configure_production_env(monkeypatch, tmp_path, CSRF_COOKIE_NAME='aeroone_csrf')
    app = create_app()
    Base.metadata.create_all(bind=app.state.db.engine)
    client = TestClient(app, base_url='https://aeroone.example')

    response = client.post('/api/v1/auth/login', json={'username': 'admin', 'password': 'production-admin-password'})

    assert response.status_code == 200
    assert 'aeroone_csrf' in response.cookies
    assert 'csrf_token' not in response.cookies
    set_cookie = response.headers.get('set-cookie', '').lower()
    assert 'secure' in set_cookie

    csrf_token = response.json()['csrf_token']
    category_response = client.post(
        '/api/v1/admin/categories',
        json={'name': '운영'},
        headers={'x-csrf-token': csrf_token},
    )
    assert category_response.status_code == 200
    reset_settings_cache()
    reset_db_caches()
