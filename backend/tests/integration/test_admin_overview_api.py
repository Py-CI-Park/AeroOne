from __future__ import annotations

from datetime import UTC, datetime, timedelta
import pytest

from app.core.security import hash_password
from app.modules.admin.models import AdminAuditEvent, AiRequestLog, LoginEvent, ServiceModule
from app.modules.admin.overview_service import build_overview
from app.modules.auth.models import User

FIXED_NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)

_FORBIDDEN_KEYS = {
    'database_url',
    'ip_address',
    'user_agent',
    'metadata',
    'metadata_json',
    'actor_user_id',
    'actor_username',
    'actor_role',
    'before_json',
    'after_json',
    'request_id',
    'target_id',
    'session_hash',
}


def _scan_forbidden_keys(payload: object) -> set[str]:
    found: set[str] = set()
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in _FORBIDDEN_KEYS:
                found.add(key)
            found |= _scan_forbidden_keys(value)
    elif isinstance(payload, list):
        for item in payload:
            found |= _scan_forbidden_keys(item)
    return found


def test_overview_login_window_boundaries_are_inclusive_of_current_start(app, settings) -> None:
    with app.state.db.session() as session:
        session.add(LoginEvent(username='exact-current', status='success', created_at=FIXED_NOW - timedelta(hours=24)))
        session.add(LoginEvent(username='exact-prior', status='success', created_at=FIXED_NOW - timedelta(hours=48)))
        session.add(LoginEvent(username='too-old', status='success', created_at=FIXED_NOW - timedelta(hours=48, seconds=1)))
        session.commit()

        overview = build_overview(session, settings, now=FIXED_NOW)

    assert overview['logins']['success'] == {'current': 1, 'prior': 1, 'delta': 0}


def test_overview_login_window_boundary_excludes_now_itself(app, settings) -> None:
    with app.state.db.session() as session:
        session.add(LoginEvent(username='at-now', status='failure', created_at=FIXED_NOW))
        session.commit()

        overview = build_overview(session, settings, now=FIXED_NOW)

    # the current window is [now-24h, now); an event exactly at `now` is excluded.
    assert overview['logins']['failure'] == {'current': 0, 'prior': 0, 'delta': 0}


def test_overview_ai_failure_window_and_delta(app, settings) -> None:
    with app.state.db.session() as session:
        for idx in range(3):
            session.add(AiRequestLog(request_id=f'req-current-{idx}', model='gpt', status='error', created_at=FIXED_NOW - timedelta(hours=1)))
        session.add(AiRequestLog(request_id='req-prior-0', model='gpt', status='error', created_at=FIXED_NOW - timedelta(hours=30)))
        session.add(AiRequestLog(request_id='req-ok', model='gpt', status='ok', created_at=FIXED_NOW - timedelta(hours=1)))
        session.commit()

        overview = build_overview(session, settings, now=FIXED_NOW)

    assert overview['ai']['failure'] == {'current': 3, 'prior': 1, 'delta': 2}
    assert overview['ai']['total']['current'] == 4
    assert overview['ai']['total']['prior'] == 1


def test_overview_rejects_unknown_stored_roles(app, settings) -> None:
    with app.state.db.session() as session:
        session.add(User(username='role-user', password_hash=hash_password('password'), role='user', is_active=True))
        session.add(User(username='role-weird', password_hash=hash_password('password'), role='operator', is_active=True))
        session.commit()

        with pytest.raises(ValueError, match='Unsupported stored user role'):
            build_overview(session, settings, now=FIXED_NOW)


def test_overview_module_buckets_are_disjoint_and_sum_to_total(app, settings) -> None:
    with app.state.db.session() as session:
        session.add(ServiceModule(key='m-disabled', title='Disabled', href='#', section='Test', status='active', is_enabled=False, visibility='public'))
        session.add(ServiceModule(key='m-coming', title='Coming', href='#', section='Test', status='coming_soon', is_enabled=True, visibility='public'))
        session.add(ServiceModule(key='m-dev', title='Dev', href='#', section='Test', status='development', is_enabled=True, visibility='public'))
        session.add(ServiceModule(key='m-active', title='Active', href='#', section='Test', status='active', is_enabled=True, visibility='public'))
        session.commit()

        overview = build_overview(session, settings, now=FIXED_NOW)

    buckets = overview['modules']['buckets']
    total_in_buckets = sum(len(buckets[name]) for name in ('unavailable', 'coming', 'development', 'active'))
    assert total_in_buckets == overview['modules']['total']
    keys_seen: list[str] = []
    for name in ('unavailable', 'coming', 'development', 'active'):
        keys_seen.extend(ref['key'] for ref in buckets[name])
    assert len(keys_seen) == len(set(keys_seen))
    assert 'm-disabled' in {ref['key'] for ref in buckets['unavailable']}
    assert 'm-coming' in {ref['key'] for ref in buckets['coming']}
    assert 'm-dev' in {ref['key'] for ref in buckets['development']}
    assert 'm-active' in {ref['key'] for ref in buckets['active']}


def test_overview_database_kind_never_contains_url(app, settings) -> None:
    with app.state.db.session() as session:
        overview = build_overview(session, settings, now=FIXED_NOW)
    assert '://' not in overview['system']['database_kind']
    assert overview['system']['database_kind'] == 'sqlite'


def test_overview_recent_audit_field_allowlist(app, settings) -> None:
    with app.state.db.session() as session:
        session.add(
            AdminAuditEvent(
                actor_user_id=1,
                actor_username='admin',
                actor_role='admin',
                action='service_module.update',
                target_type='service_module',
                target_id='nsa',
                status='success',
                ip_address='127.0.0.1',
                user_agent='pytest',
                request_id='req-1',
                before_json='{}',
                after_json='{}',
                metadata_json='{}',
            )
        )
        session.commit()

        overview = build_overview(session, settings, now=FIXED_NOW)

    assert len(overview['recent_audit']) >= 1
    for entry in overview['recent_audit']:
        assert set(entry.keys()) == {'id', 'action', 'target_type', 'status', 'created_at'}


def test_overview_api_endpoint_response_has_no_forbidden_keys(csrf_client) -> None:
    response = csrf_client.get('/api/v1/admin/overview')
    assert response.status_code == 200
    payload = response.json()
    assert _scan_forbidden_keys(payload) == set()
    assert set(payload.keys()) == {
        'generated_at',
        'anchor',
        'users',
        'logins',
        'ai',
        'sessions',
        'modules',
        'system',
        'recent_audit',
    }
    assert payload['sessions'].keys() == {'active_session_count', 'active_user_count', 'active_count'}


def test_overview_dashboard_route_removed(csrf_client) -> None:
    assert csrf_client.get('/api/v1/admin/dashboard').status_code == 404
