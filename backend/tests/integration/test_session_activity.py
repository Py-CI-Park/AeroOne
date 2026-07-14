from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

import pytest
from app.core.security import create_access_token
from app.modules.auth import dependencies as auth_dependencies
from app.modules.admin.models import AdminAuditEvent, LoginEvent, UserSessionActivity
from app.modules.auth.models import User
from app.modules.read_tracking.models.read_event import NewsletterReadEvent


def _login(client):
    response = client.post('/api/v1/auth/login', json={'username': 'admin', 'password': 'password'}, headers={'user-agent': 'pytest-agent'})
    assert response.status_code == 200
    client.headers.update({'x-csrf-token': response.json()['csrf_token']})
    return response


def test_session_activity_db_debounce(app, client):
    _login(client)
    first = client.get('/api/v1/auth/me')
    assert first.status_code == 200
    with app.state.db.session() as session:
        rows = session.execute(select(UserSessionActivity)).scalars().all()
        assert len(rows) == 1
        row = rows[0]
        first_id = row.id
        first_seen = row.last_seen_at
        first_hash = row.session_hash

    second = client.get('/api/v1/auth/me')
    assert second.status_code == 200
    with app.state.db.session() as session:
        rows = session.execute(select(UserSessionActivity)).scalars().all()
        assert len(rows) == 1
        row = rows[0]
        assert row.id == first_id
        assert row.session_hash == first_hash
        assert row.last_seen_at == first_seen

        row.last_seen_at = datetime.now(UTC) - timedelta(seconds=90)
        session.flush()

    third = client.get('/api/v1/auth/me')
    assert third.status_code == 200
    with app.state.db.session() as session:
        rows = session.execute(select(UserSessionActivity)).scalars().all()
        assert len(rows) == 1
        assert rows[0].id == first_id
        assert rows[0].last_seen_at > first_seen


def test_login_success_and_failure_create_metadata_only_events(app, client):
    ok = client.post('/api/v1/auth/login', json={'username': 'admin', 'password': 'password'}, headers={'user-agent': 'success-agent'})
    assert ok.status_code == 200
    bad = client.post('/api/v1/auth/login', json={'username': 'admin', 'password': 'wrong-secret'}, headers={'user-agent': 'failure-agent'})
    assert bad.status_code == 401

    with app.state.db.session() as session:
        events = session.execute(select(LoginEvent).order_by(LoginEvent.id)).scalars().all()
        assert [event.status for event in events][-2:] == ['success', 'failure']
        assert events[-2].username == 'admin'
        assert events[-1].username == 'admin'
        assert events[-2].user_agent == 'success-agent'
        assert events[-1].user_agent == 'failure-agent'
        assert not hasattr(events[-1], 'password')
        assert 'wrong-secret' not in repr(events[-1].__dict__)


def test_admin_sessions_is_gated_and_returns_sessions_logins_and_read_summary(app, client):
    assert client.get('/api/v1/admin/sessions').status_code == 401
    _login(client)
    assert client.get('/api/v1/auth/me').status_code == 200
    with app.state.db.session() as session:
        newsletter_id = session.scalar(select(NewsletterReadEvent.newsletter_id))
        if newsletter_id is None:
            newsletter_id = 1
        session.add(NewsletterReadEvent(newsletter_id=newsletter_id, client_ip='127.0.0.42', read_count=3))
        session.flush()

    response = client.get('/api/v1/admin/sessions')
    assert response.status_code == 200
    body = response.json()
    assert body['active_count'] >= 1
    assert any(row['username'] == 'admin' for row in body['active_sessions'])
    assert any(event['status'] == 'success' and event['username'] == 'admin' for event in body['recent_login_events'])
    assert body['read_tracking_summary']['rows'] >= 1
    assert body['read_tracking_summary']['total_reads'] >= 3


