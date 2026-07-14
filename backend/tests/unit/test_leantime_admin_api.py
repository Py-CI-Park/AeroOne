from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import hash_password
from app.modules.admin.models import AdminAuditEvent
from app.modules.auth.repositories import UserRepository
from app.modules.leantime.admin_api import router as leantime_admin_router
from app.modules.leantime.rpc_client import LeantimeAuthError, LeantimeRpcClient, LeantimeUnavailable

_SECRET_VALUE = 'lt-supersecret-plaintext-01234'
_VALID_PAYLOAD = {
    'name': '사내 Leantime',
    'base_url': 'https://leantime.intra',
    'api_key': _SECRET_VALUE,
}


def _ensure_router(app) -> None:
    # main.py 는 이 슬라이스에서 라우터를 include 하지 않는다(리더가 배선) — 테스트는 직접 붙인다.
    prefix = '/api/v1/admin'
    already_mounted = any(
        getattr(route, 'path', '') == f'{prefix}/leantime-connections' for route in app.routes
    )
    if not already_mounted:
        app.include_router(leantime_admin_router, prefix=prefix)


@pytest.fixture()
def client(app) -> TestClient:
    _ensure_router(app)
    return TestClient(app)


@pytest.fixture()
def csrf_client(client: TestClient) -> TestClient:
    response = client.post('/api/v1/auth/login', json={'username': 'admin', 'password': 'password'})
    assert response.status_code == 200
    csrf_token = response.json()['csrf_token']
    client.headers.update({'x-csrf-token': csrf_token})
    return client


def _create_plain_user(app) -> None:
    with app.state.db.session() as session:
        UserRepository(session).create(username='plain', password_hash=hash_password('password123'), role='user')


def test_read_permission_required(app, client: TestClient) -> None:
    _create_plain_user(app)
    login = client.post('/api/v1/auth/login', json={'username': 'plain', 'password': 'password123'})
    assert login.status_code == 200
    resp = client.get('/api/v1/admin/leantime-connections')
    assert resp.status_code == 403


def test_manage_permission_required(app, client: TestClient) -> None:
    _create_plain_user(app)
    login = client.post('/api/v1/auth/login', json={'username': 'plain', 'password': 'password123'})
    assert login.status_code == 200
    csrf = login.json()['csrf_token']
    resp = client.post('/api/v1/admin/leantime-connections', json=_VALID_PAYLOAD, headers={'x-csrf-token': csrf})
    assert resp.status_code == 403


def test_csrf_required(client: TestClient) -> None:
    login = client.post('/api/v1/auth/login', json={'username': 'admin', 'password': 'password'})
    assert login.status_code == 200
    resp = client.post('/api/v1/admin/leantime-connections', json=_VALID_PAYLOAD)
    assert resp.status_code == 403


def test_create_response_masks_key_and_hides_plaintext(csrf_client: TestClient) -> None:
    resp = csrf_client.post('/api/v1/admin/leantime-connections', json=_VALID_PAYLOAD)
    assert resp.status_code == 201
    body = resp.json()
    assert 'api_key' not in body
    assert body['api_key_masked'] == 'lt-...1234'
    assert _SECRET_VALUE not in resp.text


def test_list_masks_key(csrf_client: TestClient) -> None:
    csrf_client.post('/api/v1/admin/leantime-connections', json=_VALID_PAYLOAD)
    resp = csrf_client.get('/api/v1/admin/leantime-connections')
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]['api_key_masked'] == 'lt-...1234'
    assert _SECRET_VALUE not in resp.text


