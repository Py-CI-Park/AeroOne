from __future__ import annotations

import json

from app.core.config import reset_settings_cache
from app.core.security import hash_file_bytes, hash_password
from app.modules.admin.models import AdminAuditEvent, UserPermission
from app.modules.auth.models import User
from app.modules.newsletter.models.newsletter import AssetType, Newsletter, NewsletterAsset, SourceType

SAFE_ERROR_CODES = {None, 'FILE_NOT_FOUND', 'CHECKSUM_MISMATCH', 'ROOT_MISSING', 'PATH_ESCAPE'}
FORBIDDEN_DIAGNOSTIC_SUBSTRINGS = ('Traceback', 'Error(', 'test-secret', 'password', 'JWT_SECRET_KEY')
EXPECTED_ROOT_KINDS = {'storage', 'import', 'document', 'civil', 'nsa', 'markdown', 'thumbnails'}


def _create_user(app, username: str, *, permission: str | None = None) -> None:
    with app.state.db.session() as session:
        user = User(username=username, password_hash=hash_password('password'), role='user', is_active=True)
        session.add(user)
        session.flush()
        if permission is not None:
            session.add(UserPermission(user_id=user.id, permission_key=permission))
        session.commit()


def _newsletter(title: str, slug: str, file_path: str, checksum: str) -> Newsletter:
    newsletter = Newsletter(
        title=title,
        slug=slug,
        source_type=SourceType.HTML,
        source_identifier=slug,
        is_active=True,
    )
    newsletter.assets.append(
        NewsletterAsset(asset_type=AssetType.HTML, file_path=file_path, checksum=checksum, is_primary=True)
    )
    return newsletter


def _asset_rows(app) -> tuple[int, int, int]:
    with app.state.db.session() as session:
        return (
            session.query(Newsletter).count(),
            session.query(NewsletterAsset).count(),
            session.query(AdminAuditEvent).count(),
        )


def _assert_safe_diagnostics_payload(payload: dict) -> None:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    for item in payload['items']:
        assert item['error_code'] in SAFE_ERROR_CODES
        assert item['status'] in {'ok', 'missing', 'checksum_mismatch', 'misconfig'}
        assert item['remediation'] is not None
        assert item['resolved_root'] is not None
        for field in ('remediation', 'resolved_root', 'resolved_path'):
            value = item.get(field)
            if value is not None:
                assert all(forbidden not in value for forbidden in FORBIDDEN_DIAGNOSTIC_SUBSTRINGS)
    assert all(forbidden not in encoded for forbidden in FORBIDDEN_DIAGNOSTIC_SUBSTRINGS)


def test_asset_health_redteam_classifies_all_statuses_with_safe_codes(csrf_client, app, test_paths, monkeypatch) -> None:
    ok_path = test_paths['import_root'] / 'redteam-ok.html'
    missing_path = test_paths['import_root'] / 'redteam-missing.html'
    mismatch_path = test_paths['import_root'] / 'redteam-mismatch.html'
    ok_path.write_text('<html>ok</html>', encoding='utf-8')
    missing_path.write_text('<html>missing</html>', encoding='utf-8')
    mismatch_path.write_text('<html>actual</html>', encoding='utf-8')

    with app.state.db.session() as session:
        session.add_all(
            [
                _newsletter('Redteam Asset OK', 'redteam-asset-ok', 'redteam-ok.html', hash_file_bytes(ok_path.read_bytes())),
                _newsletter(
                    'Redteam Asset Missing',
                    'redteam-asset-missing',
                    'redteam-missing.html',
                    hash_file_bytes(missing_path.read_bytes()),
                ),
                _newsletter(
                    'Redteam Asset Mismatch',
                    'redteam-asset-mismatch',
                    'redteam-mismatch.html',
                    hash_file_bytes(b'not-the-actual-file'),
                ),
            ]
        )
        session.commit()

    missing_path.unlink()
    before_counts = _asset_rows(app)
    response = csrf_client.get('/api/v1/admin/newsletters/assets/health')
    assert response.status_code == 200
    assert _asset_rows(app) == before_counts

    health = response.json()
    _assert_safe_diagnostics_payload(health)
    by_title = {item['newsletter_title']: item for item in health['items']}
    assert by_title['Redteam Asset OK']['status'] == 'ok'
    assert by_title['Redteam Asset OK']['error_code'] is None
    assert by_title['Redteam Asset OK']['ok'] is True
    assert by_title['Redteam Asset Missing']['status'] == 'missing'
    assert by_title['Redteam Asset Missing']['error_code'] == 'FILE_NOT_FOUND'
    assert by_title['Redteam Asset Missing']['ok'] is False
    assert by_title['Redteam Asset Mismatch']['status'] == 'checksum_mismatch'
    assert by_title['Redteam Asset Mismatch']['error_code'] == 'CHECKSUM_MISMATCH'
    assert by_title['Redteam Asset Mismatch']['ok'] is False
    assert health['ok'] >= 1
    assert health['missing'] >= 1
    assert health['checksum_mismatch'] >= 1

    monkeypatch.setenv('NEWSLETTER_IMPORT_ROOT_CONTAINER', str(test_paths['import_root'] / 'missing-root-for-redteam'))
    reset_settings_cache()
    misconfig_response = csrf_client.get('/api/v1/admin/newsletters/assets/health')
    assert misconfig_response.status_code == 200
    assert _asset_rows(app) == before_counts
    misconfig_health = misconfig_response.json()
    _assert_safe_diagnostics_payload(misconfig_health)
    misconfigured = {item['newsletter_title']: item for item in misconfig_health['items']}['Redteam Asset OK']
    assert misconfigured['status'] == 'misconfig'
    assert misconfigured['error_code'] == 'ROOT_MISSING'
    assert misconfigured['ok'] is False
    assert misconfigured['resolved_path'] is None
    assert 'missing-root-for-redteam' in misconfigured['resolved_root']


