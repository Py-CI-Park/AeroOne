from __future__ import annotations

import json
from datetime import UTC, datetime
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.modules.admin.models import AdminAuditEvent, UserPermission
from app.modules.admin.schemas import AiProviderConfigResponse, AiProviderReconcileResponse, AiProviderTestResultResponse
from app.modules.ai.provider_config_service import (
    ProviderCandidateInvalid,
    ProviderConfigService,
    ProviderConfigVersionConflict,
    ProviderCredentialUnavailable,
    ProviderProofMismatch,
    ProviderProofMissing,
    ProviderSelectionInvalid,
    ProviderUpstreamUnavailable,
)
from app.modules.auth.models import User


def _config(**overrides) -> AiProviderConfigResponse:
    base: dict[str, object] = dict(
        selected_kind='ollama',
        compatible_state='absent',
        compatible_display_url=None,
        compatible_model=None,
        compatible_generation=None,
        compatible_test_proof_at=None,
        compatible_test_proof_model=None,
        config_version=1,
        updated_at=datetime.now(UTC),
    )
    base.update(overrides)
    return AiProviderConfigResponse(**base)


def _create_user(app, username: str, *, permission: str | None = None) -> None:
    with app.state.db.session() as session:
        user = User(username=username, password_hash=hash_password('password'), role='user', is_active=True)
        session.add(user)
        session.flush()
        if permission:
            session.add(UserPermission(user_id=user.id, permission_key=permission))
        session.commit()


def _latest_audit_metadata(app, action: str) -> dict[str, object]:
    with app.state.db.session() as session:
        row = session.query(AdminAuditEvent).filter(AdminAuditEvent.action == action).order_by(AdminAuditEvent.id.desc()).first()
        assert row is not None, f'no audit event recorded for action={action}'
        return json.loads(row.metadata_json) if row.metadata_json else {}


def test_ai_provider_config_get_requires_permission_and_is_no_store(client, app, monkeypatch) -> None:
    monkeypatch.setattr(ProviderConfigService, 'get_state', lambda self: _config())

    anonymous = client.get('/api/v1/admin/ai-provider/config')
    assert anonymous.status_code == 401

    _create_user(app, 'plain-user')
    login = client.post('/api/v1/auth/login', json={'username': 'plain-user', 'password': 'password'})
    assert login.status_code == 200
    forbidden = client.get('/api/v1/admin/ai-provider/config')
    assert forbidden.status_code == 403

    admin_login = client.post('/api/v1/auth/login', json={'username': 'admin', 'password': 'password'})
    assert admin_login.status_code == 200
    ok = client.get('/api/v1/admin/ai-provider/config')
    assert ok.status_code == 200
    assert ok.headers['cache-control'] == 'no-store'


def test_ai_provider_config_get_never_exposes_credential_or_canonical_url(client, monkeypatch) -> None:
    monkeypatch.setattr(
        ProviderConfigService,
        'get_state',
        lambda self: _config(
            selected_kind='openai_compatible',
            compatible_state='verified',
            compatible_display_url='https://provider.example',
            compatible_model='gpt-x',
            compatible_generation='2024-01',
            config_version=3,
        ),
    )
    login = client.post('/api/v1/auth/login', json={'username': 'admin', 'password': 'password'})
    assert login.status_code == 200

    response = client.get('/api/v1/admin/ai-provider/config')
    assert response.status_code == 200
    body = response.json()
    forbidden_keys = {'api_key', 'compatible_canonical_url', 'compatible_credential_ref', 'compatible_credential_binding_version'}
    assert forbidden_keys.isdisjoint(body.keys())


def test_ai_provider_write_requires_csrf_then_mutates_version_and_audits_allowlist_only(csrf_client, app, monkeypatch) -> None:
    monkeypatch.setattr(
        ProviderConfigService,
        'write_candidate',
        lambda self, payload, actor, expected_config_version: _config(compatible_state='unverified', config_version=expected_config_version + 1),
    )

    without_csrf = csrf_client.post(
        '/api/v1/admin/ai-provider/config',
        json={'canonical_url': 'https://upstream.internal/v1', 'display_url': 'https://provider.example', 'model': 'gpt-x', 'generation': '2024-01', 'api_key': 'super-secret-key', 'expected_config_version': 1},
        headers={'x-csrf-token': ''},
    )
    assert without_csrf.status_code == 403

    ok = csrf_client.post(
        '/api/v1/admin/ai-provider/config',
        json={'canonical_url': 'https://upstream.internal/v1', 'display_url': 'https://provider.example', 'model': 'gpt-x', 'generation': '2024-01', 'api_key': 'super-secret-key', 'expected_config_version': 1},
    )
    assert ok.status_code == 200
    assert ok.headers['cache-control'] == 'no-store'
    assert ok.json()['config_version'] == 2

    metadata = _latest_audit_metadata(app, 'ai_provider.write')
    assert set(metadata.keys()) <= {'operation', 'result', 'reason_code', 'kind', 'selected_kind', 'compatible_state', 'config_version'}
    assert 'api_key' not in json.dumps(metadata)
    assert 'super-secret-key' not in json.dumps(metadata)
    assert 'upstream.internal' not in json.dumps(metadata)


