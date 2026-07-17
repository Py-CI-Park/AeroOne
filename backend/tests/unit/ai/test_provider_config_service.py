from __future__ import annotations

import time

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

import app.modules.admin.models as admin_models  # noqa: F401  (registers ai_provider_config + journal tables)
import app.modules.auth.models as auth_models  # noqa: F401  (registers users table referenced by journal FK)
from app.core.config import Settings
from app.db.base import Base
from app.modules.admin.models import AiProviderConfig, AiProviderOperationJournal
from app.modules.admin.schemas import (
    AiProviderCompatibleDeleteRequest,
    AiProviderCompatibleTestRequest,
    AiProviderCompatibleWriteRequest,
    AiProviderSelectionRequest,
)
from app.modules.ai import provider_config_service as pcs
from app.modules.ai.egress_transport import EgressErrorCode, EgressOutcome
from app.modules.ai.provider_config_service import (
    ProviderCandidateInvalid,
    ProviderConfigService,
    ProviderConfigVersionConflict,
    ProviderSelectionInvalid,
)
from app.operations.provider_credential_store import (
    ProviderCredentialEnvelope,
    ProviderCredentialStoreError,
    ProviderCredentialStoreErrorCode,
)

# Journal rows are metadata-only: this is the exact, exhaustive allowlist of columns the
# table is permitted to carry. Any new column here must be justified as safe-result
# metadata, never candidate url/model/key material.
_SAFE_JOURNAL_COLUMNS = {
    'id',
    'operation',
    'kind',
    'result',
    'reason_code',
    'actor_user_id',
    'config_version_before',
    'config_version_after',
    'created_at',
}

SECRET_API_KEY = "sk-test-only-synthetic-not-a-real-secret-0123456789"
CANDIDATE_URL = "http://127.0.0.1:8080/v1"
CANDIDATE_MODEL = "llama3"
CANDIDATE_GENERATION = "gen-1"


class _FakeUser:
    """Minimal actor double: the service only ever reads `.id` off of it."""

    def __init__(self, user_id: int) -> None:
        self.id = user_id


class FakeCredentialStore:
    """In-memory double for ProviderCredentialStore with the same return/exception
    contract as the real DPAPI-backed store (store_credential/load_plaintext/
    get_envelope/delete_credential), without touching the filesystem or DPAPI."""

    def __init__(self) -> None:
        self._data: dict[str, tuple[bytes, int]] = {}

    def store_credential(
        self,
        credential_ref: str,
        plaintext: bytes,
        *,
        binding_version: int,
        existing_binding_version: int | None,
    ) -> ProviderCredentialEnvelope:
        current = self._data.get(credential_ref)
        if current is not None:
            _, existing_bv = current
            if existing_binding_version != existing_bv or binding_version != existing_bv:
                raise ProviderCredentialStoreError(ProviderCredentialStoreErrorCode.BINDING_VERSION_IMMUTABLE)
        elif existing_binding_version is not None:
            raise ProviderCredentialStoreError(ProviderCredentialStoreErrorCode.CREDENTIAL_NOT_FOUND)
        self._data[credential_ref] = (plaintext, binding_version)
        return ProviderCredentialEnvelope(credential_ref=credential_ref, credential_binding_version=binding_version, created_at=time.time())

    def get_envelope(self, credential_ref: str) -> ProviderCredentialEnvelope | None:
        entry = self._data.get(credential_ref)
        if entry is None:
            return None
        return ProviderCredentialEnvelope(credential_ref=credential_ref, credential_binding_version=entry[1], created_at=time.time())

    def load_plaintext(self, credential_ref: str) -> bytes:
        entry = self._data.get(credential_ref)
        if entry is None:
            raise ProviderCredentialStoreError(ProviderCredentialStoreErrorCode.CREDENTIAL_NOT_FOUND)
        return entry[0]

    def delete_credential(self, credential_ref: str) -> None:
        self._data.pop(credential_ref, None)


