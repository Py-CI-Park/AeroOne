from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.security import hash_password
from app.modules.admin.models import AiRequestLog, LoginEvent, ServiceModule, UserPermission, UserSessionActivity
from app.modules.auth.models import User

FORBIDDEN_KEYS = ('id', 'session_hash', 'ip_address', 'user_agent', 'request_id')


def _login(client, username='admin', password='password'):
    response = client.post('/api/v1/auth/login', json={'username': username, 'password': password})
    assert response.status_code == 200
    return response


def _walk_keys(node, keys: set[str]) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            keys.add(key)
            _walk_keys(value, keys)
    elif isinstance(node, list):
        for item in node:
            _walk_keys(item, keys)


def test_activity_requires_auth(client) -> None:
    response = client.get('/api/v1/auth/activity')
    assert response.status_code == 401
    assert response.headers.get('cache-control') == 'no-store'


def test_activity_rejects_query_parameters(client) -> None:
    _login(client)
    response = client.get('/api/v1/auth/activity?foo=bar')
    assert response.status_code == 422
    assert response.headers.get('cache-control') == 'no-store'


def test_activity_rejects_non_empty_body(client) -> None:
    _login(client)
    response = client.request('GET', '/api/v1/auth/activity', content=b'{"unexpected": true}')
    assert response.status_code == 422
    assert response.headers.get('cache-control') == 'no-store'


def test_activity_success_sets_no_store_and_matches_shape(client) -> None:
    _login(client)
    response = client.get('/api/v1/auth/activity')
    assert response.status_code == 200
    assert response.headers.get('cache-control') == 'no-store'
    payload = response.json()
    assert set(payload.keys()) == {'identity', 'active_sessions', 'auth_events', 'ai_requests', 'accessible_modules'}
    assert set(payload['identity'].keys()) == {'username', 'display_name', 'role'}
    assert payload['identity']['username'] == 'admin'
    assert payload['identity']['role'] == 'admin'
    assert isinstance(payload['active_sessions'], list)
    assert isinstance(payload['auth_events'], list)
    assert isinstance(payload['ai_requests'], list)
    assert isinstance(payload['accessible_modules'], list)


def test_activity_current_session_labeled_current_via_real_cookie(client) -> None:
    _login(client)
    response = client.get('/api/v1/auth/activity')
    assert response.status_code == 200
    sessions = response.json()['active_sessions']
    assert len(sessions) == 1
    assert sessions[0]['state'] == 'current'
    assert sessions[0]['device_label'] == '현재 기기'


def test_activity_role_labels_including_unknown_fail_closed(app, client) -> None:
    with app.state.db.session() as session:
        session.add(User(username='regular-user', password_hash=hash_password('password'), role='user', is_active=True))
        session.add(User(username='pending-user', password_hash=hash_password('password'), role='pending', is_active=True))
        session.add(User(username='odd-role-user', password_hash=hash_password('password'), role='superadmin', is_active=True))
        session.flush()

    expected = {
        'admin': 'admin',
        'regular-user': 'user',
        'pending-user': 'pending',
    }
    for username, expected_role in expected.items():
        _login(client, username=username)
        response = client.get('/api/v1/auth/activity')
        assert response.status_code == 200
        assert response.json()['identity']['role'] == expected_role

    _login(client, username='odd-role-user')
    response = client.get('/api/v1/auth/activity')
    assert response.status_code == 500
    assert response.headers.get('cache-control') == 'no-store'
    assert response.json() == {'detail': 'Activity data is temporarily unavailable.'}


def test_activity_custom_modules_sort_by_order_then_key_and_module_key_is_null(app, client) -> None:
    with app.state.db.session() as session:
        session.add(ServiceModule(key='zeta', title='Zeta Module', href='#', section='ops', sort_order=1))
        session.add(ServiceModule(key='alpha', title='Alpha Module', href='#', section='ops', sort_order=1))
        session.add(ServiceModule(key='beta', title='Beta Module', href='#', section='ops', sort_order=0))
        user = session.scalar(select(User).where(User.username == 'admin'))
        session.add(AiRequestLog(request_id='req-mod-1', user_id=user.id, model='gemma', status='ok', collection_scope='civil_aircraft'))
        session.flush()

    _login(client)
    response = client.get('/api/v1/auth/activity')
    assert response.status_code == 200
    payload = response.json()
    keys = [
        row['key']
        for row in payload['accessible_modules']
        if row['key'] in {'alpha', 'beta', 'zeta'}
    ]
    assert keys == ['beta', 'alpha', 'zeta']
    assert all(row['module_key'] is None for row in payload['ai_requests'])


