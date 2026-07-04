from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import hash_password
from app.modules.admin.models import AdminAuditEvent, LoginEvent, UserSessionActivity
from app.modules.auth.models import User
from app.modules.read_tracking.models.read_event import NewsletterReadEvent


WRONG_PASSWORD = 'wrong-password-redteam-secret'


def _login(client: TestClient, username: str = 'admin', password: str = 'password') -> dict:
    response = client.post(
        '/api/v1/auth/login',
        json={'username': username, 'password': password},
        headers={'user-agent': f'{username}-redteam-agent'},
    )
    assert response.status_code == 200
    body = response.json()
    client.headers.update({'x-csrf-token': body['csrf_token']})
    return body


def _create_user(app, username: str = 'plain-user', password: str = 'password') -> None:
    with app.state.db.session() as session:
        session.add(User(username=username, password_hash=hash_password(password), role='user'))
        session.flush()


def _login_event_blob(event: LoginEvent) -> str:
    values = {column.name: getattr(event, column.name) for column in LoginEvent.__table__.columns}
    return json.dumps(values, default=str, sort_keys=True)


def test_db_level_debounce_suppresses_repeated_writes_until_window_expires(app, client) -> None:
    _login(client)

    first = client.get('/api/v1/auth/me')
    assert first.status_code == 200
    with app.state.db.session() as session:
        rows = session.execute(select(UserSessionActivity)).scalars().all()
        assert len(rows) == 1
        activity = rows[0]
        activity_id = activity.id
        session_hash = activity.session_hash
        first_seen = activity.last_seen_at

    for _ in range(5):
        ping = client.get('/api/v1/auth/me')
        assert ping.status_code == 200

    with app.state.db.session() as session:
        rows = session.execute(select(UserSessionActivity)).scalars().all()
        assert len(rows) == 1
        activity = rows[0]
        assert activity.id == activity_id
        assert activity.session_hash == session_hash
        assert activity.last_seen_at == first_seen

        aged_seen = datetime.now(UTC) - timedelta(seconds=app.state.settings.session_activity_debounce_seconds + 5)
        activity.last_seen_at = aged_seen
        session.flush()

    after_window = client.get('/api/v1/auth/me')
    assert after_window.status_code == 200
    with app.state.db.session() as session:
        rows = session.execute(select(UserSessionActivity)).scalars().all()
        assert len(rows) == 1
        activity = rows[0]
        assert activity.id == activity_id
        assert activity.session_hash == session_hash
        assert activity.last_seen_at != first_seen
        assert activity.last_seen_at.replace(tzinfo=UTC) > aged_seen


def test_login_events_are_metadata_only_and_never_store_password_or_token(app, client) -> None:
    bad = client.post(
        '/api/v1/auth/login',
        json={'username': 'admin', 'password': WRONG_PASSWORD},
        headers={'user-agent': 'failure-agent'},
    )
    assert bad.status_code == 401
    success = client.post(
        '/api/v1/auth/login',
        json={'username': 'admin', 'password': 'password'},
        headers={'user-agent': 'success-agent'},
    )
    assert success.status_code == 200
    token = success.cookies.get(app.state.settings.admin_session_cookie_name)
    assert token

    with app.state.db.session() as session:
        events = session.execute(select(LoginEvent).order_by(LoginEvent.id)).scalars().all()
        failure = next(event for event in events if event.status == 'failure')
        successful = next(event for event in events if event.status == 'success')

        failure_blob = _login_event_blob(failure)
        success_blob = _login_event_blob(successful)
        assert failure.username == 'admin'
        assert failure.user_agent == 'failure-agent'
        assert failure.ip_address
        assert WRONG_PASSWORD not in failure_blob

        assert successful.username == 'admin'
        assert successful.status == 'success'
        assert successful.user_agent == 'success-agent'
        assert successful.ip_address
        assert 'password' not in success_blob.lower()
        assert token not in success_blob
        assert token not in failure_blob