def test_ai_provider_write_version_conflict_maps_409_with_fixed_safe_detail(csrf_client, monkeypatch) -> None:
    def raise_conflict(self, payload, actor, expected_config_version):
        exc = ProviderConfigVersionConflict('stale row version 7 != 1 at /internal/path')
        exc.reason_code = 'config_version_conflict'
        raise exc

    monkeypatch.setattr(ProviderConfigService, 'write_candidate', raise_conflict)

    response = csrf_client.post(
        '/api/v1/admin/ai-provider/config',
        json={'canonical_url': 'https://upstream.internal/v1', 'display_url': 'https://provider.example', 'model': 'gpt-x', 'generation': '2024-01', 'api_key': 'k', 'expected_config_version': 1},
    )
    assert response.status_code == 409
    assert response.json()['detail'] == 'config_version_conflict'
    assert 'internal/path' not in response.text


def test_ai_provider_write_candidate_invalid_maps_422(csrf_client, monkeypatch) -> None:
    def raise_invalid(self, payload, actor, expected_config_version):
        exc = ProviderCandidateInvalid('bad url')
        exc.reason_code = 'candidate_invalid'
        raise exc

    monkeypatch.setattr(ProviderConfigService, 'write_candidate', raise_invalid)

    response = csrf_client.post(
        '/api/v1/admin/ai-provider/config',
        json={'canonical_url': 'not-a-url', 'display_url': 'https://provider.example', 'model': 'gpt-x', 'generation': '2024-01', 'api_key': 'k', 'expected_config_version': 1},
    )
    assert response.status_code == 422
    assert response.json()['detail'] == 'candidate_invalid'


def test_ai_provider_test_upstream_unavailable_maps_503(csrf_client, monkeypatch) -> None:
    def raise_unavailable(self, payload, actor):
        exc = ProviderUpstreamUnavailable('connect timeout to 10.0.0.5:443')
        exc.reason_code = 'upstream_unavailable'
        raise exc

    monkeypatch.setattr(ProviderConfigService, 'test_candidate', raise_unavailable)

    response = csrf_client.post(
        '/api/v1/admin/ai-provider/test',
        json={'canonical_url': 'https://upstream.internal/v1', 'model': 'gpt-x', 'generation': '2024-01', 'api_key': 'k'},
    )
    assert response.status_code == 503
    assert response.json()['detail'] == 'upstream_unavailable'
    assert '10.0.0.5' not in response.text


def test_ai_provider_candidate_test_persists_result_only_audit_no_candidate_material(csrf_client, app, monkeypatch) -> None:
    monkeypatch.setattr(
        ProviderConfigService,
        'test_candidate',
        lambda self, payload, actor: AiProviderTestResultResponse(
            success=True,
            reason_code='ok',
            tested_at=datetime.now(UTC),
            canonical_url=payload.canonical_url,
            model=payload.model,
            generation=payload.generation,
        ),
    )

    response = csrf_client.post(
        '/api/v1/admin/ai-provider/test',
        json={'canonical_url': 'https://upstream.internal/v1', 'model': 'gpt-x', 'generation': '2024-01', 'api_key': 'candidate-secret'},
    )
    assert response.status_code == 200
    assert response.json()['success'] is True

    metadata = _latest_audit_metadata(app, 'ai_provider.test')
    assert set(metadata.keys()) <= {'operation', 'result', 'reason_code', 'kind', 'selected_kind', 'compatible_state', 'config_version'}
    dumped = json.dumps(metadata)
    for leaked in ('candidate-secret', 'upstream.internal', 'gpt-x', 'canonical_url'):
        assert leaked not in dumped


def test_ai_provider_activate_requires_exact_bound_proof(csrf_client, monkeypatch) -> None:
    def raise_missing(self, actor, expected_config_version):
        exc = ProviderProofMissing('no proof row')
        exc.reason_code = 'proof_missing'
        raise exc

    monkeypatch.setattr(ProviderConfigService, 'activate', raise_missing)
    missing = csrf_client.post('/api/v1/admin/ai-provider/activate', json={'expected_config_version': 2})
    assert missing.status_code == 409
    assert missing.json()['detail'] == 'proof_missing'

    def raise_mismatch(self, actor, expected_config_version):
        exc = ProviderProofMismatch('proof bound to stale model')
        exc.reason_code = 'proof_mismatch'
        raise exc

    monkeypatch.setattr(ProviderConfigService, 'activate', raise_mismatch)
    mismatch = csrf_client.post('/api/v1/admin/ai-provider/activate', json={'expected_config_version': 2})
    assert mismatch.status_code == 409
    assert mismatch.json()['detail'] == 'proof_mismatch'


