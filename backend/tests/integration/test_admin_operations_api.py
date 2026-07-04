from __future__ import annotations
from app.core.security import hash_password
from app.modules.admin.models import UserPermission
from app.modules.auth.models import User


def _create_user(app, username: str, *, permission: str | None = None) -> None:
    with app.state.db.session() as session:
        user = User(username=username, password_hash=hash_password('password'), role='user', is_active=True)
        session.add(user)
        session.flush()
        if permission is not None:
            session.add(UserPermission(user_id=user.id, permission_key=permission))
        session.commit()




def test_admin_dashboard_modules_assets_and_backup(csrf_client) -> None:
    modules_response = csrf_client.get('/api/v1/admin/service-modules/public')
    assert modules_response.status_code == 200
    modules = modules_response.json()
    assert [module['key'] for module in modules][:3] == ['newsletter', 'civil-aircraft', 'document']
    assert any(module['key'] == 'open-notebook' and module['is_external'] for module in modules)

    summary_response = csrf_client.get('/api/v1/admin/dashboard')
    assert summary_response.status_code == 200
    summary = summary_response.json()
    assert summary['app_version'] == '1.9.0'
    assert summary['db_ok'] is True
    assert 'asset_health' in summary

    module_id = next(module['id'] for module in modules if module['key'] == 'announcement')
    update_response = csrf_client.patch(
        f'/api/v1/admin/service-modules/{module_id}',
        json={'is_enabled': True, 'status': 'development', 'badge': 'Active'},
    )
    assert update_response.status_code == 200
    assert update_response.json()['is_enabled'] is True

    audit_response = csrf_client.get('/api/v1/admin/audit-events')
    assert audit_response.status_code == 200
    assert any(event['action'] == 'service_module.update' for event in audit_response.json())

    health_response = csrf_client.get('/api/v1/admin/newsletters/assets/health')
    assert health_response.status_code == 200
    assert health_response.json()['ok'] >= 1

    backup_response = csrf_client.post('/api/v1/admin/backups')
    assert backup_response.status_code == 200
    backup = backup_response.json()
    assert backup['filename'].endswith('.zip')
    assert backup['sha256']
    validate_response = csrf_client.post(f"/api/v1/admin/backups/{backup['id']}/validate")
    assert validate_response.status_code == 200
    assert validate_response.json()['valid'] is True
    dry_run_response = csrf_client.post(f"/api/v1/admin/backups/{backup['id']}/restore/dry-run")
    assert dry_run_response.status_code == 200
    dry_run = dry_run_response.json()
    assert dry_run['valid'] is True
    assert dry_run['compatible'] is True
    assert 'sqlite_database' in dry_run['would_restore']


def test_admin_user_rbac_self_lockout_and_non_admin_forbidden(csrf_client) -> None:
    create_response = csrf_client.post(
        '/api/v1/admin/users',
        json={'username': 'operator', 'password': 'operator-password', 'role': 'user'},
    )
    assert create_response.status_code == 200
    user_id = create_response.json()['id']

    # The only seeded admin cannot remove its own admin capability.
    self_demote = csrf_client.patch('/api/v1/admin/users/1', json={'role': 'user'})
    assert self_demote.status_code == 400

    login_response = csrf_client.post('/api/v1/auth/login', json={'username': 'operator', 'password': 'operator-password'})
    assert login_response.status_code == 200
    forbidden = csrf_client.get('/api/v1/admin/users')
    assert forbidden.status_code == 403

    # Admin audit records the safe create path without exposing password material.
    admin_login = csrf_client.post('/api/v1/auth/login', json={'username': 'admin', 'password': 'password'})
    csrf_client.headers.update({'x-csrf-token': admin_login.json()['csrf_token']})
    reset_response = csrf_client.post(
        f'/api/v1/admin/users/{user_id}/password-reset',
        json={'temporary_password': 'new-operator-password'},
    )
    assert reset_response.status_code == 200
    audit_events = csrf_client.get('/api/v1/admin/audit-events').json()
    reset_events = [event for event in audit_events if event['action'] == 'user.password_reset']
    assert reset_events
    assert 'new-operator-password' not in (reset_events[0].get('metadata_json') or '')

