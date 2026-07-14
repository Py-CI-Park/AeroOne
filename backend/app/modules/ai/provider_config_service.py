from __future__ import annotations

import secrets
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum, unique
from typing import Callable, override

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.admin.models import AiProviderConfig, AiProviderOperationJournal
from app.modules.admin.schemas import (
    AiProviderCompatibleDeleteRequest,
    AiProviderCompatibleRotateRequest,
    AiProviderCompatibleTestRequest,
    AiProviderCompatibleWriteRequest,
    AiProviderConfigResponse,
    AiProviderKind,
    AiProviderReconcileResponse,
    AiProviderSelectionRequest,
    AiProviderTestResultResponse,
)
from app.modules.ai.egress_transport import canonicalize_endpoint, probe_models
from app.modules.auth.models import User
from app.operations.provider_credential_store import ProviderCredentialEnvelope, ProviderCredentialStore, ProviderCredentialStoreError

# Deterministic transitions for the singleton AI provider configuration row. Explicit
# selection only: `selected_kind` is switched exactly by `set_selection`, never inferred
# or silently changed inside a chat request path. Replacing compatible credential
# material always invalidates any prior test proof and demotes `selected_kind` back to
# 'ollama' if it was pointed at the now-unverified compatible config, so an in-flight
# activation can never keep serving compatible traffic against a binding nobody proved.


@unique
class ProviderConfigErrorCode(StrEnum):
    CANDIDATE_INVALID = "candidate_invalid"
    UPSTREAM_UNAVAILABLE = "upstream_unavailable"
    SELECTION_INVALID = "selection_invalid"
    CREDENTIAL_UNAVAILABLE = "credential_unavailable"
    CONFIG_VERSION_CONFLICT = "config_version_conflict"
    PROOF_MISSING = "proof_missing"
    PROOF_MISMATCH = "proof_mismatch"


class ProviderConfigError(RuntimeError):
    code: ProviderConfigErrorCode
    reason_code: str

    def __init__(self, code: ProviderConfigErrorCode, message: str | None = None) -> None:
        self.code = code
        self.reason_code = code.value
        super().__init__(message or code.value)

    @override
    def __str__(self) -> str:
        return self.code.value


class ProviderCandidateInvalid(ProviderConfigError):
    def __init__(self, message: str | None = None) -> None:
        super().__init__(ProviderConfigErrorCode.CANDIDATE_INVALID, message)


class ProviderUpstreamUnavailable(ProviderConfigError):
    def __init__(self, message: str | None = None) -> None:
        super().__init__(ProviderConfigErrorCode.UPSTREAM_UNAVAILABLE, message)


class ProviderSelectionInvalid(ProviderConfigError):
    def __init__(self, message: str | None = None) -> None:
        super().__init__(ProviderConfigErrorCode.SELECTION_INVALID, message)


class ProviderCredentialUnavailable(ProviderConfigError):
    def __init__(self, message: str | None = None) -> None:
        super().__init__(ProviderConfigErrorCode.CREDENTIAL_UNAVAILABLE, message)


class ProviderConfigVersionConflict(ProviderConfigError):
    def __init__(self, message: str | None = None) -> None:
        super().__init__(ProviderConfigErrorCode.CONFIG_VERSION_CONFLICT, message)


class ProviderProofMissing(ProviderConfigError):
    def __init__(self, message: str | None = None) -> None:
        super().__init__(ProviderConfigErrorCode.PROOF_MISSING, message)


class ProviderProofMismatch(ProviderConfigError):
    def __init__(self, message: str | None = None) -> None:
        super().__init__(ProviderConfigErrorCode.PROOF_MISMATCH, message)


@dataclass(frozen=True, slots=True)
class ActiveCompatibleBinding:
    """In-process-only view of the currently selected+proven compatible binding.

    `api_key` is raw secret bytes for immediate Authorization-header construction;
    callers MUST NOT log, repr, or persist it, and must wipe it after use.
    """

    canonical_url: str
    model: str
    api_key: bytes