def test_activity_accessible_modules_enforce_audience_and_permissions(app, client) -> None:
    prefix = 'activity-policy-'
    with app.state.db.session() as session:
        direct_user = User(
            username='activity-permitted-user',
            password_hash=hash_password('password'),
            role='user',
            is_active=True,
        )
        regular_user = User(
            username='activity-regular-user',
            password_hash=hash_password('password'),
            role='user',
            is_active=True,
        )
        pending_user = User(
            username='activity-pending-user',
            password_hash=hash_password('password'),
            role='pending',
            is_active=True,
        )
        session.add_all([direct_user, regular_user, pending_user])
        session.flush()
        session.add(
            UserPermission(
                user_id=direct_user.id,
                permission_key='collections.nsa.read',
            )
        )
        session.add_all(
            [
                ServiceModule(
                    key=f'{prefix}free',
                    title='Free',
                    href='/free',
                    section='policy',
                    status='active',
                    sort_order=1,
                    is_enabled=True,
                    visibility='public',
                ),
                ServiceModule(
                    key=f'{prefix}gated',
                    title='Gated',
                    href='/gated',
                    section='policy',
                    status='active',
                    sort_order=2,
                    is_enabled=True,
                    visibility='public',
                    required_permission='collections.nsa.read',
                    resource_type='collection',
                    resource_id='nsa',
                ),
                ServiceModule(
                    key=f'{prefix}mismatched-collection-permission',
                    title='Mismatched Collection Permission',
                    href='/mismatched',
                    section='policy',
                    status='active',
                    sort_order=3,
                    is_enabled=True,
                    visibility='public',
                    required_permission='collections.nsa.write',
                    resource_type='collection',
                    resource_id='nsa',
                ),
                ServiceModule(
                    key=f'{prefix}admin',
                    title='Admin',
                    href='/admin-only',
                    section='policy',
                    status='active',
                    sort_order=3,
                    is_enabled=True,
                    visibility='admin',
                ),
                ServiceModule(
                    key=f'{prefix}hidden',
                    title='Hidden',
                    href='/hidden',
                    section='policy',
                    status='hidden',
                    sort_order=4,
                    is_enabled=True,
                    visibility='public',
                ),
                ServiceModule(
                    key=f'{prefix}disabled',
                    title='Disabled',
                    href='/disabled',
                    section='policy',
                    status='active',
                    sort_order=5,
                    is_enabled=False,
                    visibility='public',
                ),
            ]
        )
        session.flush()

    expected_by_user = {
        'activity-regular-user': [f'{prefix}free'],
        'activity-pending-user': [f'{prefix}free'],
        'activity-permitted-user': [f'{prefix}free', f'{prefix}gated'],
        'admin': [f'{prefix}free', f'{prefix}gated', f'{prefix}admin'],
    }
    for username, expected_keys in expected_by_user.items():
        _login(client, username=username)
        response = client.get('/api/v1/auth/activity')
        assert response.status_code == 200
        policy_keys = [
            item['key']
            for item in response.json()['accessible_modules']
            if item['key'].startswith(prefix)
        ]
        assert policy_keys == expected_keys


def test_activity_unknown_login_status_is_omitted(app, client) -> None:
    with app.state.db.session() as session:
        user = session.scalar(select(User).where(User.username == 'admin'))
        base = datetime.now(UTC)
        session.add(LoginEvent(user_id=user.id, username='admin', status='impersonation', created_at=base))
        session.add(LoginEvent(user_id=user.id, username='admin', status='success', created_at=base - timedelta(seconds=1)))
        session.flush()

    _login(client)
    response = client.get('/api/v1/auth/activity')
    assert response.status_code == 200
    assert response.headers.get('cache-control') == 'no-store'
    events = response.json()['auth_events']
    assert len(events) == 2
    assert all(event['kind'] == 'login' for event in events)
    assert all(event['outcome'] == 'success' for event in events)
    assert all(set(event) == {'kind', 'outcome', 'occurred_at'} for event in events)
    assert 'impersonation' not in json.dumps(response.json())


