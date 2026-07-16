from __future__ import annotations

import json
import urllib.error

import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.modules.leantime import rpc_client
from app.modules.leantime import read_api
from app.modules.leantime.connection_service import LeantimeConnectionService
from app.modules.leantime.rpc_client import (
    LeantimeAuthError,
    LeantimeProtocolError,
    LeantimeRpcClient,
    LeantimeRpcError,
    LeantimeUnavailable,
)
from app.modules.leantime.schemas import LeantimeConnectionCreate
from app.modules.auth.repositories import UserRepository


# ---------------------------------------------------------------------------
# LeantimeRpcClient — allowlist, transport, exception mapping, normalization
# ---------------------------------------------------------------------------


def _client(**overrides) -> LeantimeRpcClient:
    defaults = dict(base_url='https://leantime.internal', api_key='scoped-secret-key', verify_tls=True, timeout=1.0)
    defaults.update(overrides)
    return LeantimeRpcClient(**defaults)


def test_disallowed_method_rejected_before_any_network_call(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*args, **kwargs):
        raise AssertionError('transport must not be called for a disallowed method')

    monkeypatch.setattr(rpc_client, '_post_jsonrpc', _boom)
    client = _client()
    with pytest.raises(ValueError):
        client._call('leantime.rpc.users.delete')


def test_transport_sends_key_via_header_never_in_url_or_query(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class _FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self) -> bytes:
            return json.dumps({'jsonrpc': '2.0', 'id': 1, 'result': []}).encode('utf-8')

    def _fake_urlopen(req, timeout=None, context=None):
        captured['url'] = req.full_url
        captured['headers'] = {key.lower(): value for key, value in req.header_items()}
        captured['body'] = req.data.decode('utf-8')
        return _FakeResponse()

    monkeypatch.setattr(rpc_client.request, 'urlopen', _fake_urlopen)
    client = _client(api_key='super-secret-token')
    client.list_projects()

    assert captured['url'] == 'https://leantime.internal/api/jsonrpc'
    assert '?' not in captured['url']
    assert 'super-secret-token' not in captured['url']
    assert captured['headers']['x-api-key'] == 'super-secret-token'
    assert 'super-secret-token' not in captured['body']


def test_timeout_maps_to_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise_timeout(*args, **kwargs):
        raise TimeoutError('timed out')

    monkeypatch.setattr(rpc_client, '_post_jsonrpc', _raise_timeout)
    with pytest.raises(LeantimeUnavailable):
        _client().list_projects()


def test_http_5xx_maps_to_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise_500(*args, **kwargs):
        raise urllib.error.HTTPError('https://leantime.internal/api/jsonrpc', 502, 'Bad Gateway', {}, None)

    monkeypatch.setattr(rpc_client, '_post_jsonrpc', _raise_500)
    with pytest.raises(LeantimeUnavailable):
        _client().list_projects()


@pytest.mark.parametrize('code', [401, 403])
def test_http_401_403_maps_to_auth_error(monkeypatch: pytest.MonkeyPatch, code: int) -> None:
    def _raise_auth(*args, **kwargs):
        raise urllib.error.HTTPError('https://leantime.internal/api/jsonrpc', code, 'Forbidden', {}, None)

    monkeypatch.setattr(rpc_client, '_post_jsonrpc', _raise_auth)
    with pytest.raises(LeantimeAuthError):
        _client().list_projects()


def test_jsonrpc_error_object_maps_to_rpc_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake(*args, **kwargs):
        return {'jsonrpc': '2.0', 'id': 1, 'error': {'code': -32601, 'message': 'Method not found'}}

    monkeypatch.setattr(rpc_client, '_post_jsonrpc', _fake)
    with pytest.raises(LeantimeRpcError):
        _client().list_projects()


@pytest.mark.parametrize(
    'malformed',
    [
        ['not', 'a', 'dict'],
        {'jsonrpc': '2.0', 'id': 1},  # missing result
        {'no': 'envelope'},
    ],
)
def test_malformed_response_maps_to_protocol_error(monkeypatch: pytest.MonkeyPatch, malformed) -> None:
    monkeypatch.setattr(rpc_client, '_post_jsonrpc', lambda *a, **k: malformed)
    with pytest.raises(LeantimeProtocolError):
        _client().list_projects()


def test_dto_normalization_tolerates_missing_and_extra_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [
        {'id': 1, 'name': 'Alpha', 'unexpectedField': 'ignored'},
        {'unexpectedField': 'ignored-again'},  # missing id/name entirely
    ]
    monkeypatch.setattr(rpc_client, '_post_jsonrpc', lambda *a, **k: {'jsonrpc': '2.0', 'id': 1, 'result': rows})
    projects = _client().list_projects()
    assert len(projects) == 2
    assert projects[0].id == '1'
    assert projects[0].name == 'Alpha'
    assert projects[1].name  # defaulted, never raises


# ---------------------------------------------------------------------------
# read_api — permission gate + graceful degradation
# ---------------------------------------------------------------------------


def _mount_read_api(app) -> TestClient:
    if not any(route.path == '/api/v1/leantime/projects' for route in app.routes):
        app.include_router(read_api.router, prefix='/api/v1/leantime')
    return TestClient(app)


def _create_user(app, username: str, role: str) -> None:
    with app.state.db.session() as session:
        UserRepository(session).create(username=username, password_hash=hash_password('password123'), role=role)


def _login(client: TestClient, username: str, password: str) -> None:
    resp = client.post('/api/v1/auth/login', json={'username': username, 'password': password})
    assert resp.status_code == 200


