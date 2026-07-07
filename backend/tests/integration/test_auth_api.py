from fastapi.testclient import TestClient
from sqlalchemy import func, select
from app.core.security import hash_password
from app.modules.admin.models import LoginEvent, ResourceGrant, UserPermission, UserSessionActivity
from app.modules.auth.models import User
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


def test_logout_clears_cookies_records_event_and_removes_session_activity(client, app) -> None:
    login_response = client.post('/api/v1/auth/login', json={'username': 'admin', 'password': 'password'})
    assert login_response.status_code == 200

    assert client.get('/api/v1/auth/me').status_code == 200

    response = client.post('/api/v1/auth/logout')

    assert response.status_code == 200
    assert response.json() == {'status': 'ok'}
    assert 'max-age=0' in response.headers.get('set-cookie', '').lower()
    assert client.get('/api/v1/auth/me').status_code == 401
    with app.state.db.session() as session:
        statuses = session.execute(select(LoginEvent.status).order_by(LoginEvent.id)).scalars().all()
        active_rows = session.scalar(select(func.count(UserSessionActivity.id)))
    assert statuses == ['success', 'logout']
    assert active_rows == 0

    second_login = client.post('/api/v1/auth/login', json={'username': 'admin', 'password': 'password'})
    assert second_login.status_code == 200
    sessions_response = client.get('/api/v1/admin/sessions')
    assert sessions_response.status_code == 200
    assert any(event['status'] == 'logout' for event in sessions_response.json()['recent_login_events'])


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


def test_effective_permissions_requires_auth(client) -> None:
    response = client.get('/api/v1/auth/effective-permissions')

    assert response.status_code == 401


def test_effective_permissions_returns_user_permissions_and_resource_grants(client, app) -> None:
    with app.state.db.session() as session:
        user = User(username='nsa-reader', password_hash=hash_password('password'), role='user', is_active=True)
        session.add(user)
        session.flush()
        session.add(UserPermission(user_id=user.id, permission_key='collections.nsa.read'))
        session.add(
            ResourceGrant(
                subject_type='user',
                subject_id=user.id,
                resource_type='collection',
                resource_id='nsa',
                permission_key='collections.nsa.read',
            )
        )
        session.commit()

    login_response = client.post('/api/v1/auth/login', json={'username': 'nsa-reader', 'password': 'password'})
    assert login_response.status_code == 200

    response = client.get('/api/v1/auth/effective-permissions')

    assert response.status_code == 200
    payload = response.json()
    assert 'collections.nsa.read' in payload['permissions']
    assert {
        'resource_type': 'collection',
        'resource_id': 'nsa',
        'permission_key': 'collections.nsa.read',
    } in payload['resources']