def test_get_one_and_404(csrf_client: TestClient) -> None:
    created = csrf_client.post('/api/v1/admin/leantime-connections', json=_VALID_PAYLOAD).json()
    resp = csrf_client.get(f"/api/v1/admin/leantime-connections/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()['api_key_masked'] == 'lt-...1234'

    missing = csrf_client.get('/api/v1/admin/leantime-connections/999999')
    assert missing.status_code == 404


def test_update_via_api(csrf_client: TestClient) -> None:
    created = csrf_client.post('/api/v1/admin/leantime-connections', json=_VALID_PAYLOAD).json()
    resp = csrf_client.patch(
        f"/api/v1/admin/leantime-connections/{created['id']}",
        json={'name': '변경된 이름'},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body['name'] == '변경된 이름'
    assert body['api_key_masked'] == 'lt-...1234'
    assert _SECRET_VALUE not in resp.text


def test_update_missing_404(csrf_client: TestClient) -> None:
    resp = csrf_client.patch('/api/v1/admin/leantime-connections/999999', json={'name': 'x'})
    assert resp.status_code == 404


def test_delete_via_api(csrf_client: TestClient) -> None:
    created = csrf_client.post('/api/v1/admin/leantime-connections', json=_VALID_PAYLOAD).json()
    resp = csrf_client.delete(f"/api/v1/admin/leantime-connections/{created['id']}")
    assert resp.status_code == 204
    assert csrf_client.get('/api/v1/admin/leantime-connections').json() == []


def test_rotate_key_changes_secret_and_masks(csrf_client: TestClient) -> None:
    created = csrf_client.post('/api/v1/admin/leantime-connections', json=_VALID_PAYLOAD).json()
    new_secret = 'lt-rotated-secret-98765'
    resp = csrf_client.post(
        f"/api/v1/admin/leantime-connections/{created['id']}/rotate-key",
        json={'api_key': new_secret},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body['api_key_masked'] == 'lt-...8765'
    assert body['api_key_masked'] != created['api_key_masked']
    assert new_secret not in resp.text
    assert _SECRET_VALUE not in resp.text


def test_verify_ok(csrf_client: TestClient, monkeypatch) -> None:
    created = csrf_client.post('/api/v1/admin/leantime-connections', json=_VALID_PAYLOAD).json()
    monkeypatch.setattr(LeantimeRpcClient, 'list_projects', lambda self: [])
    resp = csrf_client.post(f"/api/v1/admin/leantime-connections/{created['id']}/verify")
    assert resp.status_code == 200
    body = resp.json()
    assert body['status'] == 'ok'
    assert _SECRET_VALUE not in resp.text


def test_verify_auth_failed(csrf_client: TestClient, monkeypatch) -> None:
    created = csrf_client.post('/api/v1/admin/leantime-connections', json=_VALID_PAYLOAD).json()

    def _boom(self):
        raise LeantimeAuthError('rejected')

    monkeypatch.setattr(LeantimeRpcClient, 'list_projects', _boom)
    resp = csrf_client.post(f"/api/v1/admin/leantime-connections/{created['id']}/verify")
    assert resp.status_code == 200
    body = resp.json()
    assert body['status'] == 'auth_failed'
    assert _SECRET_VALUE not in resp.text
    assert body['detail'] is not None
    assert _SECRET_VALUE not in body['detail']


def test_verify_unreachable(csrf_client: TestClient, monkeypatch) -> None:
    created = csrf_client.post('/api/v1/admin/leantime-connections', json=_VALID_PAYLOAD).json()

    def _boom(self):
        raise LeantimeUnavailable('down')

    monkeypatch.setattr(LeantimeRpcClient, 'list_projects', _boom)
    resp = csrf_client.post(f"/api/v1/admin/leantime-connections/{created['id']}/verify")
    assert resp.status_code == 200
    body = resp.json()
    assert body['status'] == 'unreachable'
    assert _SECRET_VALUE not in resp.text


def test_verify_error_on_undecryptable_key(csrf_client: TestClient, monkeypatch) -> None:
    # 저장 키가 복호화 불가여도 500 이 아니라 status='error' 로 낮춘다.
    from app.modules.leantime.connection_service import LeantimeConnectionService

    created = csrf_client.post('/api/v1/admin/leantime-connections', json=_VALID_PAYLOAD).json()

    def _boom(self, connection):
        raise ValueError('MAC verification failed')

    monkeypatch.setattr(LeantimeConnectionService, 'decrypted_key', _boom)
    resp = csrf_client.post(f"/api/v1/admin/leantime-connections/{created['id']}/verify")
    assert resp.status_code == 200
    body = resp.json()
    assert body['status'] == 'error'
    assert _SECRET_VALUE not in resp.text


def test_audit_recorded_for_mutations_and_verify(app, csrf_client: TestClient, monkeypatch) -> None:
    created = csrf_client.post('/api/v1/admin/leantime-connections', json=_VALID_PAYLOAD).json()
    connection_id = created['id']
    csrf_client.patch(f'/api/v1/admin/leantime-connections/{connection_id}', json={'name': '개정'})
    csrf_client.post(
        f'/api/v1/admin/leantime-connections/{connection_id}/rotate-key',
        json={'api_key': 'lt-another-secret-11111'},
    )
    monkeypatch.setattr(LeantimeRpcClient, 'list_projects', lambda self: [])
    csrf_client.post(f'/api/v1/admin/leantime-connections/{connection_id}/verify')
    csrf_client.delete(f'/api/v1/admin/leantime-connections/{connection_id}')

    with app.state.db.session() as session:
        events = session.execute(
            select(AdminAuditEvent).where(AdminAuditEvent.target_type == 'leantime_connection')
        ).scalars().all()
        actions = {event.action for event in events}
        assert actions == {
            'leantime_connection.create',
            'leantime_connection.update',
            'leantime_connection.rotate_key',
            'leantime_connection.verify',
            'leantime_connection.delete',
        }
        for event in events:
            assert _SECRET_VALUE not in (event.after_json or '')
            assert _SECRET_VALUE not in (event.before_json or '')
            assert _SECRET_VALUE not in (event.metadata_json or '')
