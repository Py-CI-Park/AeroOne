from __future__ import annotations

import pytest
from app.core.security import hash_password
from app.modules.admin.models import UserPermission
from app.modules.auth.models import User


def _make_user(app, username: str, *, role: str = 'user', permissions: list[str] | None = None) -> int:
    with app.state.db.session() as session:
        user = User(username=username, password_hash=hash_password('password'), role=role, is_active=True)
        session.add(user)
        session.flush()
        for key in permissions or []:
            session.add(UserPermission(user_id=user.id, permission_key=key))
        user_id = user.id
        session.commit()
        return user_id


def _session_version(app, user_id: int) -> int:
    with app.state.db.session() as session:
        return session.get(User, user_id).session_version


def _create_group(csrf_client, *, key: str = 'nsa-readers', permissions: list[str] | None = None) -> dict:
    response = csrf_client.post('/api/v1/admin/groups', json={'key': key, 'name': key, 'is_active': True, 'permissions': permissions or ['collections.nsa.read']})
    assert response.status_code == 200
    return response.json()


def test_resource_grant_crud_is_permission_csrf_gated_audited_and_bumps_sessions(csrf_client, client, app) -> None:
    user_id = _make_user(app, 'resource-subject')
    payload = {'subject_type': 'user', 'subject_id': user_id, 'resource_type': 'collection', 'resource_id': 'nsa', 'permission_key': 'collections.nsa.read'}

    client.headers.pop('x-csrf-token', None)
    login = client.post('/api/v1/auth/login', json={'username': 'admin', 'password': 'password'})
    assert login.status_code == 200
    no_csrf = client.post('/api/v1/admin/resource-grants', json=payload)
    assert no_csrf.status_code == 403
    client.headers.update({'x-csrf-token': login.json()['csrf_token']})

    before = _session_version(app, user_id)
    create = csrf_client.post('/api/v1/admin/resource-grants', json=payload)
    assert create.status_code == 201
    grant = create.json()
    assert grant['subject_type'] == 'user'
    assert _session_version(app, user_id) == before + 1
    duplicate = csrf_client.post('/api/v1/admin/resource-grants', json=payload)
    assert duplicate.status_code == 409
    missing = csrf_client.post('/api/v1/admin/resource-grants', json={**payload, 'subject_id': 99999})
    assert missing.status_code == 404

    listed = csrf_client.get('/api/v1/admin/resource-grants', params={'subject_type': 'user', 'subject_id': user_id})
    assert listed.status_code == 200
    assert [item['id'] for item in listed.json()] == [grant['id']]

    before_delete = _session_version(app, user_id)
    delete = csrf_client.delete(f"/api/v1/admin/resource-grants/{grant['id']}")
    assert delete.status_code == 204
    assert _session_version(app, user_id) == before_delete + 1
    actions = {event['action'] for event in csrf_client.get('/api/v1/admin/audit-events').json()}
    assert {'resource_grant.create', 'resource_grant.delete'} <= actions


def test_rbac_matrix_source_labels_for_role_direct_group_and_resource_grants(csrf_client, app) -> None:
    user_id = _make_user(app, 'matrix-user', permissions=['search.use'])
    group = _create_group(csrf_client, key='matrix-group', permissions=['collections.nsa.read'])
    assert csrf_client.post(f"/api/v1/admin/users/{user_id}/groups/{group['id']}").status_code == 200
    assert csrf_client.post('/api/v1/admin/resource-grants', json={'subject_type': 'user', 'subject_id': user_id, 'resource_type': 'collection', 'resource_id': 'nsa', 'permission_key': 'collections.nsa.read'}).status_code == 201
    assert csrf_client.post('/api/v1/admin/resource-grants', json={'subject_type': 'group', 'subject_id': group['id'], 'resource_type': 'collection', 'resource_id': 'engineering', 'permission_key': 'collections.read'}).status_code == 201

    response = csrf_client.get('/api/v1/admin/rbac-matrix')
    assert response.status_code == 200
    row = next(item for item in response.json() if item['user_id'] == user_id)
    assert 'ai.use' in row['role_permissions']
    assert row['direct_permissions'] == ['search.use']
    assert {'group': 'matrix-group', 'key': 'collections.nsa.read'} in row['group_permissions']
    effective = {item['key']: set(item['sources']) for item in row['effective_permissions']}
    assert 'role:user' in effective['ai.use']
    assert 'direct' in effective['search.use']
    assert 'group:matrix-group' in effective['collections.nsa.read']
    assert {'resource_type': 'collection', 'resource_id': 'nsa', 'permission_key': 'collections.nsa.read', 'source': 'user'} in row['resource_grants']
    assert {'resource_type': 'collection', 'resource_id': 'engineering', 'permission_key': 'collections.read', 'source': 'group:matrix-group'} in row['resource_grants']


def test_session_version_fanout_for_authorization_changes(csrf_client, app) -> None:
    user_id = _make_user(app, 'fanout-user')
    assert csrf_client.patch(f'/api/v1/admin/users/{user_id}', json={'permissions': ['search.use']}).status_code == 200
    assert _session_version(app, user_id) == 1
    assert csrf_client.patch(f'/api/v1/admin/users/{user_id}', json={'role': 'pending'}).status_code == 200
    assert _session_version(app, user_id) == 2

    group = _create_group(csrf_client, key='fanout-group', permissions=['ai.use'])
    assert csrf_client.post(f"/api/v1/admin/users/{user_id}/groups/{group['id']}").status_code == 200
    assert _session_version(app, user_id) == 3
    assert csrf_client.post('/api/v1/admin/groups', json={'key': 'fanout-group', 'name': 'fanout-group', 'is_active': False, 'permissions': ['ai.use']}).status_code == 200
    assert _session_version(app, user_id) == 4
    assert csrf_client.post('/api/v1/admin/groups', json={'key': 'fanout-group', 'name': 'fanout-group', 'is_active': True, 'permissions': ['search.use']}).status_code == 200
    assert _session_version(app, user_id) == 5
    create_grant = csrf_client.post('/api/v1/admin/resource-grants', json={'subject_type': 'group', 'subject_id': group['id'], 'resource_type': 'collection', 'resource_id': 'nsa', 'permission_key': 'collections.nsa.read'})
    assert create_grant.status_code == 201
    assert _session_version(app, user_id) == 6
    delete_grant = csrf_client.delete(f"/api/v1/admin/resource-grants/{create_grant.json()['id']}")
    assert delete_grant.status_code == 204
    assert _session_version(app, user_id) == 7
    assert csrf_client.delete(f"/api/v1/admin/users/{user_id}/groups/{group['id']}").status_code == 200
    assert _session_version(app, user_id) == 8


def test_rbac_matrix_rejects_unknown_stored_roles(csrf_client, app) -> None:
    _make_user(app, 'invalid-role-user', role='operator')
    with pytest.raises(ValueError, match='Unsupported stored user role'):
        csrf_client.get('/api/v1/admin/rbac-matrix')
def test_self_registration_route_does_not_exist(client) -> None:
    assert client.post('/api/v1/auth/register', json={'username': 'new', 'password': 'password'}).status_code == 404
    assert client.post('/api/v1/register', json={'username': 'new', 'password': 'password'}).status_code == 404
