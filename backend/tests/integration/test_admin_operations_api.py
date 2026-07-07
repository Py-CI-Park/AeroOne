from __future__ import annotations

import json

from app.core.config import reset_settings_cache
from app.core.security import hash_file_bytes, hash_password
from app.modules.newsletter.models.newsletter import AssetType, Newsletter, NewsletterAsset, SourceType
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
    assert summary['app_version'] == '1.12.1'
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


def test_admin_user_optional_profile_metadata(csrf_client) -> None:
    create_response = csrf_client.post(
        '/api/v1/admin/users',
        json={'username': 'profile-user', 'password': 'profile-password'},
    )
    assert create_response.status_code == 200
    created = create_response.json()
    assert created['username'] == 'profile-user'
    assert created['email'] is None
    assert created['display_name'] is None
    assert created['role'] == 'user'
    assert {'search.use', 'ai.use', 'ai.history.manage_own'} <= set(created['permissions'])

    update_response = csrf_client.patch(
        f"/api/v1/admin/users/{created['id']}",
        json={'display_name': 'Profile User', 'email': 'profile-user@example.test'},
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated['display_name'] == 'Profile User'
    assert updated['email'] == 'profile-user@example.test'
    assert updated['username'] == 'profile-user'
    assert updated['role'] == 'user'
    assert {'search.use', 'ai.use', 'ai.history.manage_own'} <= set(updated['permissions'])

    login_response = csrf_client.post('/api/v1/auth/login', json={'username': 'profile-user', 'password': 'profile-password'})
    assert login_response.status_code == 200
    admin_login = csrf_client.post('/api/v1/auth/login', json={'username': 'admin', 'password': 'password'})
    assert admin_login.status_code == 200
    csrf_client.headers.update({'x-csrf-token': admin_login.json()['csrf_token']})

    audit_events = csrf_client.get('/api/v1/admin/audit-events').json()
    create_event = next(event for event in audit_events if event['action'] == 'user.create' and event['target_id'] == str(created['id']))
    update_event = next(event for event in audit_events if event['action'] == 'user.update' and event['target_id'] == str(created['id']))
    create_after = json.loads(create_event['after_json'])
    update_before = json.loads(update_event['before_json'])
    update_after = json.loads(update_event['after_json'])
    assert create_after['display_name'] is None
    assert create_after['email'] is None
    assert update_before['display_name'] is None
    assert update_before['email'] is None
    assert update_after['display_name'] == 'Profile User'
    assert update_after['email'] == 'profile-user@example.test'

    clear_response = csrf_client.patch(
        f"/api/v1/admin/users/{created['id']}",
        json={'display_name': ' ', 'email': ''},
    )
    assert clear_response.status_code == 200
    cleared = clear_response.json()
    assert cleared['display_name'] is None
    assert cleared['email'] is None


def test_admin_user_create_rejects_blank_login_id_or_password(csrf_client) -> None:
    blank_username = csrf_client.post('/api/v1/admin/users', json={'username': '   ', 'password': 'profile-password'})
    assert blank_username.status_code == 400
    assert blank_username.json()['detail'] == 'username is required'

    blank_password = csrf_client.post('/api/v1/admin/users', json={'username': 'blank-password-user', 'password': '   '})
    assert blank_password.status_code == 400
    assert blank_password.json()['detail'] == 'password is required'

    trimmed_username = csrf_client.post('/api/v1/admin/users', json={'username': '  trimmed-user  ', 'password': 'trimmed-password'})
    assert trimmed_username.status_code == 200
    assert trimmed_username.json()['username'] == 'trimmed-user'


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

def test_public_modules_hide_admin_only_and_gated_for_anonymous(client) -> None:
    response = client.get('/api/v1/admin/service-modules/public')
    assert response.status_code == 200
    modules = response.json()
    keys = {module['key'] for module in modules}
    assert {'newsletter', 'civil-aircraft', 'document'} <= keys
    assert 'nsa' not in keys
    assert all(module['visibility'] == 'public' for module in modules)
    assert 'ai' not in keys and 'announcement' not in keys


def test_public_modules_include_nsa_for_direct_permission_user(client, app) -> None:
    _create_user(app, 'nsa-dashboard-user', permission='collections.nsa.read')
    login_response = client.post('/api/v1/auth/login', json={'username': 'nsa-dashboard-user', 'password': 'password'})
    assert login_response.status_code == 200

    response = client.get('/api/v1/admin/service-modules/public')
    assert response.status_code == 200
    keys = {module['key'] for module in response.json()}
    assert {'newsletter', 'civil-aircraft', 'document', 'nsa'} <= keys



def test_service_module_activation_patch_is_audited_and_changes_public_visibility(csrf_client, app) -> None:
    _create_user(app, 'plain-module-user')
    plain_login = csrf_client.post('/api/v1/auth/login', json={'username': 'plain-module-user', 'password': 'password'})
    assert plain_login.status_code == 200
    before_response = csrf_client.get('/api/v1/admin/service-modules/public')
    assert before_response.status_code == 200
    assert 'nsa' not in {module['key'] for module in before_response.json()}

    admin_login = csrf_client.post('/api/v1/auth/login', json={'username': 'admin', 'password': 'password'})
    assert admin_login.status_code == 200
    csrf_client.headers.update({'x-csrf-token': admin_login.json()['csrf_token']})
    modules_response = csrf_client.get('/api/v1/admin/service-modules')
    assert modules_response.status_code == 200
    nsa_module = next(module for module in modules_response.json() if module['key'] == 'nsa')

    update_response = csrf_client.patch(
        f"/api/v1/admin/service-modules/{nsa_module['id']}",
        json={'required_permission': None, 'resource_type': None, 'resource_id': None},
    )
    assert update_response.status_code == 200
    assert update_response.json()['required_permission'] is None

    audit_response = csrf_client.get('/api/v1/admin/audit-events')
    assert audit_response.status_code == 200
    assert any(event['action'] == 'service_module.update' for event in audit_response.json())

    plain_login = csrf_client.post('/api/v1/auth/login', json={'username': 'plain-module-user', 'password': 'password'})
    assert plain_login.status_code == 200
    after_response = csrf_client.get('/api/v1/admin/service-modules/public')
    assert after_response.status_code == 200
    assert 'nsa' in {module['key'] for module in after_response.json()}

def test_operator_sees_admin_only_modules(csrf_client) -> None:
    response = csrf_client.get('/api/v1/admin/service-modules/public')
    assert response.status_code == 200
    keys = {module['key'] for module in response.json()}
    assert {'ai', 'announcement', 'open-notebook', 'nsa'} <= keys


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

def test_asset_health_classifies_assets_and_config_health_is_admin_only(csrf_client, client, app, test_paths, monkeypatch) -> None:
    ok_path = test_paths['import_root'] / 'asset-ok.html'
    missing_path = test_paths['import_root'] / 'asset-missing.html'
    mismatch_path = test_paths['import_root'] / 'asset-mismatch.html'
    ok_path.write_text('<html>ok</html>', encoding='utf-8')
    missing_path.write_text('<html>missing</html>', encoding='utf-8')
    mismatch_path.write_text('<html>actual</html>', encoding='utf-8')
    ok_checksum = hash_file_bytes(ok_path.read_bytes())
    wrong_checksum = hash_file_bytes(b'expected')

    with app.state.db.session() as session:
        ok_newsletter = Newsletter(
            title='Asset OK',
            slug='asset-ok',
            source_type=SourceType.HTML,
            source_identifier='asset-ok',
            is_active=True,
        )
        ok_newsletter.assets.append(NewsletterAsset(asset_type=AssetType.HTML, file_path='asset-ok.html', checksum=ok_checksum, is_primary=True))
        missing_newsletter = Newsletter(
            title='Asset Missing',
            slug='asset-missing',
            source_type=SourceType.HTML,
            source_identifier='asset-missing',
            is_active=True,
        )
        missing_newsletter.assets.append(NewsletterAsset(asset_type=AssetType.HTML, file_path='asset-missing.html', checksum=hash_file_bytes(missing_path.read_bytes()), is_primary=True))
        mismatch_newsletter = Newsletter(
            title='Asset Mismatch',
            slug='asset-mismatch',
            source_type=SourceType.HTML,
            source_identifier='asset-mismatch',
            is_active=True,
        )
        mismatch_newsletter.assets.append(NewsletterAsset(asset_type=AssetType.HTML, file_path='asset-mismatch.html', checksum=wrong_checksum, is_primary=True))
        session.add_all([ok_newsletter, missing_newsletter, mismatch_newsletter])
        session.commit()

    missing_path.unlink()
    response = csrf_client.get('/api/v1/admin/newsletters/assets/health')
    assert response.status_code == 200
    health = response.json()
    by_title = {item['newsletter_title']: item for item in health['items']}
    assert by_title['Asset OK']['status'] == 'ok'
    assert by_title['Asset OK']['error_code'] is None
    assert by_title['Asset OK']['root_kind'] == 'import'
    assert by_title['Asset Missing']['status'] == 'missing'
    assert by_title['Asset Missing']['error_code'] == 'FILE_NOT_FOUND'
    assert by_title['Asset Mismatch']['status'] == 'checksum_mismatch'
    assert by_title['Asset Mismatch']['error_code'] == 'CHECKSUM_MISMATCH'
    assert health['ok'] >= 1
    assert health['missing'] >= 1
    assert health['checksum_mismatch'] >= 1

    config_response = csrf_client.get('/api/v1/admin/config/health')
    assert config_response.status_code == 200
    roots = {root['kind']: root for root in config_response.json()['roots']}
    assert {'storage', 'import', 'document', 'civil', 'nsa', 'markdown', 'thumbnails'} <= set(roots)
    assert roots['import']['exists'] is True
    assert roots['import']['readable'] is True

    _create_user(app, 'config-plain')
    plain_login = client.post('/api/v1/auth/login', json={'username': 'config-plain', 'password': 'password'})
    assert plain_login.status_code == 200
    plain_response = client.get('/api/v1/admin/config/health')
    assert plain_response.status_code == 403

    admin_login = csrf_client.post('/api/v1/auth/login', json={'username': 'admin', 'password': 'password'})
    assert admin_login.status_code == 200
    csrf_client.headers.update({'x-csrf-token': admin_login.json()['csrf_token']})

    monkeypatch.setenv('NEWSLETTER_IMPORT_ROOT_CONTAINER', str(test_paths['import_root'] / 'does-not-exist'))
    reset_settings_cache()
    misconfig_response = csrf_client.get('/api/v1/admin/newsletters/assets/health')
    assert misconfig_response.status_code == 200
    misconfigured = {item['newsletter_title']: item for item in misconfig_response.json()['items']}['Asset OK']
    assert misconfigured['status'] == 'misconfig'
    assert misconfigured['error_code'] == 'ROOT_MISSING'
    assert misconfigured['resolved_root'].endswith('does-not-exist')
    assert '환경변수' in misconfigured['remediation']
