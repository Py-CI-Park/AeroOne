from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.modules.admin.models import ResourceGrant, UserPermission
from app.modules.auth.models import User


ENDPOINT = '/api/v1/auth/effective-permissions'


def _create_user(app, username: str, *, role: str = 'user', is_active: bool = True) -> int:
    with app.state.db.session() as session:
        user = User(
            username=username,
            password_hash=hash_password('password'),
            role=role,
            is_active=is_active,
        )
        session.add(user)
        session.flush()
        user_id = user.id
        session.commit()
    return user_id


def _login(client: TestClient, username: str) -> str:
    response = client.post('/api/v1/auth/login', json={'username': username, 'password': 'password'})
    assert response.status_code == 200
    return response.json()['csrf_token']


def _resource(resource_id: str, permission_key: str = 'collections.nsa.read') -> dict[str, str]:
    return {
        'resource_type': 'collection',
        'resource_id': resource_id,
        'permission_key': permission_key,
    }


def test_effective_permissions_rejects_anonymous_user(client: TestClient) -> None:
    response = client.get(ENDPOINT)

    assert response.status_code == 401


def test_plain_user_sees_only_role_defaults_not_admin_permissions(client: TestClient, app) -> None:
    _create_user(app, 'plain-user')
    _login(client, 'plain-user')

    response = client.get(ENDPOINT)

    assert response.status_code == 200
    payload = response.json()
    assert set(payload['permissions']) == {'search.use', 'ai.use', 'ai.history.manage_own'}
    assert 'admin.users.manage' not in payload['permissions']
    assert 'admin.users.read' not in payload['permissions']
    assert payload['resources'] == []


def test_direct_resource_grant_does_not_leak_other_users_grants(client: TestClient, app) -> None:
    user_a_id = _create_user(app, 'grant-user-a')
    user_b_id = _create_user(app, 'grant-user-b')
    with app.state.db.session() as session:
        session.add_all(
            [
                ResourceGrant(
                    subject_type='user',
                    subject_id=user_a_id,
                    resource_type='collection',
                    resource_id='a-private',
                    permission_key='collections.nsa.read',
                ),
                ResourceGrant(
                    subject_type='user',
                    subject_id=user_b_id,
                    resource_type='collection',
                    resource_id='b-private',
                    permission_key='collections.nsa.read',
                ),
            ]
        )
        session.commit()
    _login(client, 'grant-user-a')

    response = client.get(ENDPOINT)

    assert response.status_code == 200
    payload = response.json()
    assert _resource('a-private') in payload['resources']
    assert _resource('b-private') not in payload['resources']


def test_effective_permissions_is_read_only_and_does_not_enable_admin_access(client: TestClient, app) -> None:
    user_id = _create_user(app, 'read-only-user')
    with app.state.db.session() as session:
        session.add(UserPermission(user_id=user_id, permission_key='admin.users.read'))
        session.commit()
    csrf_token = _login(client, 'read-only-user')

    before = client.get(ENDPOINT)
    assert before.status_code == 200

    for _ in range(2):
        response = client.get(ENDPOINT)
        assert response.status_code == 200
        assert response.json() == before.json()

    denied = client.post(
        '/api/v1/admin/users',
        json={'username': 'should-not-exist', 'password': 'password', 'role': 'user'},
        headers={'x-csrf-token': csrf_token},
    )
    after = client.get(ENDPOINT)

    assert denied.status_code == 403
    assert after.status_code == 200
    assert after.json() == before.json()
    with app.state.db.session() as session:
        assert session.query(User).filter(User.username == 'should-not-exist').first() is None


def test_effective_permissions_rejects_inactive_user_even_with_grants(client: TestClient, app) -> None:
    user_id = _create_user(app, 'inactive-with-grants')
    _login(client, 'inactive-with-grants')
    with app.state.db.session() as session:
        user = session.get(User, user_id)
        assert user is not None
        user.is_active = False
        session.add(UserPermission(user_id=user_id, permission_key='admin.users.read'))
        session.add(
            ResourceGrant(
                subject_type='user',
                subject_id=user_id,
                resource_type='collection',
                resource_id='inactive-private',
                permission_key='collections.nsa.read',
            )
        )
        session.commit()

    response = client.get(ENDPOINT)

    assert response.status_code == 401
