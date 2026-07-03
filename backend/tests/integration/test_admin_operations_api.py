from __future__ import annotations


def test_admin_dashboard_modules_assets_and_backup(csrf_client) -> None:
    modules_response = csrf_client.get('/api/v1/admin/service-modules/public')
    assert modules_response.status_code == 200
    modules = modules_response.json()
    assert [module['key'] for module in modules][:3] == ['newsletter', 'civil-aircraft', 'document']
    assert any(module['key'] == 'open-notebook' and module['is_external'] for module in modules)

    summary_response = csrf_client.get('/api/v1/admin/dashboard')
    assert summary_response.status_code == 200
    summary = summary_response.json()
    assert summary['app_version'] == '1.8.0'
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
