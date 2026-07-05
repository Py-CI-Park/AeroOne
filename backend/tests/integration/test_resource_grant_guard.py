from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.security import hash_password
from app.modules.admin.models import AdminAuditEvent, ResourceGrant
from app.modules.admin.permissions import has_permission, has_resource_permission
from app.modules.auth.models import User


def _make_user(app, username: str, *, role: str = 'user') -> int:
    with app.state.db.session() as session:
        user = User(username=username, password_hash=hash_password('password'), role=role, is_active=True)
        session.add(user)
        session.flush()
        user_id = user.id
        session.commit()
        return user_id


def _session_version(app, user_id: int) -> int:
    with app.state.db.session() as session:
        return session.get(User, user_id).session_version


def _resource_grant_count(app) -> int:
    with app.state.db.session() as session:
        return session.scalar(select(func.count(ResourceGrant.id))) or 0


def _audit_count(app) -> int:
    with app.state.db.session() as session:
        return session.scalar(select(func.count(AdminAuditEvent.id))) or 0


def _assert_rejected_without_side_effects(csrf_client, app, payload: dict) -> None:
    before_version = _session_version(app, payload['subject_id'])
    before_grants = _resource_grant_count(app)
    before_audits = _audit_count(app)

    response = csrf_client.post('/api/v1/admin/resource-grants', json=payload)

    assert response.status_code in {400, 422}
    assert _resource_grant_count(app) == before_grants
    assert _audit_count(app) == before_audits
    assert _session_version(app, payload['subject_id']) == before_version


def _payload(user_id: int, **overrides) -> dict:
    payload = {
        'subject_type': 'user',
        'subject_id': user_id,
        'resource_type': 'collection',
        'resource_id': 'nsa',
        'permission_key': 'collections.nsa.read',
    }
    payload.update(overrides)
    return payload


@pytest.mark.parametrize('permission_key', ['admin.users.manage', 'admin.rbac.manage', 'admin.not_a_real_permission'])
def test_resource_grant_rejects_unsafe_unknown_permission_without_side_effects(csrf_client, app, permission_key: str) -> None:
    user_id = _make_user(app, f'guard-permission-{permission_key.replace(".", "-")}')

    _assert_rejected_without_side_effects(csrf_client, app, _payload(user_id, permission_key=permission_key))


@pytest.mark.parametrize('resource_type', ['global', 'user', ''])
def test_resource_grant_rejects_invalid_resource_type_without_side_effects(csrf_client, app, resource_type: str) -> None:
    user_id = _make_user(app, f'guard-resource-type-{resource_type or "blank"}')

    _assert_rejected_without_side_effects(csrf_client, app, _payload(user_id, resource_type=resource_type))


@pytest.mark.parametrize('resource_id', ['', '   ', '*', '../nsa', 'nsa/foo', 'nsa\\foo', 'n' * 201, 'nsa\nfoo', 'nsa\x1ffoo', 'nsa\x7ffoo'])
def test_resource_grant_rejects_malformed_resource_id_without_side_effects(csrf_client, app, resource_id: str) -> None:
    user_id = _make_user(app, f'guard-resource-id-{len(resource_id)}-{abs(hash(resource_id))}')

    _assert_rejected_without_side_effects(csrf_client, app, _payload(user_id, resource_id=resource_id))


def test_resource_grant_valid_collection_grant_still_audits_fans_out_and_requires_csrf(client, csrf_client, app) -> None:
    user_id = _make_user(app, 'guard-valid-grant')
    payload = _payload(user_id)

    no_csrf_admin = TestClient(app)
    login = no_csrf_admin.post('/api/v1/auth/login', json={'username': 'admin', 'password': 'password'})
    assert login.status_code == 200
    assert no_csrf_admin.post('/api/v1/admin/resource-grants', json=payload).status_code == 403
    assert _resource_grant_count(app) == 0
    assert _audit_count(app) == 0
    assert _session_version(app, user_id) == 0

    response = csrf_client.post('/api/v1/admin/resource-grants', json=payload)

    assert response.status_code == 201
    grant = response.json()
    assert grant['resource_type'] == 'collection'
    assert grant['resource_id'] == 'nsa'
    assert grant['permission_key'] == 'collections.nsa.read'
    assert _resource_grant_count(app) == 1
    assert _audit_count(app) == 1
    assert _session_version(app, user_id) == 1

    with app.state.db.session() as session:
        user = session.get(User, user_id)
        assert user is not None
        assert has_permission(session, user, 'admin.users.manage') is False
        assert has_permission(session, user, 'admin.rbac.manage') is False
        assert has_resource_permission(session, user, 'collection', 'nsa', 'collections.nsa.read') is True
