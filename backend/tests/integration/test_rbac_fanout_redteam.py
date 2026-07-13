from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.modules.admin.models import UserPermission
from app.modules.admin.permissions import has_permission
from app.modules.auth.models import User
from app.modules.collections.policy import can_read_collection


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


def _login_client(app, username: str) -> TestClient:
    actor = TestClient(app)
    response = actor.post('/api/v1/auth/login', json={'username': username, 'password': 'password'})
    assert response.status_code == 200
    return actor


def _assert_session_expired(client: TestClient) -> None:
    response = client.get('/api/v1/auth/effective-permissions')
    assert response.status_code == 401
    assert response.json()['detail'] == 'Session expired'


def _assert_fresh_permissions(app, username: str, *, has_perm: str | None = None, nsa_readable: bool | None = None) -> None:
    fresh = _login_client(app, username)
    response = fresh.get('/api/v1/auth/effective-permissions')
    assert response.status_code == 200
    payload = response.json()
    if has_perm is not None:
        assert has_perm in payload['permissions']
    if nsa_readable is not None:
        nsa = fresh.get('/api/v1/collections/nsa/list')
        assert nsa.status_code == (200 if nsa_readable else 403)


def _create_group(csrf_client, *, key: str, permissions: list[str], is_active: bool = True) -> dict:
    response = csrf_client.post('/api/v1/admin/groups', json={'key': key, 'name': key, 'is_active': is_active, 'permissions': permissions})
    assert response.status_code == 200
    return response.json()


def test_resource_grant_allows_collection_without_global_admin_escalation(csrf_client, app) -> None:
    user_id = _make_user(app, 'grant-not-global')
    response = csrf_client.post(
        '/api/v1/admin/resource-grants',
        json={
            'subject_type': 'user',
            'subject_id': user_id,
            'resource_type': 'collection',
            'resource_id': 'nsa',
            'permission_key': 'collections.nsa.read',
        },
    )
    assert response.status_code == 201

    with app.state.db.session() as session:
        user = session.get(User, user_id)
        assert has_permission(session, user, 'admin.users.manage') is False
        assert has_permission(session, user, 'admin.resource_grants.manage') is False
        assert can_read_collection(session, user, 'nsa') is True

    actor = _login_client(app, 'grant-not-global')
    assert actor.get('/api/v1/admin/users').status_code == 403
    assert actor.get('/api/v1/collections/nsa/list').status_code == 200


def test_resource_grant_mutations_require_manage_permission_and_csrf(client, csrf_client, app) -> None:
    subject_id = _make_user(app, 'resource-crud-subject')
    reader_id = _make_user(app, 'resource-reader-only', permissions=['admin.resource_grants.read'])
    payload = {
        'subject_type': 'user',
        'subject_id': subject_id,
        'resource_type': 'collection',
        'resource_id': 'nsa',
        'permission_key': 'collections.nsa.read',
    }

    plain = _login_client(app, 'resource-crud-subject')
    assert plain.post('/api/v1/admin/resource-grants', json=payload).status_code == 403
    assert plain.delete('/api/v1/admin/resource-grants/1').status_code == 403

    reader = _login_client(app, 'resource-reader-only')
    assert reader.get('/api/v1/admin/resource-grants', params={'subject_type': 'user', 'subject_id': reader_id}).status_code == 200
    assert reader.post('/api/v1/admin/resource-grants', json=payload).status_code == 403
    assert reader.delete('/api/v1/admin/resource-grants/1').status_code == 403

    missing_csrf_admin = TestClient(app)
    login = missing_csrf_admin.post('/api/v1/auth/login', json={'username': 'admin', 'password': 'password'})
    assert login.status_code == 200
    assert missing_csrf_admin.post('/api/v1/admin/resource-grants', json=payload).status_code == 403

    created = csrf_client.post('/api/v1/admin/resource-grants', json=payload)
    assert created.status_code == 201
    assert missing_csrf_admin.delete(f"/api/v1/admin/resource-grants/{created.json()['id']}").status_code == 403


def test_stale_session_rejected_after_direct_permission_group_membership_resource_grant_and_role_changes(csrf_client, app) -> None:
    direct_id = _make_user(app, 'stale-direct')
    direct_old = _login_client(app, 'stale-direct')
    assert csrf_client.patch(f'/api/v1/admin/users/{direct_id}', json={'permissions': ['search.use']}).status_code == 200
    _assert_session_expired(direct_old)
    _assert_fresh_permissions(app, 'stale-direct', has_perm='search.use')

    group_id_user = _make_user(app, 'stale-group-add')
    group = _create_group(csrf_client, key='stale-group-adders', permissions=['admin.newsletters.read'])
    group_old = _login_client(app, 'stale-group-add')
    assert csrf_client.post(f"/api/v1/admin/users/{group_id_user}/groups/{group['id']}").status_code == 200
    _assert_session_expired(group_old)
    _assert_fresh_permissions(app, 'stale-group-add', has_perm='admin.newsletters.read')

    grant_user = _make_user(app, 'stale-grant-create')
    grant_old = _login_client(app, 'stale-grant-create')
    create_grant = csrf_client.post(
        '/api/v1/admin/resource-grants',
        json={'subject_type': 'user', 'subject_id': grant_user, 'resource_type': 'collection', 'resource_id': 'nsa', 'permission_key': 'collections.nsa.read'},
    )
    assert create_grant.status_code == 201
    _assert_session_expired(grant_old)
    _assert_fresh_permissions(app, 'stale-grant-create', nsa_readable=True)

    inactive_user = _make_user(app, 'stale-group-inactive')
    inactive_group = _create_group(csrf_client, key='stale-inactive-group', permissions=['admin.newsletters.read'])
    assert csrf_client.post(f"/api/v1/admin/users/{inactive_user}/groups/{inactive_group['id']}").status_code == 200
    inactive_old = _login_client(app, 'stale-group-inactive')
    assert csrf_client.post('/api/v1/admin/groups', json={'key': 'stale-inactive-group', 'name': 'stale-inactive-group', 'is_active': False, 'permissions': ['admin.newsletters.read']}).status_code == 200
    _assert_session_expired(inactive_old)
    fresh_inactive = _login_client(app, 'stale-group-inactive')
    assert 'admin.newsletters.read' not in fresh_inactive.get('/api/v1/auth/effective-permissions').json()['permissions']

    role_user = _make_user(app, 'stale-role')
    role_old = _login_client(app, 'stale-role')
    assert csrf_client.patch(f'/api/v1/admin/users/{role_user}', json={'role': 'pending'}).status_code == 200
    _assert_session_expired(role_old)
    fresh_role = _login_client(app, 'stale-role')
    assert fresh_role.get('/api/v1/auth/effective-permissions').status_code == 200