def test_activity_all_unknown_ai_statuses_return_empty_array(app, client) -> None:
    with app.state.db.session() as session:
        user = session.scalar(select(User).where(User.username == 'admin'))
        session.add(
            AiRequestLog(
                request_id='req-unknown-ai-only',
                user_id=user.id,
                model='gemma',
                status='queued',
            )
        )
        session.flush()

    _login(client)
    response = client.get('/api/v1/auth/activity')
    assert response.status_code == 200
    assert response.headers.get('cache-control') == 'no-store'
    assert response.json()['ai_requests'] == []
    assert 'queued' not in json.dumps(response.json())


def test_activity_session_ttl_cutoff_and_latest_20_limit(app, client) -> None:
    _login(client)
    assert client.get('/api/v1/auth/activity').status_code == 200  # creates the current session row

    with app.state.db.session() as session:
        user = session.scalar(select(User).where(User.username == 'admin'))
        now = datetime.now(UTC)
        stale_timestamp = (now - timedelta(minutes=31)).isoformat().replace('+00:00', 'Z')
        session.add(UserSessionActivity(user_id=user.id, session_hash='expired1' * 8, last_seen_at=now, expires_at=now - timedelta(minutes=1)))
        session.add(
            UserSessionActivity(
                user_id=user.id,
                session_hash='stale-null-expiry'.ljust(64, 's'),
                last_seen_at=now - timedelta(minutes=31),
                expires_at=None,
            )
        )
        future_expiry = now + timedelta(hours=1)
        session.add(
            UserSessionActivity(
                user_id=user.id,
                session_hash='future-expiry'.ljust(64, 'f'),
                last_seen_at=now + timedelta(seconds=1),
                expires_at=future_expiry,
            )
        )
        for i in range(25):
            session.add(
                UserSessionActivity(
                    user_id=user.id,
                    session_hash=f'{i:064d}',
                    last_seen_at=now - timedelta(seconds=i + 1),
                )
            )
        session.flush()

    response = client.get('/api/v1/auth/activity')
    assert response.status_code == 200
    sessions = response.json()['active_sessions']
    assert len(sessions) == 20
    timestamps = [row['last_activity_at'] for row in sessions]
    assert timestamps == sorted(timestamps, reverse=True)
    assert stale_timestamp not in timestamps
    assert datetime.fromisoformat(timestamps[0].replace('Z', '+00:00')) > now


def test_activity_response_never_leaks_forbidden_keys(app, client) -> None:
    with app.state.db.session() as session:
        user = session.scalar(select(User).where(User.username == 'admin'))
        now = datetime.now(UTC)
        session.add(LoginEvent(user_id=user.id, username='admin', status='success', ip_address='10.0.0.5', user_agent='pytest-agent', created_at=now))
        session.add(AiRequestLog(request_id='req-privacy-1', user_id=user.id, model='gemma', status='ok', ip_address='10.0.0.5', session_hash='c' * 64, created_at=now))
        session.add(UserSessionActivity(user_id=user.id, session_hash='d' * 64, last_seen_at=now))
        session.flush()

    _login(client)
    response = client.get('/api/v1/auth/activity')
    assert response.status_code == 200
    payload = response.json()

    all_keys: set[str] = set()
    _walk_keys(payload, all_keys)
    assert not (all_keys & set(FORBIDDEN_KEYS))

    dumped = json.dumps(payload)
    for fragment in ('session_hash', 'ip_address', 'user_agent', 'request_id', '10.0.0.5', 'pytest-agent'):
        assert fragment not in dumped


def test_activity_rfc3339_utc_z_timestamps(app, client) -> None:
    _login(client)
    response = client.get('/api/v1/auth/activity')
    assert response.status_code == 200
    payload = response.json()
    for row in payload['active_sessions']:
        assert row['last_activity_at'].endswith('Z')
        datetime.fromisoformat(row['last_activity_at'].replace('Z', '+00:00'))