class ProviderConfigService:
    def __init__(
        self,
        db: Session,
        settings: Settings,
        *,
        credential_store: ProviderCredentialStore | None = None,
        failpoint: Callable[[str], None] | None = None,
    ) -> None:
        self.db = db
        self.settings = settings
        self.credential_store = credential_store or ProviderCredentialStore()
        # Crash failpoint seam: tests inject a callable that raises at a named stage to
        # verify the surrounding transaction rolls back cleanly instead of leaving a
        # half-written config_version/proof/credential-ref combination.
        self._failpoint = failpoint or (lambda _stage: None)

    def _row(self) -> AiProviderConfig:
        row = self.db.get(AiProviderConfig, 1)
        if row is None:
            # Alembic seeds the singleton in deployed databases. Tests and other
            # metadata.create_all consumers do not run migrations, so initialize the
            # same safe Ollama default lazily instead of breaking existing AI routes.
            row = AiProviderConfig(
                singleton_id=1,
                selected_kind="ollama",
                compatible_state="absent",
                config_version=1,
            )
            self.db.add(row)
            self.db.flush()
        return row

    def _journal(
        self,
        *,
        operation: str,
        kind: AiProviderKind,
        result: str,
        reason_code: str | None,
        actor: User,
        before: int | None,
        after: int | None,
    ) -> None:
        self.db.add(
            AiProviderOperationJournal(
                operation=operation,
                kind=kind,
                result=result,
                reason_code=reason_code,
                actor_user_id=actor.id,
                config_version_before=before,
                config_version_after=after,
            )
        )

    def _check_version(self, row: AiProviderConfig, expected: int) -> None:
        if row.config_version != expected:
            raise ProviderConfigVersionConflict()

    def get_state(self) -> AiProviderConfigResponse:
        return AiProviderConfigResponse.model_validate(self._row())

    def _envelope_matches(self, row: AiProviderConfig, envelope: ProviderCredentialEnvelope | None) -> bool:
        return (
            envelope is not None
            and envelope.credential_ref == row.compatible_credential_ref
            and envelope.credential_binding_version == row.compatible_credential_binding_version
        )

    def _load_bound_plaintext(self, row: AiProviderConfig) -> bytes:
        """Loads plaintext only after the on-disk envelope's ref+binding exactly match
        the persisted DB row. A DB/envelope binding mismatch always surfaces as
        `credential_unavailable` instead of silently trusting a stale/rotated blob."""
        credential_ref = row.compatible_credential_ref
        if credential_ref is None:
            raise ProviderCredentialUnavailable()
        try:
            envelope = self.credential_store.get_envelope(credential_ref)
        except ProviderCredentialStoreError as exc:
            raise ProviderCredentialUnavailable() from exc
        if not self._envelope_matches(row, envelope):
            raise ProviderCredentialUnavailable()
        try:
            return self.credential_store.load_plaintext(credential_ref)
        except ProviderCredentialStoreError as exc:
            raise ProviderCredentialUnavailable() from exc

    def write_candidate(self, payload: AiProviderCompatibleWriteRequest, actor: User, expected_config_version: int) -> AiProviderConfigResponse:
        return self._write_candidate(payload, actor, expected_config_version=expected_config_version)

    def rotate_credential(self, payload: AiProviderCompatibleRotateRequest, actor: User) -> AiProviderConfigResponse:
        return self._write_candidate(payload, actor, expected_config_version=payload.expected_config_version)

    def _write_candidate(self, payload: AiProviderCompatibleWriteRequest, actor: User, *, expected_config_version: int) -> AiProviderConfigResponse:
        row = self._row()
        self._check_version(row, expected_config_version)
        try:
            endpoint = canonicalize_endpoint(payload.canonical_url, app_env=self.settings.app_env)
        except Exception as exc:
            raise ProviderCandidateInvalid() from exc

        before = row.config_version
        old_ref = row.compatible_credential_ref
        credential_ref = secrets.token_hex(16)
        next_binding_version = (row.compatible_credential_binding_version or 0) + 1
        try:
            envelope = self.credential_store.store_credential(
                credential_ref,
                payload.api_key.encode("utf-8"),
                binding_version=next_binding_version,
                existing_binding_version=None,
            )
        except ProviderCredentialStoreError as exc:
            self._journal(operation="rotate", kind="openai_compatible", result="failure", reason_code=exc.code.value, actor=actor, before=before, after=None)
            self.db.commit()
            raise ProviderCredentialUnavailable() from exc

        self._failpoint("write_candidate.pre_commit")
        row.compatible_canonical_url = endpoint.canonical_url
        row.compatible_display_url = payload.display_url
        row.compatible_model = payload.model
        row.compatible_generation = payload.generation
        row.compatible_credential_ref = envelope.credential_ref
        row.compatible_credential_binding_version = envelope.credential_binding_version
        row.compatible_state = "unverified"
        row.compatible_test_proof_ref = None
        row.compatible_test_proof_at = None
        row.compatible_test_proof_canonical_url = None
        row.compatible_test_proof_model = None
        row.compatible_test_proof_generation = None
        row.config_version = before + 1
        self.db.flush()
        self._journal(operation="rotate", kind="openai_compatible", result="success", reason_code=None, actor=actor, before=before, after=row.config_version)
        self.db.commit()

        if old_ref is not None and old_ref != credential_ref:
            try:
                self.credential_store.delete_credential(old_ref)
            except ProviderCredentialStoreError:
                pass  # DB is authoritative for the active ref; reconcile() catches orphans
        return AiProviderConfigResponse.model_validate(row)

    def test_candidate(self, payload: AiProviderCompatibleTestRequest, actor: User) -> AiProviderTestResultResponse:
        row = self._row()
        before = row.config_version
        if row.compatible_state == "absent" or row.compatible_canonical_url is None or row.compatible_credential_ref is None:
            raise ProviderCandidateInvalid()
        try:
            candidate_endpoint = canonicalize_endpoint(payload.canonical_url, app_env=self.settings.app_env)
        except Exception as exc:
            raise ProviderCandidateInvalid() from exc
        if (
            candidate_endpoint.canonical_url != row.compatible_canonical_url
            or payload.model != row.compatible_model
            or payload.generation != row.compatible_generation
        ):
            # Only the exact persisted candidate can be proven; stale/mismatched
            # submissions are rejected instead of silently testing something else.
            raise ProviderCandidateInvalid()

        plaintext = self._load_bound_plaintext(row)

        started = time.monotonic()
        try:
            secret = plaintext.decode("utf-8")
            outcome = probe_models(
                row.compatible_canonical_url,
                model=row.compatible_model,
                app_env=self.settings.app_env,
                api_key=secret,
                policy=self.settings.ai_compatible_egress_policy,
                peer_policy=self.settings.ai_compatible_peer_policy,
            )
        finally:
            wiped = bytearray(plaintext)
            wiped[:] = b"\0" * len(wiped)
        latency_ms = int((time.monotonic() - started) * 1000)
        tested_at = datetime.now(UTC)

        if not outcome.ok:
            self._journal(
                operation="test",
                kind="openai_compatible",
                result="failure",
                reason_code=(outcome.error_code.value if outcome.error_code else None),
                actor=actor,
                before=before,
                after=before,
            )
            self.db.commit()
            return AiProviderTestResultResponse(
                success=False,
                reason_code=outcome.error_code.value if outcome.error_code else None,
                tested_at=tested_at,
                canonical_url=row.compatible_canonical_url,
                model=row.compatible_model,
                generation=row.compatible_generation,
            )

        self._failpoint("test_compatible.pre_commit")
        row.compatible_state = "verified"
        row.compatible_test_proof_ref = secrets.token_hex(16)
        row.compatible_test_proof_at = tested_at
        row.compatible_test_proof_canonical_url = row.compatible_canonical_url
        row.compatible_test_proof_model = row.compatible_model
        row.compatible_test_proof_generation = row.compatible_generation
        row.config_version = before + 1
        self.db.flush()
        self._journal(operation="test", kind="openai_compatible", result="success", reason_code=None, actor=actor, before=before, after=row.config_version)
        self.db.commit()
        return AiProviderTestResultResponse(
            success=True,
            reason_code=None,
            tested_at=tested_at,
            canonical_url=row.compatible_canonical_url,
            model=row.compatible_model,
            generation=row.compatible_generation,
        )

    def set_selection(self, payload: AiProviderSelectionRequest, actor: User) -> AiProviderConfigResponse:
        row = self._row()
        self._check_version(row, payload.expected_config_version)
        before = row.config_version
        if payload.selected_kind == "openai_compatible" and not self._compatible_proof_bound(row):
            self._journal(operation="select", kind="openai_compatible", result="failure", reason_code="proof-not-bound", actor=actor, before=before, after=before)
            self.db.commit()
            raise ProviderSelectionInvalid()

        self._failpoint("set_selection.pre_commit")
        row.selected_kind = payload.selected_kind
        row.config_version = before + 1
        self.db.flush()
        self._journal(operation="select", kind=payload.selected_kind, result="success", reason_code=None, actor=actor, before=before, after=row.config_version)
        self.db.commit()
        return AiProviderConfigResponse.model_validate(row)

    @staticmethod
    def _compatible_proof_bound(row: AiProviderConfig) -> bool:
        return (
            row.compatible_state == "verified"
            and row.compatible_test_proof_canonical_url == row.compatible_canonical_url
            and row.compatible_test_proof_model == row.compatible_model
            and row.compatible_test_proof_generation == row.compatible_generation
        )

    def activate(self, actor: User, expected_config_version: int) -> AiProviderConfigResponse:
        """Validate the persisted compatible candidate has an exact-bound proof for the
        currently expected config version, without switching `selected_kind`.

        Activation is a readiness confirmation only; the only way traffic actually moves
        to the compatible provider is the explicit `set_selection` call, which
        independently re-checks this same proof binding before switching.
        """
        row = self._row()
        self._check_version(row, expected_config_version)
        before = row.config_version
        if row.compatible_state != "verified":
            self._journal(operation="select", kind="openai_compatible", result="failure", reason_code="proof-missing", actor=actor, before=before, after=before)
            self.db.commit()
            raise ProviderProofMissing()
        if not self._compatible_proof_bound(row):
            self._journal(operation="select", kind="openai_compatible", result="failure", reason_code="proof-mismatch", actor=actor, before=before, after=before)
            self.db.commit()
            raise ProviderProofMismatch()

        self._journal(operation="select", kind="openai_compatible", result="success", reason_code=None, actor=actor, before=before, after=before)
        self.db.commit()
        return AiProviderConfigResponse.model_validate(row)


    def delete_credential(self, payload: AiProviderCompatibleDeleteRequest, actor: User) -> AiProviderConfigResponse:
        row = self._row()
        self._check_version(row, payload.expected_config_version)
        before = row.config_version
        old_ref = row.compatible_credential_ref

        self._failpoint("delete_candidate.pre_commit")
        row.compatible_state = "absent"
        row.compatible_canonical_url = None
        row.compatible_display_url = None
        row.compatible_model = None
        row.compatible_generation = None
        row.compatible_credential_ref = None
        row.compatible_credential_binding_version = None
        row.compatible_test_proof_ref = None
        row.compatible_test_proof_at = None
        row.compatible_test_proof_canonical_url = None
        row.compatible_test_proof_model = None
        row.compatible_test_proof_generation = None
        row.config_version = before + 1
        self.db.flush()
        self._journal(operation="delete", kind="openai_compatible", result="success", reason_code=None, actor=actor, before=before, after=row.config_version)
        self.db.commit()

        if old_ref is not None:
            try:
                self.credential_store.delete_credential(old_ref)
            except ProviderCredentialStoreError:
                pass
        return AiProviderConfigResponse.model_validate(row)

    def reconcile(self, actor: User) -> AiProviderReconcileResponse:
        row = self._row()
        before = row.config_version
        reconciled = True

        if row.compatible_credential_ref is not None:
            try:
                envelope = self.credential_store.get_envelope(row.compatible_credential_ref)
            except ProviderCredentialStoreError:
                envelope = None
            if not self._envelope_matches(row, envelope):
                reconciled = False
                self._failpoint("reconcile.pre_commit")
                if row.compatible_state == "verified":
                    row.compatible_state = "unverified"
                row.compatible_test_proof_ref = None
                row.compatible_test_proof_at = None
                row.compatible_test_proof_canonical_url = None
                row.compatible_test_proof_model = None
                row.compatible_test_proof_generation = None
                row.config_version = before + 1
                self.db.flush()

        self._journal(
            operation="reconcile",
            kind=row.selected_kind,
            result="success" if reconciled else "failure",
            reason_code=None if reconciled else "credential-drift",
            actor=actor,
            before=before,
            after=row.config_version,
        )
        self.db.commit()
        return AiProviderReconcileResponse(reconciled=reconciled, compatible_state=row.compatible_state, config_version=row.config_version)

    def load_active_compatible_binding(self) -> ActiveCompatibleBinding:
        """Returns the exact-bound, live-selected compatible endpoint + credential.

        Raises `ProviderSelectionInvalid` if `selected_kind` is not currently
        'openai_compatible' with a proof still bound to the persisted candidate —
        this is the only place service.py may obtain compatible credential bytes,
        and it is only ever called from the request-time chat path after
        `selected_kind` was already confirmed explicitly, never as a fallback probe.
        """
        row = self._row()
        if row.selected_kind != "openai_compatible" or not self._compatible_proof_bound(row) or row.compatible_credential_ref is None:
            raise ProviderSelectionInvalid()
        if row.compatible_canonical_url is None or row.compatible_model is None:
            raise ProviderSelectionInvalid()
        plaintext = self._load_bound_plaintext(row)
        return ActiveCompatibleBinding(canonical_url=row.compatible_canonical_url, model=row.compatible_model, api_key=plaintext)