def test_stale_session_rejected_after_resource_grant_delete_and_group_membership_remove(csrf_client, app) -> None:
    grant_user = _make_user(app, 'stale-grant-delete')
    grant = csrf_client.post(
        '/api/v1/admin/resource-grants',
        json={'subject_type': 'user', 'subject_id': grant_user, 'resource_type': 'collection', 'resource_id': 'nsa', 'permission_key': 'collections.nsa.read'},
    )
    assert grant.status_code == 201
    grant_old = _login_client(app, 'stale-grant-delete')
    assert grant_old.get('/api/v1/collections/nsa/list').status_code == 200
    assert csrf_client.delete(f"/api/v1/admin/resource-grants/{grant.json()['id']}").status_code == 204
    _assert_session_expired(grant_old)
    _assert_fresh_permissions(app, 'stale-grant-delete', nsa_readable=False)

    member_user = _make_user(app, 'stale-group-remove')
    group = _create_group(csrf_client, key='stale-removers', permissions=['admin.newsletters.read'])
    assert csrf_client.post(f"/api/v1/admin/users/{member_user}/groups/{group['id']}").status_code == 200
    member_old = _login_client(app, 'stale-group-remove')
    assert 'admin.newsletters.read' in member_old.get('/api/v1/auth/effective-permissions').json()['permissions']
    assert csrf_client.delete(f"/api/v1/admin/users/{member_user}/groups/{group['id']}").status_code == 200
    _assert_session_expired(member_old)
    fresh_member = _login_client(app, 'stale-group-remove')
    assert 'admin.newsletters.read' not in fresh_member.get('/api/v1/auth/effective-permissions').json()['permissions']


def test_rbac_matrix_admin_only_and_source_labels(csrf_client, app) -> None:
    _make_user(app, 'matrix-denied')
    denied = _login_client(app, 'matrix-denied')
    assert denied.get('/api/v1/admin/rbac-matrix').status_code == 403

    user_id = _make_user(app, 'redteam-matrix-user', permissions=['search.use'])
    group = _create_group(csrf_client, key='redteam-matrix-group', permissions=['collections.nsa.read'])
    assert csrf_client.post(f"/api/v1/admin/users/{user_id}/groups/{group['id']}").status_code == 200
    grant = csrf_client.post(
        '/api/v1/admin/resource-grants',
        json={'subject_type': 'user', 'subject_id': user_id, 'resource_type': 'collection', 'resource_id': 'nsa', 'permission_key': 'collections.nsa.read'},
    )
    assert grant.status_code == 201

    response = csrf_client.get('/api/v1/admin/rbac-matrix')
    assert response.status_code == 200
    row = next(item for item in response.json() if item['user_id'] == user_id)
    assert 'ai.use' in row['role_permissions']
    assert row['direct_permissions'] == ['search.use']
    assert {'group': 'redteam-matrix-group', 'key': 'collections.nsa.read'} in row['group_permissions']
    effective = {item['key']: set(item['sources']) for item in row['effective_permissions']}
    assert 'role:user' in effective['ai.use']
    assert 'direct' in effective['search.use']
    assert 'group:redteam-matrix-group' in effective['collections.nsa.read']
    assert {'resource_type': 'collection', 'resource_id': 'nsa', 'permission_key': 'collections.nsa.read', 'source': 'user'} in row['resource_grants']


def test_resource_grant_duplicate_create_returns_409(csrf_client, app) -> None:
    user_id = _make_user(app, 'duplicate-grant')
    payload = {'subject_type': 'user', 'subject_id': user_id, 'resource_type': 'collection', 'resource_id': 'nsa', 'permission_key': 'collections.nsa.read'}
    assert csrf_client.post('/api/v1/admin/resource-grants', json=payload).status_code == 201
    duplicate = csrf_client.post('/api/v1/admin/resource-grants', json=payload)
    assert duplicate.status_code == 409


def test_public_self_registration_routes_do_not_exist(client) -> None:
    payload = {'username': 'new-user', 'password': 'password'}
    for route in ('/api/v1/auth/register', '/api/v1/register', '/api/v1/users/register', '/api/v1/signup'):
        assert client.post(route, json=payload).status_code in {404, 405}