def test_public_modules_hide_admin_only_for_anonymous(client) -> None:
    response = client.get('/api/v1/admin/service-modules/public')
    assert response.status_code == 200
    modules = response.json()
    keys = {module['key'] for module in modules}
    assert keys == {'newsletter', 'civil-aircraft', 'document', 'nsa'}
    assert all(module['visibility'] == 'public' for module in modules)
    assert 'ai' not in keys and 'announcement' not in keys


def test_operator_sees_admin_only_modules(csrf_client) -> None:
    response = csrf_client.get('/api/v1/admin/service-modules/public')
    assert response.status_code == 200
    keys = {module['key'] for module in response.json()}
    assert {'ai', 'announcement', 'open-notebook'} <= keys


def test_service_module_create_and_delete(csrf_client) -> None:
    create = csrf_client.post(
        '/api/v1/admin/service-modules',
        json={'key': 'labs', 'title': 'Labs', 'section': 'Development', 'status': 'development', 'visibility': 'admin'},
    )
    assert create.status_code == 201
    created = create.json()
    assert created['visibility'] == 'admin'
    module_id = created['id']

    duplicate = csrf_client.post('/api/v1/admin/service-modules', json={'key': 'labs', 'title': 'Dup'})
    assert duplicate.status_code == 409

    delete = csrf_client.delete(f'/api/v1/admin/service-modules/{module_id}')
    assert delete.status_code == 204

    actions = {event['action'] for event in csrf_client.get('/api/v1/admin/audit-events').json()}
    assert 'service_module.create' in actions
    assert 'service_module.delete' in actions


def test_self_password_change_rotates_credentials(csrf_client) -> None:
    change = csrf_client.post(
        '/api/v1/auth/change-password',
        json={'current_password': 'password', 'new_password': 'new-admin-password'},
    )
    assert change.status_code == 200
    assert change.json()['csrf_token']

    old_login = csrf_client.post('/api/v1/auth/login', json={'username': 'admin', 'password': 'password'})
    assert old_login.status_code == 401
    new_login = csrf_client.post('/api/v1/auth/login', json={'username': 'admin', 'password': 'new-admin-password'})
    assert new_login.status_code == 200

    audit_actions = {event['action'] for event in csrf_client.get('/api/v1/admin/audit-events').json()}
    assert 'account.password_change' in audit_actions


def test_unified_search_include_nsa_uses_collection_policy(client, app, test_paths) -> None:
    (test_paths['document_root'] / 'public.html').write_text('<html><body>SharedSearchToken document</body></html>', encoding='utf-8')
    (test_paths['nsa_root'] / 'secret.html').write_text('<html><body>SharedSearchToken nsa</body></html>', encoding='utf-8')

    _create_user(app, 'plain')
    plain_login = client.post('/api/v1/auth/login', json={'username': 'plain', 'password': 'password'})
    assert plain_login.status_code == 200
    plain_response = client.get('/api/v1/admin/search', params={'q': 'SharedSearchToken', 'include_nsa': 'true'})
    assert plain_response.status_code == 200
    assert {item['source'] for item in plain_response.json()['results']} == {'document'}

    admin_login = client.post('/api/v1/auth/login', json={'username': 'admin', 'password': 'password'})
    assert admin_login.status_code == 200
    admin_response = client.get('/api/v1/admin/search', params={'q': 'SharedSearchToken', 'include_nsa': 'true'})
    assert admin_response.status_code == 200
    assert {'document', 'nsa'} <= {item['source'] for item in admin_response.json()['results']}

    _create_user(app, 'nsa-user', permission='collections.nsa.read')
    nsa_login = client.post('/api/v1/auth/login', json={'username': 'nsa-user', 'password': 'password'})
    assert nsa_login.status_code == 200
    nsa_response = client.get('/api/v1/admin/search', params={'q': 'SharedSearchToken', 'include_nsa': 'true'})
    assert nsa_response.status_code == 200
    assert {'document', 'nsa'} <= {item['source'] for item in nsa_response.json()['results']}
