from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.modules.admin.models import AiRequestLog, LoginEvent, ServiceModule, UserSessionActivity
from app.modules.auth.activity_service import build_activity_payload
from app.modules.auth.models import User
from app.modules.auth.session_hash import hash_session_token


class _FakeRequest:
    def __init__(self, cookies: dict[str, str]) -> None:
        self.cookies = cookies


def _get_admin(app) -> User:
    with app.state.db.session() as session:
        user = session.scalar(select(User).where(User.username == 'admin'))
        session.expunge(user)
        return user


def test_session_creation_stores_hash_matching_helper(app, client) -> None:
    login_response = client.post('/api/v1/auth/login', json={'username': 'admin', 'password': 'password'})
    assert login_response.status_code == 200
    token = client.cookies.get('admin_session')
    assert token

    assert client.get('/api/v1/auth/me').status_code == 200

    with app.state.db.session() as session:
        rows = session.execute(select(UserSessionActivity)).scalars().all()
        assert len(rows) == 1
        assert rows[0].session_hash == hash_session_token(token)


def test_logout_removes_exactly_the_helper_hashed_row(app, client) -> None:
    login_response = client.post('/api/v1/auth/login', json={'username': 'admin', 'password': 'password'})
    assert login_response.status_code == 200
    token = client.cookies.get('admin_session')
    assert client.get('/api/v1/auth/me').status_code == 200

    other_hash = 'f' * 64
    with app.state.db.session() as session:
        user = session.scalar(select(User).where(User.username == 'admin'))
        session.add(UserSessionActivity(user_id=user.id, session_hash=other_hash, last_seen_at=datetime.now(UTC)))
        session.flush()

    logout_response = client.post('/api/v1/auth/logout')
    assert logout_response.status_code == 200

    with app.state.db.session() as session:
        remaining_hashes = set(session.execute(select(UserSessionActivity.session_hash)).scalars().all())
    assert hash_session_token(token) not in remaining_hashes
    assert other_hash in remaining_hashes


def test_no_matching_session_yields_no_synthetic_current(app) -> None:
    user = _get_admin(app)
    now = datetime.now(UTC)
    with app.state.db.session() as session:
        session.add(UserSessionActivity(user_id=user.id, session_hash='a' * 64, last_seen_at=now))
        session.flush()
        payload = build_activity_payload(session, user, _FakeRequest({'admin_session': 'no-such-token'}), app.state.settings)

    assert len(payload['active_sessions']) == 1
    assert payload['active_sessions'][0]['state'] == 'active'
    assert payload['active_sessions'][0]['device_label'] == '다른 활성 기기'
    assert not any(row['state'] == 'current' for row in payload['active_sessions'])


def test_matching_session_is_labeled_current(app) -> None:
    user = _get_admin(app)
    token = 'a-real-current-token'
    now = datetime.now(UTC)
    with app.state.db.session() as session:
        session.add(UserSessionActivity(user_id=user.id, session_hash=hash_session_token(token), last_seen_at=now))
        session.flush()
        payload = build_activity_payload(session, user, _FakeRequest({'admin_session': token}), app.state.settings)

    assert len(payload['active_sessions']) == 1
    assert payload['active_sessions'][0]['state'] == 'current'
    assert payload['active_sessions'][0]['device_label'] == '현재 기기'


def test_expired_session_is_omitted(app) -> None:
    user = _get_admin(app)
    now = datetime.now(UTC)
    with app.state.db.session() as session:
        session.add(UserSessionActivity(user_id=user.id, session_hash='e' * 64, last_seen_at=now, expires_at=now - timedelta(minutes=5)))
        session.add(UserSessionActivity(user_id=user.id, session_hash='n' * 64, last_seen_at=now, expires_at=None))
        session.add(UserSessionActivity(user_id=user.id, session_hash='f' * 64, last_seen_at=now, expires_at=now + timedelta(minutes=5)))
        session.flush()
        payload = build_activity_payload(session, user, _FakeRequest({}), app.state.settings)

    assert len(payload['active_sessions']) == 2