def test_admin_sessions_endpoint_is_admin_only_and_returns_required_payload(app, client) -> None:
    _create_user(app)
    _login(client, 'plain-user', 'password')
    forbidden = client.get('/api/v1/admin/sessions')
    assert forbidden.status_code == 403

    _login(client)
    assert client.get('/api/v1/auth/me').status_code == 200
    with app.state.db.session() as session:
        session.add(NewsletterReadEvent(newsletter_id=1, client_ip='127.0.0.9', read_count=4))
        session.flush()

    response = client.get('/api/v1/admin/sessions')
    assert response.status_code == 200
    body = response.json()
    assert {'active_sessions', 'recent_login_events', 'read_tracking_summary'} <= set(body)
    assert body['active_count'] >= 1
    assert any(row['username'] == 'admin' for row in body['active_sessions'])
    assert any(event['username'] == 'admin' and event['status'] == 'success' for event in body['recent_login_events'])
    assert isinstance(body['login_failure_count'], int)
    assert body['read_tracking_summary']['rows'] >= 1
    assert body['read_tracking_summary']['total_reads'] >= 4


def test_purge_is_admin_csrf_gated_audited_and_retention_clamped(app, client) -> None:
    _create_user(app, username='purge-user')
    _login(client, 'purge-user', 'password')
    assert client.post('/api/v1/admin/sessions/purge').status_code == 403

    _login(client)
    assert client.post('/api/v1/admin/sessions/purge', headers={'x-csrf-token': ''}).status_code == 403

    app.state.settings.connected_user_retention_days = 5
    now = datetime.now(UTC)
    older_than_minimum = now - timedelta(days=31)
    inside_minimum = now - timedelta(days=29)
    with app.state.db.session() as session:
        admin = session.scalar(select(User).where(User.username == 'admin'))
        assert admin is not None
        session.add_all(
            [
                LoginEvent(user_id=admin.id, username='old-login-min-clamp', status='failure', created_at=older_than_minimum),
                LoginEvent(user_id=admin.id, username='recent-login-min-clamp', status='success', created_at=inside_minimum),
                UserSessionActivity(user_id=admin.id, session_hash='c' * 64, last_seen_at=older_than_minimum),
                UserSessionActivity(user_id=admin.id, session_hash='d' * 64, last_seen_at=inside_minimum),
            ]
        )
        session.flush()

    min_response = client.post('/api/v1/admin/sessions/purge')
    assert min_response.status_code == 200
    assert min_response.json()['login_events_deleted'] >= 1
    assert min_response.json()['session_activity_deleted'] >= 1
    with app.state.db.session() as session:
        usernames = set(session.execute(select(LoginEvent.username)).scalars().all())
        hashes = set(session.execute(select(UserSessionActivity.session_hash)).scalars().all())
        assert 'old-login-min-clamp' not in usernames
        assert 'recent-login-min-clamp' in usernames
        assert 'c' * 64 not in hashes
        assert 'd' * 64 in hashes
        assert session.scalar(select(AdminAuditEvent).where(AdminAuditEvent.action == 'admin.sessions.purge')) is not None

    app.state.settings.connected_user_retention_days = 120
    older_than_maximum = now - timedelta(days=91)
    inside_maximum = now - timedelta(days=89)
    with app.state.db.session() as session:
        admin = session.scalar(select(User).where(User.username == 'admin'))
        assert admin is not None
        session.add_all(
            [
                LoginEvent(user_id=admin.id, username='old-login-max-clamp', status='failure', created_at=older_than_maximum),
                LoginEvent(user_id=admin.id, username='recent-login-max-clamp', status='success', created_at=inside_maximum),
                UserSessionActivity(user_id=admin.id, session_hash='e' * 64, last_seen_at=older_than_maximum),
                UserSessionActivity(user_id=admin.id, session_hash='f' * 64, last_seen_at=inside_maximum),
            ]
        )
        session.flush()

    max_response = client.post('/api/v1/admin/sessions/purge')
    assert max_response.status_code == 200
    with app.state.db.session() as session:
        usernames = set(session.execute(select(LoginEvent.username)).scalars().all())
        hashes = set(session.execute(select(UserSessionActivity.session_hash)).scalars().all())
        assert 'old-login-max-clamp' not in usernames
        assert 'recent-login-max-clamp' in usernames
        assert 'e' * 64 not in hashes
        assert 'f' * 64 in hashes
        audits = session.execute(select(AdminAuditEvent).where(AdminAuditEvent.action == 'admin.sessions.purge')).scalars().all()
        assert len(audits) >= 2