def test_config_health_is_admin_only_safe_and_reports_roots(csrf_client, client, app) -> None:
    _create_user(app, 'redteam-non-admin')
    login = client.post('/api/v1/auth/login', json={'username': 'redteam-non-admin', 'password': 'password'})
    assert login.status_code == 200
    forbidden = client.get('/api/v1/admin/config/health')
    assert forbidden.status_code == 403

    admin_login = csrf_client.post('/api/v1/auth/login', json={'username': 'admin', 'password': 'password'})
    assert admin_login.status_code == 200
    csrf_client.headers.update({'x-csrf-token': admin_login.json()['csrf_token']})
    before_counts = _asset_rows(app)
    response = csrf_client.get('/api/v1/admin/config/health')
    assert response.status_code == 200
    assert _asset_rows(app) == before_counts

    payload = response.json()
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    assert all(forbidden_text not in encoded for forbidden_text in FORBIDDEN_DIAGNOSTIC_SUBSTRINGS)
    roots = {root['kind']: root for root in payload['roots']}
    assert EXPECTED_ROOT_KINDS <= set(roots)
    for kind in EXPECTED_ROOT_KINDS:
        assert isinstance(roots[kind]['resolved_path'], str)
        assert isinstance(roots[kind]['exists'], bool)
        assert isinstance(roots[kind]['readable'], bool)
    assert roots['import']['exists'] is True
    assert roots['import']['readable'] is True


def test_diagnostics_endpoints_are_get_only_and_admin_gated(csrf_client, client, app) -> None:
    _create_user(app, 'redteam-no-diagnostics-permission')
    login = client.post('/api/v1/auth/login', json={'username': 'redteam-no-diagnostics-permission', 'password': 'password'})
    assert login.status_code == 200
    assert client.get('/api/v1/admin/newsletters/assets/health').status_code == 403
    assert client.get('/api/v1/admin/config/health').status_code == 403

    admin_login = csrf_client.post('/api/v1/auth/login', json={'username': 'admin', 'password': 'password'})
    assert admin_login.status_code == 200
    csrf_client.headers.update({'x-csrf-token': admin_login.json()['csrf_token']})
    before_counts = _asset_rows(app)
    for endpoint in ('/api/v1/admin/newsletters/assets/health', '/api/v1/admin/config/health'):
        assert csrf_client.get(endpoint).status_code == 200
        assert csrf_client.post(endpoint).status_code == 405
        assert csrf_client.put(endpoint).status_code == 405
        assert csrf_client.patch(endpoint).status_code == 405
        assert csrf_client.delete(endpoint).status_code == 405
    assert _asset_rows(app) == before_counts