def _add_connection(app, *, base_url='https://leantime.internal', api_key='scoped-key', is_enabled=True):
    settings = app.state.settings
    with app.state.db.session() as session:
        service = LeantimeConnectionService(session, settings)
        connection = service.create(
            LeantimeConnectionCreate(name='primary', base_url=base_url, api_key=api_key, is_enabled=is_enabled)
        )
        session.commit()
        return connection.id


def test_read_endpoint_requires_permission(app) -> None:
    # 1.16.3 부터 발급 계정(user 역할)은 leantime.read 를 기본 보유한다.
    # 권한 없는 인증 주체는 역할 기본 권한이 빈 pending 계정으로 재현한다.
    _create_user(app, 'pending-leantime', role='pending')
    client = _mount_read_api(app)
    _login(client, 'pending-leantime', 'password123')
    resp = client.get('/api/v1/leantime/projects')
    assert resp.status_code == 403


def test_read_endpoint_allows_issued_user_by_default(app) -> None:
    # 발급 계정 전체 접근(1.16.3): 명시 부여 없이도 user 역할이면 읽기 가능(degraded 응답).
    _create_user(app, 'issued-leantime', role='user')
    client = _mount_read_api(app)
    _login(client, 'issued-leantime', 'password123')
    resp = client.get('/api/v1/leantime/projects')
    assert resp.status_code == 200
    assert resp.json()['degraded'] is True


def test_read_endpoint_degrades_when_not_configured(app) -> None:
    client = _mount_read_api(app)
    _login(client, 'admin', 'password')
    resp = client.get('/api/v1/leantime/projects')
    assert resp.status_code == 200
    body = resp.json()
    assert body['degraded'] is True
    assert body['reason'] == 'not_configured'
    assert body['items'] == []


def test_read_endpoint_degrades_on_client_failure(app, monkeypatch: pytest.MonkeyPatch) -> None:
    _add_connection(app, api_key='top-secret-key')
    client = _mount_read_api(app)
    _login(client, 'admin', 'password')

    def _boom(self):
        raise LeantimeUnavailable('down')

    monkeypatch.setattr(LeantimeRpcClient, 'list_projects', _boom)
    resp = client.get('/api/v1/leantime/projects')
    assert resp.status_code == 200
    body = resp.json()
    assert body['degraded'] is True
    assert body['reason'] == 'upstream_unavailable'
    assert 'top-secret-key' not in resp.text


def test_read_endpoint_degrades_on_auth_failure(app, monkeypatch: pytest.MonkeyPatch) -> None:
    _add_connection(app, api_key='top-secret-key')
    client = _mount_read_api(app)
    _login(client, 'admin', 'password')

    def _boom(self):
        raise LeantimeAuthError('rejected')

    monkeypatch.setattr(LeantimeRpcClient, 'list_tasks', _boom)
    resp = client.get('/api/v1/leantime/tasks')
    assert resp.status_code == 200
    body = resp.json()
    assert body['degraded'] is True
    assert body['reason'] == 'auth_failed'


def test_read_endpoint_degrades_on_undecryptable_key(app, monkeypatch: pytest.MonkeyPatch) -> None:
    # 저장 키가 복호화 불가(시크릿 회전/손상)여도 500 이 아니라 degraded 로 낮춘다.
    from app.modules.leantime.connection_service import LeantimeConnectionService

    _add_connection(app, api_key='top-secret-key')
    client = _mount_read_api(app)
    _login(client, 'admin', 'password')

    def _boom(self, connection):
        raise ValueError('MAC verification failed')

    monkeypatch.setattr(LeantimeConnectionService, 'decrypted_key', _boom)
    resp = client.get('/api/v1/leantime/projects')
    assert resp.status_code == 200
    body = resp.json()
    assert body['degraded'] is True
    assert body['reason'] == 'credential_error'
    assert body['items'] == []
    assert 'top-secret-key' not in resp.text

def test_read_endpoint_returns_normalized_items_on_success(app, monkeypatch: pytest.MonkeyPatch) -> None:
    _add_connection(app, api_key='top-secret-key')
    client = _mount_read_api(app)
    _login(client, 'admin', 'password')

    from app.modules.leantime.schemas import LeantimeProject

    def _fake_list_projects(self):
        return [LeantimeProject(id='1', name='Demo Project')]

    monkeypatch.setattr(LeantimeRpcClient, 'list_projects', _fake_list_projects)
    resp = client.get('/api/v1/leantime/projects')
    assert resp.status_code == 200
    body = resp.json()
    assert body['degraded'] is False
    assert body['items'] == [{'id': '1', 'name': 'Demo Project', 'state': None, 'client_name': None}]
    assert body['fetched_at']
    assert 'top-secret-key' not in resp.text


def test_calendar_endpoint_never_leaks_api_key_on_success(app, monkeypatch: pytest.MonkeyPatch) -> None:
    _add_connection(app, api_key='top-secret-key')
    client = _mount_read_api(app)
    _login(client, 'admin', 'password')

    from app.modules.leantime.schemas import LeantimeCalendarEntry

    def _fake_list_calendar(self, start, end):
        return [LeantimeCalendarEntry(id='1', name='Milestone', date_start=start, date_end=end)]

    monkeypatch.setattr(LeantimeRpcClient, 'list_calendar', _fake_list_calendar)
    resp = client.get('/api/v1/leantime/calendar', params={'start': '2026-01-01', 'end': '2026-01-31'})
    assert resp.status_code == 200
    body = resp.json()
    assert body['items'][0]['date_start'] == '2026-01-01'
    assert 'top-secret-key' not in resp.text