@pytest.fixture()
def engine():
    eng = sa.create_engine('sqlite://')
    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)


@pytest.fixture()
def db(engine) -> Session:
    with Session(engine) as session:
        session.add(AiProviderConfig(singleton_id=1, selected_kind='ollama', compatible_state='absent', config_version=1))
        session.commit()
        yield session


@pytest.fixture()
def settings() -> Settings:
    return Settings(app_env='test')


@pytest.fixture()
def store() -> FakeCredentialStore:
    return FakeCredentialStore()


@pytest.fixture()
def actor() -> _FakeUser:
    return _FakeUser(1)


@pytest.fixture()
def service(db: Session, settings: Settings, store: FakeCredentialStore) -> ProviderConfigService:
    return ProviderConfigService(db, settings, credential_store=store)


def _write_payload(*, expected_config_version: int = 1) -> AiProviderCompatibleWriteRequest:
    return AiProviderCompatibleWriteRequest(
        canonical_url=CANDIDATE_URL,
        display_url=CANDIDATE_URL,
        model=CANDIDATE_MODEL,
        generation=CANDIDATE_GENERATION,
        api_key=SECRET_API_KEY,
        expected_config_version=expected_config_version,
    )


def _test_payload(**overrides: str) -> AiProviderCompatibleTestRequest:
    fields = {'canonical_url': CANDIDATE_URL, 'model': CANDIDATE_MODEL, 'generation': CANDIDATE_GENERATION}
    fields.update(overrides)
    return AiProviderCompatibleTestRequest(**fields)


def _ok_outcome() -> EgressOutcome:
    return EgressOutcome(ok=True, error_code=None, status_code=200, latency_ms=2, payload={'data': [{'id': CANDIDATE_MODEL}]})


def test_write_candidate_stages_unverified_clears_proof_and_bumps_version_without_activating(
    service: ProviderConfigService, actor: _FakeUser, db: Session
) -> None:
    response = service.write_candidate(_write_payload(), actor, expected_config_version=1)

    assert response.compatible_state == 'unverified'
    assert response.config_version == 2
    assert response.selected_kind == 'ollama'  # write_candidate never auto-activates

    row = db.get(AiProviderConfig, 1)
    assert row is not None
    assert row.selected_kind == 'ollama'
    assert row.compatible_canonical_url == CANDIDATE_URL
    assert row.compatible_credential_ref is not None
    assert row.compatible_test_proof_ref is None
    assert row.compatible_test_proof_at is None
    assert row.compatible_test_proof_canonical_url is None


def test_write_candidate_rejects_stale_expected_version(service: ProviderConfigService, actor: _FakeUser) -> None:
    with pytest.raises(ProviderConfigVersionConflict):
        service.write_candidate(_write_payload(), actor, expected_config_version=99)