def test_purge_is_permission_csrf_audited_and_retention_scoped(app, client):
    _login(client)
    now = datetime.now(UTC)
    old = now - timedelta(days=45)
    recent = now - timedelta(days=5)
    with app.state.db.session() as session:
        user = session.scalar(select(User).where(User.username == 'admin'))
        session.add_all([
            LoginEvent(user_id=user.id, username='old', status='failure', created_at=old),
            LoginEvent(user_id=user.id, username='recent', status='success', created_at=recent),
            UserSessionActivity(user_id=user.id, session_hash='a' * 64, last_seen_at=old),
            UserSessionActivity(user_id=user.id, session_hash='b' * 64, last_seen_at=recent),
        ])
        session.flush()

    no_csrf = client.post('/api/v1/admin/sessions/purge', headers={'x-csrf-token': ''})
    assert no_csrf.status_code == 403
    response = client.post('/api/v1/admin/sessions/purge')
    assert response.status_code == 200
    assert response.json()['login_events_deleted'] >= 1
    assert response.json()['session_activity_deleted'] >= 1

    with app.state.db.session() as session:
        usernames = set(session.execute(select(LoginEvent.username)).scalars().all())
        hashes = set(session.execute(select(UserSessionActivity.session_hash)).scalars().all())
        assert 'old' not in usernames
        assert 'recent' in usernames
        assert 'a' * 64 not in hashes
        assert 'b' * 64 in hashes
        audit = session.scalar(select(AdminAuditEvent).where(AdminAuditEvent.action == 'admin.sessions.purge'))
        assert audit is not None


def test_session_activity_recovers_from_expected_unique_insert_race(app, monkeypatch):
    with app.state.db.session() as session:
        user = session.scalar(select(User).where(User.username == 'admin'))
        assert user is not None
        token = create_access_token(
            'test-secret',
            str(user.id),
            user.role,
            'race-csrf-token',
            30,
            session_version=user.session_version,
        )
        session_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()
        session.add(
            UserSessionActivity(
                user_id=user.id,
                session_hash=session_hash,
                last_seen_at=datetime.now(UTC),
            )
        )

    with app.state.db.session() as session:
        user = session.scalar(select(User).where(User.username == 'admin'))
        assert user is not None
        original_execute = session.execute
        initial_lookup_hidden = True

        class NoActivityResult:
            def scalar_one_or_none(self):
                return None

        def hide_initial_lookup(*args, **kwargs):
            nonlocal initial_lookup_hidden
            if initial_lookup_hidden:
                initial_lookup_hidden = False
                return NoActivityResult()
            return original_execute(*args, **kwargs)

        monkeypatch.setattr(session, 'execute', hide_initial_lookup)
        auth_dependencies._record_session_activity(
            None,
            session,
            app.state.settings,
            user,
            token,
            {'exp': 2_000_000_000},
        )

        activities = session.execute(
            select(UserSessionActivity).where(UserSessionActivity.session_hash == session_hash)
        ).scalars().all()
        assert len(activities) == 1
        assert activities[0].user_id == user.id


def test_session_activity_propagates_integrity_error_without_competing_activity(app, monkeypatch):
    with app.state.db.session() as session:
        user = session.scalar(select(User).where(User.username == 'admin'))
        assert user is not None
        token = create_access_token(
            'test-secret',
            str(user.id),
            user.role,
            'unexpected-error-csrf-token',
            30,
            session_version=user.session_version,
        )
        original_flush = session.flush
        failure_injected = False
        expected_error = IntegrityError(
            'INSERT INTO user_session_activity ...',
            {},
            RuntimeError('unexpected persistence failure'),
        )

        def fail_only_the_new_activity_insert(*args, **kwargs):
            nonlocal failure_injected
            if not failure_injected and any(
                isinstance(instance, UserSessionActivity) for instance in session.new
            ):
                failure_injected = True
                raise expected_error
            return original_flush(*args, **kwargs)

        monkeypatch.setattr(session, 'flush', fail_only_the_new_activity_insert)
        with pytest.raises(IntegrityError) as exc_info:
            auth_dependencies._record_session_activity(
                None,
                session,
                app.state.settings,
                user,
                token,
                {'exp': 2_000_000_000},
            )

        assert exc_info.value is expected_error