def test_active_sessions_ordering_latest_20_and_id_tiebreak(app) -> None:
    user = _get_admin(app)
    t0 = datetime.now(UTC)
    token = 'tiebreak-token'
    with app.state.db.session() as session:
        low_id_row = UserSessionActivity(user_id=user.id, session_hash=hash_session_token(token), last_seen_at=t0)
        session.add(low_id_row)
        session.flush()
        high_id_row = UserSessionActivity(user_id=user.id, session_hash='b' * 64, last_seen_at=t0)
        session.add(high_id_row)
        session.flush()
        assert high_id_row.id > low_id_row.id

        for i in range(25):
            session.add(
                UserSessionActivity(
                    user_id=user.id,
                    session_hash=f'{i:064d}',
                    last_seen_at=t0 - timedelta(seconds=i + 1),
                )
            )
        session.flush()

        payload = build_activity_payload(session, user, _FakeRequest({'admin_session': token}), app.state.settings)

    sessions = payload['active_sessions']
    assert len(sessions) == 20
    # Tied last_activity_at at the top: higher id (non-current) must sort before the lower-id current row.
    assert sessions[0]['last_activity_at'] == sessions[1]['last_activity_at']
    assert sessions[0]['state'] == 'active'
    assert sessions[1]['state'] == 'current'
    timestamps = [row['last_activity_at'] for row in sessions]
    assert timestamps == sorted(timestamps, reverse=True)


def test_auth_events_unknown_status_fails_closed(app) -> None:
    user = _get_admin(app)
    base = datetime.now(UTC)
    statuses = ['unknown-a', 'unknown-b'] + ['success', 'failure', 'logout'] * 20
    with app.state.db.session() as session:
        for index, status in enumerate(statuses):
            session.add(
                LoginEvent(
                    user_id=user.id,
                    username='admin',
                    status=status,
                    created_at=base - timedelta(seconds=index),
                )
            )
        session.flush()
        with pytest.raises(ValueError, match='Unsupported stored login event status'):
            build_activity_payload(session, user, _FakeRequest({}), app.state.settings)


def test_auth_events_keep_latest_20_in_order(app) -> None:
    user = _get_admin(app)
    base = datetime.now(UTC)
    statuses = ['success', 'failure', 'logout'] * 10
    with app.state.db.session() as session:
        for index, status in enumerate(statuses):
            session.add(
                LoginEvent(
                    user_id=user.id,
                    username='admin',
                    status=status,
                    created_at=base - timedelta(seconds=index),
                )
            )
        session.flush()
        payload = build_activity_payload(session, user, _FakeRequest({}), app.state.settings)

    assert len(payload['auth_events']) == 20
    occurred = [event['occurred_at'] for event in payload['auth_events']]
    assert occurred == sorted(occurred, reverse=True)
    assert {event['kind'] for event in payload['auth_events']} == {'login', 'logout'}


def test_ai_requests_unknown_status_fails_closed(app) -> None:
    user = _get_admin(app)
    base = datetime.now(UTC)
    with app.state.db.session() as session:
        session.add(AiRequestLog(request_id='req-ok-1', user_id=user.id, model='gemma', status='ok', collection_scope='civil', created_at=base))
        session.add(AiRequestLog(request_id='req-error-1', user_id=user.id, model='gemma', status='error', created_at=base - timedelta(seconds=1)))
        session.add(AiRequestLog(request_id='req-unknown-1', user_id=user.id, model='gemma', status='pending', created_at=base - timedelta(seconds=2)))
        session.flush()
        with pytest.raises(ValueError, match='Unsupported stored AI request status'):
            build_activity_payload(session, user, _FakeRequest({}), app.state.settings)


