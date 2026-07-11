from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import hash_password
from app.modules.admin.models import AdminAuditEvent
from app.modules.ai.openai_client import LlmConnectionError, OpenAiCompatibleClient
from app.modules.auth.repositories import UserRepository

_SECRET_VALUE = 'sk-supersecret-plaintext-01234'
_VALID_PAYLOAD = {
    'name': '사내 gpt-oss',
    'base_url': 'https://gpt-oss.intra/v1',
    'api_key': _SECRET_VALUE,
    'default_model': 'gpt-oss-20b',
}


def _create_plain_user(app) -> None:
    with app.state.db.session() as session:
        UserRepository(session).create(username='plain', password_hash=hash_password('password123'), role='user')


def test_manage_permission_required(app) -> None:
    _create_plain_user(app)
    client = TestClient(app)
    login = client.post('/api/v1/auth/login', json={'username': 'plain', 'password': 'password123'})
    assert login.status_code == 200
    csrf = login.json()['csrf_token']
    resp = client.post('/api/v1/admin/llm-connections', json=_VALID_PAYLOAD, headers={'x-csrf-token': csrf})
    assert resp.status_code == 403


def test_csrf_required(app) -> None:
    client = TestClient(app)
    login = client.post('/api/v1/auth/login', json={'username': 'admin', 'password': 'password'})
    assert login.status_code == 200
    # csrf 헤더 없이 변경 시도 → 403.
    resp = client.post('/api/v1/admin/llm-connections', json=_VALID_PAYLOAD)
    assert resp.status_code == 403


def test_create_response_masks_key_and_hides_plaintext(csrf_client: TestClient) -> None:
    resp = csrf_client.post('/api/v1/admin/llm-connections', json=_VALID_PAYLOAD)
    assert resp.status_code == 201
    body = resp.json()
    assert 'api_key' not in body  # 평문 키 필드 자체가 없다.
    assert body['api_key_masked'] == 'sk-...1234'
    assert _SECRET_VALUE not in resp.text


def test_list_masks_key(csrf_client: TestClient) -> None:
    csrf_client.post('/api/v1/admin/llm-connections', json=_VALID_PAYLOAD)
    resp = csrf_client.get('/api/v1/admin/llm-connections')
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]['api_key_masked'] == 'sk-...1234'
    assert _SECRET_VALUE not in resp.text


def test_audit_after_snapshot_has_no_plaintext_key(app, csrf_client: TestClient) -> None:
    resp = csrf_client.post('/api/v1/admin/llm-connections', json=_VALID_PAYLOAD)
    assert resp.status_code == 201
    with app.state.db.session() as session:
        event = session.execute(
            select(AdminAuditEvent).where(AdminAuditEvent.action == 'llm_connection.create')
        ).scalars().first()
    assert event is not None
    assert event.after_json is not None
    assert _SECRET_VALUE not in event.after_json


def test_invalid_base_url_rejected(csrf_client: TestClient) -> None:
    payload = dict(_VALID_PAYLOAD, base_url='ftp://not-allowed/v1')
    resp = csrf_client.post('/api/v1/admin/llm-connections', json=payload)
    assert resp.status_code == 422


def test_verify_success(csrf_client: TestClient, monkeypatch) -> None:
    created = csrf_client.post('/api/v1/admin/llm-connections', json=_VALID_PAYLOAD)
    connection_id = created.json()['id']
    monkeypatch.setattr(OpenAiCompatibleClient, 'list_models', lambda self: ['gpt-oss-20b', 'llama3'])
    resp = csrf_client.post(f'/api/v1/admin/llm-connections/{connection_id}/verify')
    assert resp.status_code == 200
    body = resp.json()
    assert body['ok'] is True
    assert body['models'] == ['gpt-oss-20b', 'llama3']


def test_verify_failure_degrades(csrf_client: TestClient, monkeypatch) -> None:
    created = csrf_client.post('/api/v1/admin/llm-connections', json=_VALID_PAYLOAD)
    connection_id = created.json()['id']

    def _boom(self) -> list[str]:
        raise LlmConnectionError('endpoint is down')

    monkeypatch.setattr(OpenAiCompatibleClient, 'list_models', _boom)
    resp = csrf_client.post(f'/api/v1/admin/llm-connections/{connection_id}/verify')
    assert resp.status_code == 200
    body = resp.json()
    assert body['ok'] is False
    assert body['models'] == []
    assert body['detail']


def test_models_listing_reads_permission(csrf_client: TestClient, monkeypatch) -> None:
    created = csrf_client.post('/api/v1/admin/llm-connections', json=_VALID_PAYLOAD)
    connection_id = created.json()['id']
    monkeypatch.setattr(OpenAiCompatibleClient, 'list_models', lambda self: ['m1'])
    resp = csrf_client.get(f'/api/v1/admin/llm-connections/{connection_id}/models')
    assert resp.status_code == 200
    assert resp.json()['models'] == ['m1']


def test_set_default_via_api(csrf_client: TestClient) -> None:
    first = csrf_client.post('/api/v1/admin/llm-connections', json=dict(_VALID_PAYLOAD, name='a')).json()
    second = csrf_client.post('/api/v1/admin/llm-connections', json=dict(_VALID_PAYLOAD, name='b')).json()
    resp = csrf_client.post(f"/api/v1/admin/llm-connections/{second['id']}/default")
    assert resp.status_code == 200
    assert resp.json()['is_default'] is True
    rows = csrf_client.get('/api/v1/admin/llm-connections').json()
    defaults = [row for row in rows if row['is_default']]
    assert len(defaults) == 1
    assert defaults[0]['id'] == second['id']
    assert first['is_default'] is False


def test_delete_via_api(csrf_client: TestClient) -> None:
    created = csrf_client.post('/api/v1/admin/llm-connections', json=_VALID_PAYLOAD).json()
    resp = csrf_client.delete(f"/api/v1/admin/llm-connections/{created['id']}")
    assert resp.status_code == 204
    assert csrf_client.get('/api/v1/admin/llm-connections').json() == []