def test_ai_provider_activate_success_switches_selected_kind_and_audits(csrf_client, app, monkeypatch) -> None:
    monkeypatch.setattr(
        ProviderConfigService,
        'activate',
        lambda self, actor, expected_config_version: _config(selected_kind='openai_compatible', compatible_state='verified', config_version=3),
    )

    response = csrf_client.post('/api/v1/admin/ai-provider/activate', json={'expected_config_version': 2})
    assert response.status_code == 200
    assert response.json()['selected_kind'] == 'openai_compatible'
    assert response.json()['config_version'] == 3

    metadata = _latest_audit_metadata(app, 'ai_provider.activate')
    assert metadata['selected_kind'] == 'openai_compatible'
    assert metadata['config_version'] == 3


def test_ai_provider_selection_is_explicit_rollback_to_ollama(csrf_client, app, monkeypatch) -> None:
    monkeypatch.setattr(
        ProviderConfigService,
        'set_selection',
        lambda self, payload, actor: _config(selected_kind='ollama', compatible_state='verified', config_version=4),
    )

    response = csrf_client.post(
        '/api/v1/admin/ai-provider/selection',
        json={'selected_kind': 'ollama', 'expected_config_version': 3},
    )
    assert response.status_code == 200
    assert response.json()['selected_kind'] == 'ollama'

    metadata = _latest_audit_metadata(app, 'ai_provider.selection')
    assert metadata['selected_kind'] == 'ollama'


def test_ai_provider_selection_invalid_maps_422(csrf_client, monkeypatch) -> None:
    def raise_invalid(self, payload, actor):
        exc = ProviderSelectionInvalid('cannot select unverified compatible provider')
        exc.reason_code = 'selection_invalid'
        raise exc

    monkeypatch.setattr(ProviderConfigService, 'set_selection', raise_invalid)
    response = csrf_client.post(
        '/api/v1/admin/ai-provider/selection',
        json={'selected_kind': 'openai_compatible', 'expected_config_version': 1},
    )
    assert response.status_code == 422
    assert response.json()['detail'] == 'selection_invalid'


def test_ai_provider_rotate_credential_conflict_maps_409_and_success_returns_new_version(csrf_client, monkeypatch) -> None:
    def raise_unavailable(self, payload, actor):
        exc = ProviderCredentialUnavailable('dpapi store locked')
        exc.reason_code = 'credential_unavailable'
        raise exc

    monkeypatch.setattr(ProviderConfigService, 'rotate_credential', raise_unavailable)
    conflict = csrf_client.post(
        '/api/v1/admin/ai-provider/rotate',
        json={'canonical_url': 'https://upstream.internal/v1', 'display_url': 'https://provider.example', 'model': 'gpt-x', 'generation': '2024-01', 'api_key': 'new-key', 'expected_config_version': 3},
    )
    assert conflict.status_code == 409
    assert conflict.json()['detail'] == 'credential_unavailable'

    monkeypatch.setattr(ProviderConfigService, 'rotate_credential', lambda self, payload, actor: _config(compatible_state='unverified', config_version=5))
    ok = csrf_client.post(
        '/api/v1/admin/ai-provider/rotate',
        json={'canonical_url': 'https://upstream.internal/v1', 'display_url': 'https://provider.example', 'model': 'gpt-x', 'generation': '2024-01', 'api_key': 'new-key', 'expected_config_version': 4},
    )
    assert ok.status_code == 200
    assert ok.json()['config_version'] == 5
    assert 'new-key' not in ok.text


def test_ai_provider_delete_credential_resets_state_forces_ollama(csrf_client, monkeypatch) -> None:
    monkeypatch.setattr(
        ProviderConfigService,
        'delete_credential',
        lambda self, payload, actor: _config(selected_kind='ollama', compatible_state='absent', config_version=6),
    )

    response = csrf_client.request('DELETE', '/api/v1/admin/ai-provider/credential', json={'expected_config_version': 5})
    assert response.status_code == 200
    assert response.json() == {
        'selected_kind': 'ollama',
        'compatible_state': 'absent',
        'compatible_display_url': None,
        'compatible_model': None,
        'compatible_generation': None,
        'compatible_test_proof_at': None,
        'compatible_test_proof_model': None,
        'config_version': 6,
        'updated_at': response.json()['updated_at'],
    }


def test_ai_provider_reconcile_is_manage_gated_and_audited(client, app, csrf_client, monkeypatch) -> None:
    monkeypatch.setattr(
        ProviderConfigService,
        'reconcile',
        lambda self, actor: AiProviderReconcileResponse(reconciled=True, compatible_state='verified', config_version=7),
    )

    anonymous = TestClient(app).post('/api/v1/admin/ai-provider/reconcile')
    assert anonymous.status_code == 401

    response = csrf_client.post('/api/v1/admin/ai-provider/reconcile')
    assert response.status_code == 200
    assert response.json() == {'reconciled': True, 'compatible_state': 'verified', 'config_version': 7}

    metadata = _latest_audit_metadata(app, 'ai_provider.reconcile')
    assert metadata['reason_code'] == 'reconciled'
    assert metadata['config_version'] == 7