def test_ai_requests_map_known_statuses_and_keep_module_key_null(app) -> None:
    user = _get_admin(app)
    base = datetime.now(UTC)
    with app.state.db.session() as session:
        session.add(
            AiRequestLog(
                request_id='req-known-ok',
                user_id=user.id,
                model='gemma',
                status='ok',
                created_at=base,
            )
        )
        session.add(
            AiRequestLog(
                request_id='req-known-error',
                user_id=user.id,
                model='gemma',
                status='error',
                created_at=base - timedelta(seconds=1),
            )
        )
        session.flush()
        payload = build_activity_payload(session, user, _FakeRequest({}), app.state.settings)

    assert [row['status'] for row in payload['ai_requests']] == ['completed', 'failed']
    assert all(row['module_key'] is None for row in payload['ai_requests'])


def test_accessible_modules_sorted_by_sort_order_then_key(app) -> None:
    user = _get_admin(app)
    with app.state.db.session() as session:
        session.add(ServiceModule(key='zeta', title='Zeta Module', href='#', section='ops', sort_order=1))
        session.add(ServiceModule(key='alpha', title='Alpha Module', href='#', section='ops', sort_order=1))
        session.add(ServiceModule(key='beta', title='Beta Module', href='#', section='ops', sort_order=0))
        session.flush()
        payload = build_activity_payload(session, user, _FakeRequest({}), app.state.settings)

    keys = [
        row['key']
        for row in payload['accessible_modules']
        if row['key'] in {'alpha', 'beta', 'zeta'}
    ]
    assert keys == ['beta', 'alpha', 'zeta']
    labels = {row['key']: row['label'] for row in payload['accessible_modules']}
    assert labels['beta'] == 'Beta Module'


def test_unknown_role_fails_closed(app) -> None:
    with app.state.db.session() as session:
        user = User(username='odd-role-user', password_hash='x', role='superadmin', is_active=True)
        session.add(user)
        session.flush()
        session.expunge(user)
        with pytest.raises(ValueError, match='Unsupported stored user role'):
            build_activity_payload(session, user, _FakeRequest({}), app.state.settings)


def test_valid_roles_pass_through_unchanged(app) -> None:
    for role in ('admin', 'user', 'pending'):
        with app.state.db.session() as session:
            user = User(username=f'role-{role}', password_hash='x', role=role, is_active=True)
            session.add(user)
            session.flush()
            session.expunge(user)
            payload = build_activity_payload(session, user, _FakeRequest({}), app.state.settings)
        assert payload['identity']['role'] == role


def test_payload_never_includes_forbidden_keys(app) -> None:
    import json

    user = _get_admin(app)
    now = datetime.now(UTC)
    with app.state.db.session() as session:
        session.add(UserSessionActivity(user_id=user.id, session_hash='a' * 64, last_seen_at=now))
        session.add(LoginEvent(user_id=user.id, username='admin', status='success', ip_address='127.0.0.1', user_agent='pytest', created_at=now))
        session.add(AiRequestLog(request_id='req-forbidden-1', user_id=user.id, model='gemma', status='ok', ip_address='127.0.0.1', session_hash='a' * 64, created_at=now))
        session.flush()
        payload = build_activity_payload(session, user, _FakeRequest({}), app.state.settings)

    dumped = json.dumps(payload)

    def _collect_keys(node: object, keys: set[str]) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                keys.add(key)
                _collect_keys(value, keys)
        elif isinstance(node, list):
            for item in node:
                _collect_keys(item, keys)

    all_keys: set[str] = set()
    _collect_keys(payload, all_keys)
    forbidden = {'id', 'session_hash', 'ip_address', 'user_agent', 'request_id', 'token', 'hash'}
    assert not (all_keys & forbidden)
    for forbidden_fragment in ('session_hash', 'ip_address', 'user_agent', 'request_id', '"id":'):
        assert forbidden_fragment not in dumped