def test_write_candidate_clears_prior_proof_on_replacement(
    service: ProviderConfigService, actor: _FakeUser, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(pcs, 'probe_models', lambda *a, **k: _ok_outcome())
    resp1 = service.write_candidate(_write_payload(), actor, expected_config_version=1)
    service.test_candidate(_test_payload(), actor)
    row = db.get(AiProviderConfig, 1)
    assert row.compatible_state == 'verified'

    resp2 = service.write_candidate(_write_payload(expected_config_version=row.config_version), actor, expected_config_version=row.config_version)
    assert resp2.compatible_state == 'unverified'
    row = db.get(AiProviderConfig, 1)
    assert row.compatible_state == 'unverified'
    assert row.compatible_test_proof_ref is None
    assert row.compatible_credential_ref != resp1  # sanity: ref rotated, not compared literally


def test_test_candidate_binds_proof_on_exact_persisted_match(
    service: ProviderConfigService, actor: _FakeUser, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    service.write_candidate(_write_payload(), actor, expected_config_version=1)
    monkeypatch.setattr(pcs, 'probe_models', lambda *a, **k: _ok_outcome())

    result = service.test_candidate(_test_payload(), actor)

    assert result.success is True
    assert result.canonical_url == CANDIDATE_URL
    assert result.model == CANDIDATE_MODEL
    assert result.generation == CANDIDATE_GENERATION

    row = db.get(AiProviderConfig, 1)
    assert row.compatible_state == 'verified'
    assert row.config_version == 3
    assert row.compatible_test_proof_ref is not None
    assert row.compatible_test_proof_canonical_url == CANDIDATE_URL
    assert row.compatible_test_proof_model == CANDIDATE_MODEL
    assert row.compatible_test_proof_generation == CANDIDATE_GENERATION


@pytest.mark.parametrize(
    "overrides",
    [
        {'model': 'a-different-model'},
        {'canonical_url': 'http://127.0.0.1:9090/v1'},
        {'generation': 'gen-2'},
    ],
)
def test_test_candidate_rejects_mismatched_submission_without_any_network_call(
    service: ProviderConfigService, actor: _FakeUser, monkeypatch: pytest.MonkeyPatch, overrides: dict[str, str]
) -> None:
    service.write_candidate(_write_payload(), actor, expected_config_version=1)

    def _must_not_be_called(*_a: object, **_k: object) -> EgressOutcome:
        raise AssertionError('probe_models must not be called for a mismatched candidate')

    monkeypatch.setattr(pcs, 'probe_models', _must_not_be_called)

    with pytest.raises(ProviderCandidateInvalid):
        service.test_candidate(_test_payload(**overrides), actor)


def test_failed_probe_records_result_only_journal_row_and_never_writes_proof(
    service: ProviderConfigService, actor: _FakeUser, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    service.write_candidate(_write_payload(), actor, expected_config_version=1)
    monkeypatch.setattr(
        pcs,
        'probe_models',
        lambda *a, **k: EgressOutcome(ok=False, error_code=EgressErrorCode.CONNECT_FAILED, status_code=None, latency_ms=4, payload=None),
    )

    result = service.test_candidate(_test_payload(), actor)

    assert result.success is False
    assert result.reason_code == EgressErrorCode.CONNECT_FAILED.value

    row = db.get(AiProviderConfig, 1)
    assert row.compatible_state == 'unverified'
    assert row.compatible_test_proof_ref is None
    assert row.config_version == 2  # unchanged since the write_candidate bump; failure never bumps further

    journal_rows = db.query(AiProviderOperationJournal).filter_by(operation='test').all()
    assert len(journal_rows) == 1
    assert journal_rows[0].result == 'failure'
    assert journal_rows[0].reason_code == EgressErrorCode.CONNECT_FAILED.value
    assert journal_rows[0].config_version_before == journal_rows[0].config_version_after == 2


def test_set_selection_to_compatible_requires_bound_verified_proof(
    service: ProviderConfigService, actor: _FakeUser, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    resp = service.write_candidate(_write_payload(), actor, expected_config_version=1)

    with pytest.raises(ProviderSelectionInvalid):
        service.set_selection(AiProviderSelectionRequest(selected_kind='openai_compatible', expected_config_version=resp.config_version), actor)

    monkeypatch.setattr(pcs, 'probe_models', lambda *a, **k: _ok_outcome())
    service.test_candidate(_test_payload(), actor)
    row = db.get(AiProviderConfig, 1)

    ok = service.set_selection(AiProviderSelectionRequest(selected_kind='openai_compatible', expected_config_version=row.config_version), actor)
    assert ok.selected_kind == 'openai_compatible'


def test_set_selection_to_ollama_is_always_allowed_even_without_compatible_proof(
    service: ProviderConfigService, actor: _FakeUser, db: Session
) -> None:
    row = db.get(AiProviderConfig, 1)
    assert row.compatible_state == 'absent'  # no candidate ever written

    ok = service.set_selection(AiProviderSelectionRequest(selected_kind='ollama', expected_config_version=row.config_version), actor)
    assert ok.selected_kind == 'ollama'


def test_delete_credential_resets_row_to_absent_and_removes_stored_secret(
    service: ProviderConfigService, actor: _FakeUser, store: FakeCredentialStore, db: Session
) -> None:
    resp = service.write_candidate(_write_payload(), actor, expected_config_version=1)
    row = db.get(AiProviderConfig, 1)
    old_ref = row.compatible_credential_ref
    assert old_ref in store._data

    result = service.delete_credential(AiProviderCompatibleDeleteRequest(expected_config_version=resp.config_version), actor)

    assert result.compatible_state == 'absent'
    row = db.get(AiProviderConfig, 1)
    assert row.compatible_canonical_url is None
    assert row.compatible_credential_ref is None
    assert row.compatible_test_proof_ref is None
    assert old_ref not in store._data


def test_reconcile_detects_drifted_envelope_and_invalidates_proof(
    service: ProviderConfigService, actor: _FakeUser, store: FakeCredentialStore, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    service.write_candidate(_write_payload(), actor, expected_config_version=1)
    monkeypatch.setattr(pcs, 'probe_models', lambda *a, **k: _ok_outcome())
    service.test_candidate(_test_payload(), actor)

    row = db.get(AiProviderConfig, 1)
    ref = row.compatible_credential_ref
    assert row.compatible_state == 'verified'
    # Simulate out-of-band drift: the on-disk envelope's binding version no longer
    # matches what the DB row expects (e.g. a stale/rotated blob).
    plaintext, _bv = store._data[ref]
    store._data[ref] = (plaintext, row.compatible_credential_binding_version + 1)

    result = service.reconcile(actor)

    assert result.reconciled is False
    assert result.compatible_state == 'unverified'
    row = db.get(AiProviderConfig, 1)
    assert row.compatible_state == 'unverified'
    assert row.compatible_test_proof_ref is None
    assert row.compatible_test_proof_canonical_url is None


def test_reconcile_detects_missing_envelope_and_invalidates_proof(
    service: ProviderConfigService, actor: _FakeUser, store: FakeCredentialStore, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    service.write_candidate(_write_payload(), actor, expected_config_version=1)
    monkeypatch.setattr(pcs, 'probe_models', lambda *a, **k: _ok_outcome())
    service.test_candidate(_test_payload(), actor)

    row = db.get(AiProviderConfig, 1)
    ref = row.compatible_credential_ref
    del store._data[ref]  # underlying credential vanished out-of-band

    result = service.reconcile(actor)

    assert result.reconciled is False
    row = db.get(AiProviderConfig, 1)
    assert row.compatible_state == 'unverified'
    assert row.compatible_test_proof_ref is None


def test_load_active_compatible_binding_requires_selection_and_bound_proof(
    service: ProviderConfigService, actor: _FakeUser, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(ProviderSelectionInvalid):
        service.load_active_compatible_binding()

    service.write_candidate(_write_payload(), actor, expected_config_version=1)
    with pytest.raises(ProviderSelectionInvalid):  # unverified candidate, not selected
        service.load_active_compatible_binding()

    monkeypatch.setattr(pcs, 'probe_models', lambda *a, **k: _ok_outcome())
    service.test_candidate(_test_payload(), actor)
    with pytest.raises(ProviderSelectionInvalid):  # proven but selected_kind still 'ollama'
        service.load_active_compatible_binding()

    row = db.get(AiProviderConfig, 1)
    service.set_selection(AiProviderSelectionRequest(selected_kind='openai_compatible', expected_config_version=row.config_version), actor)

    binding = service.load_active_compatible_binding()
    assert binding.canonical_url == CANDIDATE_URL
    assert binding.model == CANDIDATE_MODEL
    assert binding.api_key == SECRET_API_KEY.encode('utf-8')


def test_operation_journal_columns_are_allowlisted_and_never_carry_candidate_secrets(
    service: ProviderConfigService, actor: _FakeUser, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    columns = {c.name for c in AiProviderOperationJournal.__table__.columns}
    assert columns == _SAFE_JOURNAL_COLUMNS

    service.write_candidate(_write_payload(), actor, expected_config_version=1)
    monkeypatch.setattr(
        pcs,
        'probe_models',
        lambda *a, **k: EgressOutcome(ok=False, error_code=EgressErrorCode.CONNECT_FAILED, status_code=None, latency_ms=1, payload=None),
    )
    service.test_candidate(_test_payload(), actor)

    rows = db.query(AiProviderOperationJournal).all()
    assert rows
    for row in rows:
        assert row.reason_code is None or (SECRET_API_KEY not in row.reason_code and CANDIDATE_URL not in row.reason_code and CANDIDATE_MODEL not in row.reason_code)
        for attr in ('operation', 'kind', 'result'):
            value = getattr(row, attr)
            assert SECRET_API_KEY not in value
            assert CANDIDATE_URL not in value


def test_failpoint_before_commit_rolls_back_write_candidate_cleanly(
    db: Session, settings: Settings, store: FakeCredentialStore, actor: _FakeUser
) -> None:
    def failpoint(stage: str) -> None:
        if stage == 'write_candidate.pre_commit':
            raise RuntimeError('injected crash before commit')

    svc = ProviderConfigService(db, settings, credential_store=store, failpoint=failpoint)

    with pytest.raises(RuntimeError):
        svc.write_candidate(_write_payload(), actor, expected_config_version=1)

    db.rollback()
    row = db.get(AiProviderConfig, 1)
    assert row is not None
    assert row.config_version == 1
    assert row.compatible_state == 'absent'
    assert row.compatible_credential_ref is None
    assert row.compatible_test_proof_ref is None
    assert db.query(AiProviderOperationJournal).count() == 0


def test_failpoint_before_commit_rolls_back_test_candidate_without_half_written_proof(
    db: Session, settings: Settings, store: FakeCredentialStore, actor: _FakeUser, monkeypatch: pytest.MonkeyPatch
) -> None:
    svc = ProviderConfigService(db, settings, credential_store=store)
    svc.write_candidate(_write_payload(), actor, expected_config_version=1)
    db.commit()
    monkeypatch.setattr(pcs, 'probe_models', lambda *a, **k: _ok_outcome())

    def failpoint(stage: str) -> None:
        if stage == 'test_compatible.pre_commit':
            raise RuntimeError('injected crash before commit')

    svc._failpoint = failpoint  # inject after construction to reuse the already-staged candidate

    with pytest.raises(RuntimeError):
        svc.test_candidate(_test_payload(), actor)

    db.rollback()
    row = db.get(AiProviderConfig, 1)
    assert row.compatible_state == 'unverified'  # never flipped to verified
    assert row.compatible_test_proof_ref is None
    assert row.config_version == 2  # still just the write_candidate bump, not test's


def test_write_request_repr_never_exposes_api_key() -> None:
    # Field(repr=False) 를 __repr_args__ 재정의로 바꾼 뒤에도(경고 제거) repr/str 어디에도
    # api_key 가 노출되지 않는 보안 계약을 회귀로 고정한다.
    from app.modules.admin.schemas import AiProviderCompatibleRotateRequest, AiProviderCompatibleWriteRequest

    secret = 'sk-REPR-EXPOSURE-CANARY'
    for cls in (AiProviderCompatibleWriteRequest, AiProviderCompatibleRotateRequest):
        request = cls(
            canonical_url='http://127.0.0.1:11434/v1',
            display_url='http://127.0.0.1:11434/v1',
            model='m',
            generation='g',
            api_key=secret,
            expected_config_version=1,
        )
        assert secret not in repr(request)
        assert secret not in str(request)
        # 직렬화(model_dump)에는 남아 있어야 한다 — 저장 경로가 소비.
        assert request.api_key == secret
