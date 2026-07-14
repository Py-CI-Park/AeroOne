"""Office job ownership, retention, recovery, and durable destructive-operation APIs."""

from __future__ import annotations

import re
from uuid import uuid4
from typing import Any, Iterator
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask

from app.db.session import get_session_factory
from app.modules.admin.audit import record_admin_audit, redact_audit_metadata
from app.modules.auth.dependencies import get_current_user, get_db, require_csrf, require_permission
from app.modules.auth.models import User
from app.modules.office_tools.core.job_store import (
    OfficeJobArtifactReadLease,
    OfficeJobCapacityError,
    OfficeJobCorruptionError,
    OfficeJobDeletionError,
    OfficeJobDirectMutationError,
    OfficeJobOwnerDeletionError,
    OfficeJobPendingResultError,
    OfficeJobPurgeError,
    OfficeJobStore,
    strict_owner_id,
)
from app.modules.office_tools.schemas import (
    OfficeJobAuditPersistenceStateResponse,
    OfficeJobDetailResponse,
    OfficeJobDirectMutationFailureResponse,
    OfficeJobDirectMutationOutcomeResponse,
    OfficeJobDirectMutationPartialFailureDetail,
    OfficeJobEvidenceDispositionResponse,
    OfficeJobListItemResponse,
    OfficeJobListResponse,
    OfficeJobOwnerDeletionFailureResponse,
    OfficeJobOwnerDeletionOutcomeResponse,
    OfficeJobOwnerDeletionPartialFailureDetail,
    OfficeJobOwnerDeletionResponse,
    OfficeJobOwnerIdentityInventoryResponse,
    OfficeJobPurgeFailureResponse,
    OfficeJobPurgePartialFailureDetail,
    OfficeJobPurgeResponse,
    OfficeJobPendingReceiptInventoryResponse,
    OfficeJobPendingReceiptReplayResponse,
    OfficeJobQuarantineActionResponse,
    OfficeJobQuarantineInventoryResponse,
    OfficeJobRecoveryActionResponse,
    OfficeJobRecoveryInventoryResponse,
    OfficeJobStorageAccountingResponse,
    OfficeJobUnresolvedMutationFailureResponse,
    OfficeJobUnresolvedMutationFailureDetail,
    OfficeJobUsageResponse,
)

router = APIRouter(tags=['office-tools'])


_DIRECT_MUTATION_FAILURE_RESPONSE = {
    status.HTTP_500_INTERNAL_SERVER_ERROR: {
        'model': OfficeJobDirectMutationFailureResponse,
        'description': 'The mutation outcome or its durable audit receipt requires recovery.',
    },
}
_OWNER_DELETION_FAILURE_RESPONSE = {
    status.HTTP_500_INTERNAL_SERVER_ERROR: {
        'model': OfficeJobOwnerDeletionFailureResponse,
        'description': 'The owner deletion outcome or its durable audit receipt requires recovery.',
    },
}
_PURGE_FAILURE_RESPONSE = {
    status.HTTP_500_INTERNAL_SERVER_ERROR: {
        'model': OfficeJobPurgeFailureResponse,
        'description': 'Purge completed partially or its durable audit receipt requires recovery.',
    },
}
_BUNDLE_CLEANUP_FAILURE_RESPONSE = {
    status.HTTP_500_INTERNAL_SERVER_ERROR: {
        'model': OfficeJobUnresolvedMutationFailureResponse,
        'description': 'The temporary bundle was retained because its cleanup receipt is unresolved.',
    },
}


class OfficeJobAuditPersistenceError(RuntimeError):
    """A receipt remains on disk because its audit acknowledgement could not finish."""

    def __init__(
        self,
        state: OfficeJobAuditPersistenceStateResponse,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.state = state
        self.metadata = metadata
        super().__init__('office job audit persistence failed')


def get_office_job_store(request: Request) -> OfficeJobStore:
    return request.app.state.office_job_store


def _load_owned_job(store: OfficeJobStore, job_id: str, user: User) -> dict[str, object]:
    """Load a job only after strict ownership validation."""
    try:
        owner_id = strict_owner_id(user.id)
        record = store.get(job_id)
        record_owner_id = strict_owner_id(record.get('owner_id'))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='job not found') from exc
    except OfficeJobCorruptionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='invalid job owner') from exc
    if record_owner_id != owner_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='job belongs to another user')
    return record


def _usage_response(store: OfficeJobStore, owner_id: int) -> OfficeJobUsageResponse:
    usage = store.usage_for_owner(owner_id)
    return OfficeJobUsageResponse(
        **usage,
        max_jobs_per_owner=store.max_jobs_per_owner,
        max_bytes_per_owner=store.max_bytes_per_owner,
    )


def _completed_display_metadata(record: dict[str, Any]) -> tuple[str | None, bool | None]:
    """완료된 검증 record의 표시 전용 메타데이터만 목록에 노출한다."""
    if record['status'] != 'completed':
        return None, None
    title = record.get('title')
    llm_used = record.get('llm_used')
    return (
        title if isinstance(title, str) else None,
        llm_used if isinstance(llm_used, bool) else None,
    )


def _request_provenance(actor: User, request: Request) -> dict[str, Any]:
    """Capture only immutable request/actor evidence before a destructive operation starts."""
    return {
        'actor_id': strict_owner_id(actor.id),
        'actor_username': actor.username,
        'actor_role': actor.role,
        'method': request.method,
        'path': str(request.url.path),
        'ip_address': request.client.host if request.client else None,
        'user_agent': request.headers.get('user-agent'),
        'request_id': request.headers.get('x-request-id'),
        'request_available': True,
    }


def _sanitized_receipt_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """Keep durable recovery evidence aligned with the audit redaction contract."""
    sanitized = redact_audit_metadata(metadata)
    return dict(sanitized) if isinstance(sanitized, dict) else {}

def _without_replay_evidence(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _without_replay_evidence(item)
            for key, item in value.items()
            if key != '_replay_evidence'
        }
    if isinstance(value, list):
        return [_without_replay_evidence(item) for item in value]
    return value


def _audit_metadata(value: dict[str, Any]) -> dict[str, Any]:
    clean = _without_replay_evidence(value)
    return dict(clean) if isinstance(clean, dict) else {}

def _receipt_state(
    pending_result_id: str,
    *,
    state: str,
    retry_required: bool,
    outcome_known: bool,
) -> OfficeJobAuditPersistenceStateResponse:
    valid_states = {
        'prepared',
        'mutation_started',
        'result_ready',
        'audit_persisted',
        'audit_failed',
        'unresolved',
    }
    return OfficeJobAuditPersistenceStateResponse(
        pending_result_id=pending_result_id,
        state=state if state in valid_states else 'unresolved',
        # Every emitted state has a durable receipt that still needs recovery.
        retry_required=True,
        outcome_known=outcome_known,
    )


def _receipt_state_from_record(record: dict[str, Any]) -> OfficeJobAuditPersistenceStateResponse:
    phase = record.get('phase')
    raw_state = str(record.get('state', 'unresolved'))
    receipt_state = 'mutation_started' if raw_state == 'prepared' and phase == 1 else raw_state
    return _receipt_state(
        str(record['pending_result_id']),
        state=receipt_state,
        retry_required=True,
        outcome_known=record.get('outcome_state') == 'recorded',
    )


def _unresolved_failure_response(
    error: str,
    persistence: OfficeJobAuditPersistenceStateResponse,
    *,
    metadata: dict[str, Any] | None = None,
) -> HTTPException:
    sanitized_metadata = (
        _audit_metadata(_sanitized_receipt_metadata(metadata)) if isinstance(metadata, dict) else None
    )
    detail = OfficeJobUnresolvedMutationFailureDetail(
        error=error,
        audit_persistence=persistence,
        unresolved=persistence.state in {'prepared', 'mutation_started', 'unresolved'},
        outcome=sanitized_metadata.get('outcome') if sanitized_metadata is not None else None,
        partial_result=sanitized_metadata.get('partial_result')
        if sanitized_metadata is not None
        else None,
        receipt_metadata=sanitized_metadata,
    )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=detail.model_dump(mode='json', exclude_none=True),
    )


def _audit_persistence_failure_response(exc: OfficeJobAuditPersistenceError) -> HTTPException:
    return _unresolved_failure_response(
        'office job audit persistence failed',
        exc.state,
        metadata=exc.metadata,
    )


def _audit_idempotency_key(pending_result_id: str, phase: str) -> str:
    return f'{pending_result_id}:{phase}'


def _outcome_requires_durability_replay(value: object) -> bool:
    return (
        isinstance(value, dict)
        and value.get('removed') is True
        and value.get('durably_synced') is False
        and value.get('durability') != 'platform_best_effort'
        and value.get('retry_required') is not False
    )


def _metadata_requires_durability_replay(metadata: dict[str, Any]) -> bool:
    if _outcome_requires_durability_replay(metadata.get('outcome')):
        return True
    partial_result = metadata.get('partial_result')
    outcomes = (
        partial_result.get('partial_deletion_outcomes')
        if isinstance(partial_result, dict)
        else None
    )
    return isinstance(outcomes, list) and any(
        _outcome_requires_durability_replay(outcome) for outcome in outcomes
    )


def _replay_pending_durability_evidence(
    store: OfficeJobStore,
    *,
    pending: dict[str, Any],
    metadata: dict[str, Any],
    action: str,
    target_id: str,
    intent: dict[str, Any],
) -> None:
    """Confirm known filesystem removal before acknowledging its durable receipt."""
    if not _metadata_requires_durability_replay(metadata):
        return
    if action == 'office_jobs.purge_expired':
        partial_result = metadata.get('partial_result')
        replay_evidence = metadata.get('_replay_evidence')
        if not isinstance(partial_result, dict):
            raise ValueError('purge durability receipt is invalid')
        store.reconcile_purge_partial_durability(partial_result, replay_evidence)
        return
    if action == 'office_jobs.owner_delete':
        owner_id = strict_owner_id(intent.get('owner_id', pending['actor_id']))
        outcome = store.delete_for_owner_outcome(target_id, owner_id)
        if outcome is None or outcome['retry_required']:
            raise OSError('owner deletion durability replay is incomplete')
        return
    outcome = metadata.get('outcome')
    replay_evidence = intent.get('_replay_evidence')
    if not isinstance(outcome, dict):
        raise ValueError('direct mutation durability receipt is invalid')
    store.reconcile_direct_mutation_durability(
        outcome,
        replay_evidence,
        receipt_target_id=target_id,
    )


def _phase_one_nonbundle_recovery(
    store: OfficeJobStore,
    db: Session,
    *,
    pending: dict[str, Any],
    receipt_state: OfficeJobAuditPersistenceStateResponse,
    provenance: dict[str, Any],
    metadata: dict[str, Any],
    action: str,
    target_type: str,
    target_id: str,
    intent: dict[str, Any],
) -> None:
    """Resume only phase-one work with durable, operation-specific recovery evidence."""
    if action != 'office_jobs.owner_delete':
        replay_evidence = intent.get('_replay_evidence')
        if replay_evidence is None:
            raise OfficeJobAuditPersistenceError(
                receipt_state,
                {
                    'intent': intent,
                    'error': 'mutation outcome is unresolved after the durable boundary',
                },
            )
        try:
            outcome = store.recover_direct_mutation_outcome(
                action=action,
                target_id=target_id,
                replay_evidence=replay_evidence,
            )
        except Exception as exc:
            raise OfficeJobAuditPersistenceError(
                receipt_state,
                {
                    'intent': intent,
                    'error': 'mutation outcome replay evidence is invalid',
                },
            ) from exc
        resumed_metadata = {'intent': intent, 'outcome': dict(outcome)}
        persistence = _commit_pending_result_audit(
            store,
            db,
            pending_result_id=str(pending['pending_result_id']),
            action=action,
            target_type=target_type,
            target_id=target_id,
            provenance=provenance,
            metadata=resumed_metadata,
            audit_status='success',
            outcome_record_failure_state='mutation_started',
        )
        if persistence is not None:
            raise OfficeJobAuditPersistenceError(persistence, resumed_metadata)
        return
    try:
        owner_intent = store.owner_deletion_intent(
            target_id,
            strict_owner_id(intent.get('owner_id', pending['actor_id'])),
        )
    except (FileNotFoundError, OfficeJobCorruptionError, PermissionError, ValueError) as exc:
        raise OfficeJobAuditPersistenceError(
            receipt_state,
            {
                'intent': intent,
                'error': 'owner deletion recovery has no durable source',
            },
        ) from exc
    if (
        owner_intent.get('stored_outcome') is None
        and not owner_intent.get('retrying_sidecar_cleanup')
        and not owner_intent.get('tombstone_pending')
    ):
        raise OfficeJobAuditPersistenceError(
            receipt_state,
            {
                'intent': intent,
                'error': 'owner deletion recovery has no durable source',
            },
        )
    owner_id = strict_owner_id(intent.get('owner_id', pending['actor_id']))
    try:
        outcome = store.delete_for_owner_outcome(target_id, owner_id)
    except OfficeJobOwnerDeletionError as exc:
        known_metadata = {
            'error': 'office job deletion partially failed',
            'intent': intent,
            'outcome': dict(exc.outcome),
        }
        persistence = _commit_pending_result_audit(
            store,
            db,
            pending_result_id=str(pending['pending_result_id']),
            action=action,
            target_type=target_type,
            target_id=target_id,
            provenance=provenance,
            metadata=known_metadata,
            audit_status='partial_failure',
            outcome_record_failure_state='mutation_started',
        )
        if persistence is not None:
            raise OfficeJobAuditPersistenceError(persistence, known_metadata) from exc
        return
    except Exception as exc:
        raise OfficeJobAuditPersistenceError(receipt_state, metadata) from exc
    if outcome is None:
        raise OfficeJobAuditPersistenceError(receipt_state, metadata)
    resumed_metadata = {'intent': intent, 'outcome': dict(outcome)}
    persistence = _commit_pending_result_audit(
        store,
        db,
        pending_result_id=str(pending['pending_result_id']),
        action=action,
        target_type=target_type,
        target_id=target_id,
        provenance=provenance,
        metadata=resumed_metadata,
        audit_status='success' if not outcome['retry_required'] else 'partial_failure',
        outcome_record_failure_state='mutation_started',
    )
    if persistence is not None:
        raise OfficeJobAuditPersistenceError(persistence, resumed_metadata)

def _persist_pending_intent_audit(
    db: Session,
    *,
    pending_result_id: str,
    action: str,
    target_type: str,
    target_id: str,
    provenance: dict[str, Any],
    intent: dict[str, Any],
    failure_state: OfficeJobAuditPersistenceStateResponse | None = None,
) -> OfficeJobAuditPersistenceStateResponse | None:
    """Commit the immutable pre-mutation intent with a key distinct from its result."""
    try:
        record_admin_audit(
            db,
            actor=None,
            action=f'{action}.intent',
            target_type=target_type,
            target_id=target_id,
            metadata=_audit_metadata(intent),
            status='intent',
            provenance=provenance,
            idempotency_key=_audit_idempotency_key(pending_result_id, 'intent'),
        )
        db.commit()
    except Exception:
        db.rollback()
        return failure_state or _receipt_state(
            pending_result_id,
            state='prepared',
            retry_required=True,
            outcome_known=False,
        )
    return None
def _store_pending_outcome(
    store: OfficeJobStore,
    *,
    pending_result_id: str,
    metadata: dict[str, Any],
    audit_status: str,
    failure_state: str = 'mutation_started',
    replace_result: bool = False,
) -> OfficeJobAuditPersistenceStateResponse | None:
    try:
        store.record_pending_result(
            pending_result_id,
            metadata=metadata,
            audit_status=audit_status,
            replace_result=replace_result,
        )
    except OfficeJobPendingResultError as exc:
        return _receipt_state(
            exc.pending_result_id,
            state=failure_state,
            retry_required=True,
            outcome_known=True,
        )
    return None




def _bundle_cleanup_outcome_is_complete(metadata: dict[str, Any]) -> bool:
    outcome = metadata.get('outcome')
    if not isinstance(outcome, dict):
        return False
    if outcome.get('result') in {'not_materialized', 'not_started'}:
        return True
    return (
        outcome.get('removed') is True
        and (
            outcome.get('durably_synced') is True
            or outcome.get('durability') == 'platform_best_effort'
            or outcome.get('retry_required') is False
        )
    )

def _persist_recorded_pending_audit(
    store: OfficeJobStore,
    db: Session,
    *,
    pending_result_id: str,
    action: str,
    target_type: str,
    target_id: str,
    provenance: dict[str, Any],
    metadata: dict[str, Any],
    audit_status: str,
) -> OfficeJobAuditPersistenceStateResponse | None:
    """Commit one idempotent audit row from receipt provenance, then acknowledge the receipt."""
    if action == 'office_jobs.bundle.cleanup' and not _bundle_cleanup_outcome_is_complete(metadata):
        return _receipt_state(
            pending_result_id,
            state='result_ready',
            retry_required=True,
            outcome_known=True,
        )
    try:
        record_admin_audit(
            db,
            actor=None,
            action=action,
            target_type=target_type,
            target_id=target_id,
            metadata=_audit_metadata(metadata),
            status=audit_status,
            provenance=provenance,
            idempotency_key=_audit_idempotency_key(pending_result_id, 'result'),
        )
        db.commit()
    except Exception:
        db.rollback()
        return _receipt_state(
            pending_result_id,
            state='result_ready',
            retry_required=True,
            outcome_known=True,
        )
    try:
        store.mark_pending_result_audited(pending_result_id)
    except Exception:
        return _receipt_state(
            pending_result_id,
            state='audit_persisted',
            retry_required=True,
            outcome_known=True,
        )
    if _metadata_requires_durability_replay(metadata):
        return _receipt_state(
            pending_result_id,
            state='audit_persisted',
            retry_required=True,
            outcome_known=True,
        )
    try:
        store.acknowledge_pending_result(pending_result_id)
    except Exception:
        return _receipt_state(
            pending_result_id,
            state='audit_persisted',
            retry_required=True,
            outcome_known=True,
        )
    return None


def _commit_pending_result_audit(
    store: OfficeJobStore,
    db: Session,
    *,
    pending_result_id: str,
    action: str,
    target_type: str,
    target_id: str,
    provenance: dict[str, Any],
    metadata: dict[str, Any],
    audit_status: str,
    outcome_record_failure_state: str = 'mutation_started',
) -> OfficeJobAuditPersistenceStateResponse | None:
    """Durably store the actual result before the idempotent DB audit commit."""
    metadata = _sanitized_receipt_metadata(metadata)
    persistence = _store_pending_outcome(
        store,
        pending_result_id=pending_result_id,
        metadata=metadata,
        audit_status=audit_status,
        failure_state=outcome_record_failure_state,
    )
    if persistence is not None:
        return persistence
    return _persist_recorded_pending_audit(
        store,
        db,
        pending_result_id=pending_result_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        provenance=provenance,
        metadata=metadata,
        audit_status=audit_status,
    )


def _bundle_cleanup_id(target_id: str) -> str:
    match = re.fullmatch(r'bundle-([0-9a-f]{32})\.zip', target_id)
    if match is None:
        raise ValueError('temporary bundle cleanup target is invalid')
    return match.group(1)
def _bind_temporary_bundle_cleanup_evidence(
    store: OfficeJobStore,
    *,
    pending_result_id: str,
    bundle_id: str,
    intent: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Persist exact bundle identity before its cleanup may unlink the target."""
    existing = intent.get('_replay_evidence')
    if existing is None:
        evidence = store.temporary_bundle_replay_evidence(bundle_id)
        receipt = store.attach_pending_result_replay_evidence(
            pending_result_id,
            evidence,
        )
        bound_intent = dict(receipt['intent'])
    elif isinstance(existing, dict):
        evidence = dict(existing)
        bound_intent = dict(intent)
    else:
        raise ValueError('temporary bundle replay evidence is invalid')
    store.validate_temporary_bundle_replay_evidence(bundle_id, evidence)
    return bound_intent, evidence
def _bundle_cleanup_requires_replay(
    pending: dict[str, Any],
    metadata: dict[str, Any],
) -> bool:
    """Route only incomplete, mutation-started bundle receipts through cleanup."""
    state = pending.get('state')
    phase = pending.get('phase')
    if state == 'prepared':
        if phase == 0:
            return False
        if phase == 1:
            return True
    elif state == 'result_ready':
        if phase == 2:
            return not _bundle_cleanup_outcome_is_complete(metadata)
    elif state == 'audit_persisted':
        if phase == 3:
            return not _bundle_cleanup_outcome_is_complete(metadata)
    raise ValueError('temporary bundle cleanup receipt lifecycle is invalid')


def _merge_bundle_cleanup_outcome(
    previous: object,
    current: dict[str, Any],
) -> dict[str, Any]:
    """Keep observed deletion bytes while only advancing completion facts."""
    merged = dict(current)
    if not isinstance(previous, dict):
        return merged

    def bytes_from(value: object) -> int:
        return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0

    physical_bytes = max(
        bytes_from(previous.get('physical_bytes')),
        bytes_from(merged.get('physical_bytes')),
    )
    partial_bytes_removed = max(
        bytes_from(previous.get('partial_bytes_removed')),
        bytes_from(merged.get('partial_bytes_removed')),
    )
    removed = previous.get('removed') is True or merged.get('removed') is True
    previous_best_effort = previous.get('durability') == 'platform_best_effort'
    current_best_effort = merged.get('durability') == 'platform_best_effort'
    durably_synced = previous.get('durably_synced') is True or merged.get('durably_synced') is True
    if physical_bytes or 'physical_bytes' in previous or 'physical_bytes' in merged:
        merged['physical_bytes'] = physical_bytes
    if removed:
        partial_bytes_removed = max(partial_bytes_removed, physical_bytes)
        merged['removed'] = True
    if partial_bytes_removed or 'partial_bytes_removed' in previous or 'partial_bytes_removed' in merged:
        merged['partial_bytes_removed'] = partial_bytes_removed
    if previous_best_effort or current_best_effort:
        merged['durably_synced'] = False
        merged['durability'] = 'platform_best_effort'
    elif durably_synced:
        merged['durably_synced'] = True
        merged['durability'] = 'synced'
    return merged


def _bundle_cleanup_metadata(
    action: str,
    intent: dict[str, Any],
    outcome: dict[str, Any] | None,
    *,
    previous_outcome: object = None,
) -> tuple[dict[str, Any], str]:
    if outcome is None:
        return (
            {
                'intent': intent,
                'outcome': {'operation': action, 'result': 'not_found'},
            },
            'partial_failure',
        )
    return (
        {
            'intent': intent,
            'outcome': _merge_bundle_cleanup_outcome(previous_outcome, outcome),
        },
        'success',
    )


def _replay_temporary_bundle_cleanup(
    store: OfficeJobStore,
    db: Session,
    *,
    pending: dict[str, Any],
    receipt_state: OfficeJobAuditPersistenceStateResponse,
    provenance: dict[str, Any],
    metadata: dict[str, Any],
    action: str,
    target_type: str,
    target_id: str,
    intent: dict[str, Any],
) -> None:
    """Delete one reserved bundle before its receipt can be acknowledged."""
    pending_result_id = str(pending['pending_result_id'])
    try:
        bundle_id = _bundle_cleanup_id(target_id)
    except ValueError as exc:
        raise OfficeJobAuditPersistenceError(receipt_state, metadata) from exc
    current_state = receipt_state
    state = str(pending['state'])
    try:
        if not _bundle_cleanup_requires_replay(pending, metadata):
            raise ValueError('temporary bundle cleanup does not require replay')
    except ValueError as exc:
        raise OfficeJobAuditPersistenceError(receipt_state, metadata) from exc
    if state == 'prepared':
        try:
            provenance = _begin_pending_result_mutation(
                store,
                pending_result_id=pending_result_id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                fallback_provenance=provenance,
            )
        except HTTPException as exc:
            raise OfficeJobAuditPersistenceError(current_state, metadata) from exc
        current_state = _receipt_state(
            pending_result_id,
            state='mutation_started',
            retry_required=True,
            outcome_known=False,
        )
    try:
        intent, replay_evidence = _bind_temporary_bundle_cleanup_evidence(
            store,
            pending_result_id=pending_result_id,
            bundle_id=bundle_id,
            intent=intent,
        )
        prior_outcome = metadata.get('outcome')
        if _outcome_requires_durability_replay(prior_outcome):
            deletion = store.reconcile_temporary_bundle_durability(
                prior_outcome,
                replay_evidence,
            )
        else:
            deletion = store.delete_temporary_bundle_with_replay_evidence(
                bundle_id,
                replay_evidence,
            )
    except OfficeJobDeletionError as exc:
        partial_metadata = _sanitized_receipt_metadata(
            {
                'error': 'temporary bundle cleanup partially failed',
                'intent': intent,
                'outcome': _merge_bundle_cleanup_outcome(
                    metadata.get('outcome'),
                    dict(exc.outcome),
                ),
            }
        )
        if state in {'prepared', 'result_ready'}:
            persistence = _store_pending_outcome(
                store,
                pending_result_id=pending_result_id,
                metadata=partial_metadata,
                audit_status='partial_failure',
                failure_state=current_state.state,
                replace_result=state == 'result_ready',
            )
            if persistence is not None:
                raise OfficeJobAuditPersistenceError(persistence, partial_metadata) from exc
            metadata = partial_metadata
            current_state = _receipt_state(
                pending_result_id,
                state='result_ready',
                retry_required=True,
                outcome_known=True,
            )
        raise OfficeJobAuditPersistenceError(current_state, metadata) from exc
    except Exception as exc:
        raise OfficeJobAuditPersistenceError(current_state, metadata) from exc
    if state == 'audit_persisted':
        try:
            store.acknowledge_pending_result(pending_result_id)
        except Exception as exc:
            raise OfficeJobAuditPersistenceError(current_state, metadata) from exc
        return
    replacement_metadata, replacement_status = _bundle_cleanup_metadata(
        action,
        intent,
        deletion,
        previous_outcome=metadata.get('outcome'),
    )
    replacement_metadata = _sanitized_receipt_metadata(replacement_metadata)
    should_replace = (
        state == 'prepared'
        or (
            state == 'result_ready'
            and not _bundle_cleanup_outcome_is_complete(metadata)
        )
    )
    if should_replace:
        persistence = _store_pending_outcome(
            store,
            pending_result_id=pending_result_id,
            metadata=replacement_metadata,
            audit_status=replacement_status,
            failure_state=current_state.state,
            replace_result=state == 'result_ready',
        )
        if persistence is not None:
            raise OfficeJobAuditPersistenceError(persistence, replacement_metadata)
        metadata = replacement_metadata
        audit_status = replacement_status
        current_state = _receipt_state(
            pending_result_id,
            state='result_ready',
            retry_required=True,
            outcome_known=True,
        )
    else:
        metadata = _sanitized_receipt_metadata(metadata)
        audit_status = str(pending['audit_status'])
    intent_persistence = _persist_pending_intent_audit(
        db,
        pending_result_id=pending_result_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        provenance=provenance,
        intent=intent,
        failure_state=current_state,
    )
    if intent_persistence is not None:
        raise OfficeJobAuditPersistenceError(intent_persistence, metadata)
    persistence = _persist_recorded_pending_audit(
        store,
        db,
        pending_result_id=pending_result_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        provenance=provenance,
        metadata=metadata,
        audit_status=audit_status,
    )
    if persistence is not None:
        raise OfficeJobAuditPersistenceError(persistence, metadata)



def _receipt_provenance(
    pending: dict[str, Any],
    receipt_state: OfficeJobAuditPersistenceStateResponse,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    provenance = dict(pending['request_provenance'])
    original_actor_id = strict_owner_id(pending['actor_id'])
    stored_actor_id = provenance.get('actor_id')
    if stored_actor_id is not None and stored_actor_id != original_actor_id:
        raise OfficeJobAuditPersistenceError(receipt_state, metadata)
    provenance['actor_id'] = original_actor_id
    return provenance


def _reconcile_pending_result_audit(
    store: OfficeJobStore,
    db: Session,
    *,
    pending_result_id: str,
) -> None:
    """Replay one validated receipt with its immutable original provenance and idempotency keys."""
    pending = store.get_pending_result(pending_result_id)
    receipt_state = _receipt_state_from_record(pending)
    metadata = dict(pending.get('audit_metadata', {}))
    provenance = _receipt_provenance(pending, receipt_state, metadata)
    action = str(pending['action'])
    target_type = str(pending['target_type'])
    target_id = str(pending['target_id'])
    intent = dict(pending['intent'])
    if action == 'office_jobs.bundle.cleanup':
        try:
            bundle_replay_required = _bundle_cleanup_requires_replay(pending, metadata)
        except ValueError as exc:
            raise OfficeJobAuditPersistenceError(receipt_state, metadata) from exc
        if bundle_replay_required:
            _replay_temporary_bundle_cleanup(
                store,
                db,
                pending=pending,
                receipt_state=receipt_state,
                provenance=provenance,
                metadata=metadata,
                action=action,
                target_type=target_type,
                target_id=target_id,
                intent=intent,
            )
            return

    intent_persistence = _persist_pending_intent_audit(
        db,
        pending_result_id=pending_result_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        provenance=provenance,
        intent=intent,
        failure_state=receipt_state,
    )
    if intent_persistence is not None:
        raise OfficeJobAuditPersistenceError(intent_persistence, metadata)

    if pending['state'] == 'prepared':
        if pending.get('phase') == 1:
            _phase_one_nonbundle_recovery(
                store,
                db,
                pending=pending,
                receipt_state=receipt_state,
                provenance=provenance,
                metadata=metadata,
                action=action,
                target_type=target_type,
                target_id=target_id,
                intent=intent,
            )
            return
        if pending.get('phase') != 0:
            raise OfficeJobAuditPersistenceError(receipt_state, metadata)
        not_started_metadata = {
            'intent': intent,
            'outcome': {'operation': action, 'result': 'not_started'},
            'error': 'mutation did not start before recovery',
        }
        persistence = _commit_pending_result_audit(
            store,
            db,
            pending_result_id=pending_result_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            provenance=provenance,
            metadata=not_started_metadata,
            audit_status='partial_failure',
            outcome_record_failure_state='prepared',
        )
        if persistence is not None:
            raise OfficeJobAuditPersistenceError(persistence, not_started_metadata)
        return
    try:
        _replay_pending_durability_evidence(
            store,
            pending=pending,
            metadata=metadata,
            action=action,
            target_id=target_id,
            intent=intent,
        )
    except Exception as exc:
        raise OfficeJobAuditPersistenceError(receipt_state, metadata) from exc
    if pending['state'] == 'audit_persisted':
        try:
            store.acknowledge_pending_result(pending_result_id)
        except Exception as exc:
            raise OfficeJobAuditPersistenceError(receipt_state, metadata) from exc
        return

    persistence = _persist_recorded_pending_audit(
        store,
        db,
        pending_result_id=pending_result_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        provenance=provenance,
        metadata=metadata,
        audit_status=str(pending['audit_status']),
    )
    if persistence is not None:
        raise OfficeJobAuditPersistenceError(persistence, metadata)


def _reconcile_pending_result_audits(store: OfficeJobStore, db: Session, *, actor: User) -> None:
    """Replay receipts using the original actor/request provenance."""
    for pending in store.list_pending_results_for_actor(strict_owner_id(actor.id)):
        _reconcile_pending_result_audit(
            store,
            db,
            pending_result_id=str(pending['pending_result_id']),
        )


def _record_pending_receipt_replay_audit(
    db: Session,
    *,
    actor: User,
    request: Request,
    pending_result_id: str,
    audit_status: str,
    result: str,
) -> None:
    """Audit the operator's recovery trigger without altering the receipt's original provenance."""
    action = (
        'office_jobs.pending_receipt.replay.intent'
        if audit_status == 'intent'
        else 'office_jobs.pending_receipt.replay'
    )
    try:
        record_admin_audit(
            db,
            actor=actor,
            action=action,
            target_type='office_job_pending_receipt',
            target_id=pending_result_id,
            request=request,
            metadata={'result': result},
            status=audit_status,
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='pending receipt operator audit could not be persisted',
        ) from exc


def _prepare_pending_result(
    store: OfficeJobStore,
    *,
    actor: User,
    request: Request,
    action: str,
    target_type: str,
    target_id: str,
    intent: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    provenance = _request_provenance(actor, request)
    try:
        pending_result_id = store.prepare_pending_result(
            actor_id=strict_owner_id(actor.id),
            action=action,
            target_type=target_type,
            target_id=target_id,
            intent=intent,
            request_provenance=provenance,
        )
    except OfficeJobPendingResultError as exc:
        raise _unresolved_failure_response(
            'office job mutation receipt could not be prepared',
            _receipt_state(
                exc.pending_result_id,
                state='unresolved',
                retry_required=True,
                outcome_known=bool(exc.outcome),
            ),
            metadata=exc.outcome or None,
        ) from exc
    return pending_result_id, provenance


def _begin_pending_result_mutation(
    store: OfficeJobStore,
    *,
    pending_result_id: str,
    action: str,
    target_type: str,
    target_id: str,
    fallback_provenance: dict[str, Any],
) -> dict[str, Any]:
    try:
        receipt = store.begin_pending_result_mutation(
            pending_result_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
        )
    except OfficeJobPendingResultError as exc:
        raise _unresolved_failure_response(
            'office job mutation boundary could not be recorded',
            _receipt_state(
                exc.pending_result_id,
                state='prepared',
                retry_required=True,
                outcome_known=bool(exc.outcome),
            ),
            metadata=exc.outcome or None,
        ) from exc
    stored = receipt.get('request_provenance')
    return dict(stored) if isinstance(stored, dict) else fallback_provenance


def _known_nonmutation_failure(
    store: OfficeJobStore,
    db: Session,
    *,
    pending_result_id: str,
    action: str,
    target_type: str,
    target_id: str,
    provenance: dict[str, Any],
    intent: dict[str, Any],
    result: str,
    error: str,
) -> tuple[OfficeJobAuditPersistenceStateResponse | None, dict[str, Any]]:
    metadata = {
        'intent': intent,
        'outcome': {'operation': action, 'result': result},
        'error': error,
    }
    return (
        _commit_pending_result_audit(
            store,
            db,
            pending_result_id=pending_result_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            provenance=provenance,
            metadata=metadata,
            audit_status='partial_failure',
        ),
        metadata,
    )


def _unresolved_after_mutation_started(
    pending_result_id: str,
    error: str,
) -> HTTPException:
    return _unresolved_failure_response(
        error,
        _receipt_state(
            pending_result_id,
            state='mutation_started',
            retry_required=True,
            outcome_known=False,
        ),
    )


def _direct_mutation_partial_failure(
    store: OfficeJobStore,
    db: Session,
    *,
    pending_result_id: str,
    action: str,
    target_type: str,
    target_id: str,
    provenance: dict[str, Any],
    intent: dict[str, Any],
    exc: OfficeJobDirectMutationError,
    error: str,
) -> HTTPException:
    outcome = OfficeJobDirectMutationOutcomeResponse(**exc.outcome)
    metadata = {'error': error, 'intent': intent, 'outcome': dict(exc.outcome)}
    persistence = _commit_pending_result_audit(
        store,
        db,
        pending_result_id=pending_result_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        provenance=provenance,
        metadata=metadata,
        audit_status='partial_failure',
    )
    if persistence is not None and not (
        persistence.state == 'audit_persisted'
        and _metadata_requires_durability_replay(metadata)
    ):
        return _unresolved_failure_response(
            'office job audit persistence failed',
            persistence,
            metadata=metadata,
        )
    detail = OfficeJobDirectMutationPartialFailureDetail(error=error, outcome=outcome)
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=detail.model_dump(mode='json', exclude_none=True),
    )


def _owner_deletion_partial_failure(
    store: OfficeJobStore,
    db: Session,
    *,
    pending_result_id: str,
    job_id: str,
    provenance: dict[str, Any],
    intent: dict[str, Any],
    exc: OfficeJobOwnerDeletionError,
) -> HTTPException:
    outcome = OfficeJobOwnerDeletionOutcomeResponse(**exc.outcome)
    metadata = {
        'error': 'office job deletion partially failed',
        'intent': intent,
        'outcome': dict(exc.outcome),
    }
    persistence = _commit_pending_result_audit(
        store,
        db,
        pending_result_id=pending_result_id,
        action='office_jobs.owner_delete',
        target_type='office_job',
        target_id=job_id,
        provenance=provenance,
        metadata=metadata,
        audit_status='partial_failure',
    )
    if persistence is not None and not (
        persistence.state == 'audit_persisted'
        and _metadata_requires_durability_replay(metadata)
    ):
        return _unresolved_failure_response(
            'office job audit persistence failed',
            persistence,
            metadata=metadata,
        )
    detail = OfficeJobOwnerDeletionPartialFailureDetail(
        error='office job deletion partially failed',
        outcome=outcome,
    )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=detail.model_dump(mode='json', exclude_none=True),
    )


def _stream_artifact(lease: OfficeJobArtifactReadLease) -> Iterator[bytes]:
    """Release the read lease even when streaming disconnects or fails."""
    try:
        while chunk := lease.handle.read(64 * 1024):
            yield chunk
    finally:
        lease.close()


@router.get('', response_model=OfficeJobListResponse)
def list_jobs(
    store: OfficeJobStore = Depends(get_office_job_store),
    user: User = Depends(get_current_user),
) -> OfficeJobListResponse:
    try:
        owner_id = strict_owner_id(user.id)
        records = store.list_for_owner(owner_id)
        usage = _usage_response(store, owner_id)
    except OfficeJobCorruptionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='invalid job owner') from exc
    jobs: list[OfficeJobListItemResponse] = []
    for record in records:
        title, llm_used = _completed_display_metadata(record)
        jobs.append(
            OfficeJobListItemResponse(
                job_id=record['job_id'],
                service=record['service'],
                status=record['status'],
                created_at=record['created_at'],
                updated_at=record['updated_at'],
                warnings=record['warnings'],
                artifacts=record['artifacts'],
                title=title,
                llm_used=llm_used,
            )
        )
    return OfficeJobListResponse(jobs=jobs, usage=usage)


@router.get(
    '/owner-identities',
    response_model=OfficeJobOwnerIdentityInventoryResponse,
    dependencies=[Depends(require_permission('admin.office.manage'))],
)
def list_owner_identities(
    store: OfficeJobStore = Depends(get_office_job_store),
) -> OfficeJobOwnerIdentityInventoryResponse:
    return OfficeJobOwnerIdentityInventoryResponse(**store.list_owner_identities())


@router.get(
    '/recovery',
    response_model=OfficeJobRecoveryInventoryResponse,
    dependencies=[Depends(require_permission('admin.office.manage'))],
)
def list_recovery(
    store: OfficeJobStore = Depends(get_office_job_store),
) -> OfficeJobRecoveryInventoryResponse:
    return OfficeJobRecoveryInventoryResponse(**store.list_recovery())


@router.delete(
    '/recovery/{recovery_id}',
    response_model=OfficeJobRecoveryActionResponse,
    responses=_DIRECT_MUTATION_FAILURE_RESPONSE,
    dependencies=[Depends(require_permission('admin.office.manage')), Depends(require_csrf)],
)
def delete_recovery(
    recovery_id: str,
    request: Request,
    db: Session = Depends(get_db),
    store: OfficeJobStore = Depends(get_office_job_store),
    actor: User = Depends(get_current_user),
) -> OfficeJobRecoveryActionResponse:
    action = 'office_jobs.recovery.delete'
    target_type = 'office_job_recovery'
    try:
        _reconcile_pending_result_audits(store, db, actor=actor)
        item = next(entry for entry in store.list_recovery()['items'] if entry['recovery_id'] == recovery_id)
        item = {
            **item,
            '_replay_evidence': store.direct_mutation_replay_evidence(
                'recovery_delete',
                recovery_id,
            ),
        }
    except OfficeJobAuditPersistenceError as exc:
        raise _audit_persistence_failure_response(exc) from exc
    except StopIteration as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='recovery entry not found') from exc
    pending_result_id, original_provenance = _prepare_pending_result(
        store,
        actor=actor,
        request=request,
        action=action,
        target_type=target_type,
        target_id=recovery_id,
        intent=item,
    )
    persistence = _persist_pending_intent_audit(
        db,
        pending_result_id=pending_result_id,
        action=action,
        target_type=target_type,
        target_id=recovery_id,
        provenance=original_provenance,
        intent=item,
    )
    if persistence is not None:
        raise _unresolved_failure_response(
            'office job intent audit persistence failed',
            persistence,
            metadata={'intent': item},
        )
    provenance = _begin_pending_result_mutation(
        store,
        pending_result_id=pending_result_id,
        action=action,
        target_type=target_type,
        target_id=recovery_id,
        fallback_provenance=original_provenance,
    )
    try:
        outcome = store.delete_recovery_outcome(recovery_id)
    except OfficeJobDirectMutationError as exc:
        raise _direct_mutation_partial_failure(
            store, db, pending_result_id=pending_result_id, action=action, target_type=target_type,
            target_id=recovery_id, provenance=provenance, intent=item, exc=exc,
            error='recovery evidence discard partially failed',
        ) from exc
    except FileNotFoundError as exc:
        _direct_known_error(
            store,
            db,
            pending_result_id=pending_result_id,
            action=action,
            target_type=target_type,
            target_id=recovery_id,
            provenance=provenance,
            intent=item,
            result='not_found',
            error='recovery entry not found',
            status_code=status.HTTP_404_NOT_FOUND,
            detail='recovery entry not found',
            cause=exc,
        )
    except OfficeJobCorruptionError as exc:
        _direct_known_error(
            store,
            db,
            pending_result_id=pending_result_id,
            action=action,
            target_type=target_type,
            target_id=recovery_id,
            provenance=provenance,
            intent=item,
            result='corrupt',
            error='recovery entry is corrupt',
            status_code=status.HTTP_409_CONFLICT,
            detail='recovery entry is corrupt',
            cause=exc,
        )
    except Exception as exc:
        raise _unresolved_after_mutation_started(
            pending_result_id,
            'recovery evidence discard outcome is unresolved',
        ) from exc
    response = OfficeJobRecoveryActionResponse(item=item, outcome=outcome)
    metadata = response.model_dump(mode='json')
    metadata['outcome'] = dict(outcome)
    persistence = _commit_pending_result_audit(
        store, db, pending_result_id=pending_result_id, action=action, target_type=target_type,
        target_id=recovery_id, provenance=provenance, metadata=metadata, audit_status='success',
    )
    if persistence is not None:
        raise _unresolved_failure_response(
            'office job audit persistence failed',
            persistence,
            metadata=metadata,
        )
    return response


@router.get(
    '/storage',
    response_model=OfficeJobStorageAccountingResponse,
    dependencies=[Depends(require_permission('admin.office.manage'))],
)
def get_storage_accounting(
    store: OfficeJobStore = Depends(get_office_job_store),
) -> OfficeJobStorageAccountingResponse:
    return OfficeJobStorageAccountingResponse(**store.storage_accounting())


@router.get(
    '/quarantine',
    response_model=OfficeJobQuarantineInventoryResponse,
    dependencies=[Depends(require_permission('admin.office.manage'))],
)
def list_quarantine(
    store: OfficeJobStore = Depends(get_office_job_store),
) -> OfficeJobQuarantineInventoryResponse:
    return OfficeJobQuarantineInventoryResponse(**store.list_quarantine())


def _get_quarantine_item(store: OfficeJobStore, quarantine_id: str) -> dict[str, Any]:
    try:
        return next(entry for entry in store.list_quarantine()['items'] if entry['quarantine_id'] == quarantine_id)
    except StopIteration as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='quarantine entry not found') from exc


def _direct_known_error(
    store: OfficeJobStore,
    db: Session,
    *,
    pending_result_id: str,
    action: str,
    target_type: str,
    target_id: str,
    provenance: dict[str, Any],
    intent: dict[str, Any],
    result: str,
    error: str,
    status_code: int,
    detail: str,
    cause: Exception | None,
) -> None:
    persistence, metadata = _known_nonmutation_failure(
        store, db, pending_result_id=pending_result_id, action=action, target_type=target_type,
        target_id=target_id, provenance=provenance, intent=intent, result=result, error=error,
    )
    if persistence is not None:
        failure = _unresolved_failure_response(
            'office job audit persistence failed',
            persistence,
            metadata=metadata,
        )
        if cause is not None:
            raise failure from cause
        raise failure
    known_failure = HTTPException(status_code=status_code, detail=detail)
    if cause is not None:
        raise known_failure from cause
    raise known_failure


@router.post(
    '/quarantine/{quarantine_id}/restore',
    response_model=OfficeJobQuarantineActionResponse,
    responses=_DIRECT_MUTATION_FAILURE_RESPONSE,
    dependencies=[Depends(require_permission('admin.office.manage')), Depends(require_csrf)],
)
def restore_quarantine(
    quarantine_id: str,
    request: Request,
    db: Session = Depends(get_db),
    store: OfficeJobStore = Depends(get_office_job_store),
    actor: User = Depends(get_current_user),
) -> OfficeJobQuarantineActionResponse:
    action = 'office_jobs.quarantine.restore'
    target_type = 'office_job_quarantine'
    try:
        _reconcile_pending_result_audits(store, db, actor=actor)
        item = _get_quarantine_item(store, quarantine_id)
        item = {
            **item,
            '_replay_evidence': store.direct_mutation_replay_evidence(
                'quarantine_restore',
                quarantine_id,
            ),
        }
    except OfficeJobAuditPersistenceError as exc:
        raise _audit_persistence_failure_response(exc) from exc
    pending_result_id, original_provenance = _prepare_pending_result(
        store, actor=actor, request=request, action=action, target_type=target_type,
        target_id=quarantine_id, intent=item,
    )
    persistence = _persist_pending_intent_audit(
        db,
        pending_result_id=pending_result_id,
        action=action,
        target_type=target_type,
        target_id=quarantine_id,
        provenance=original_provenance,
        intent=item,
    )
    if persistence is not None:
        raise _unresolved_failure_response(
            'office job intent audit persistence failed',
            persistence,
            metadata={'intent': item},
        )
    provenance = _begin_pending_result_mutation(
        store, pending_result_id=pending_result_id, action=action, target_type=target_type,
        target_id=quarantine_id, fallback_provenance=original_provenance,
    )
    try:
        outcome = store.restore_quarantine_outcome(quarantine_id)
    except OfficeJobDirectMutationError as exc:
        raise _direct_mutation_partial_failure(
            store, db, pending_result_id=pending_result_id, action=action, target_type=target_type,
            target_id=quarantine_id, provenance=provenance, intent=item, exc=exc,
            error='quarantine restoration partially failed',
        ) from exc
    except FileNotFoundError as exc:
        _direct_known_error(store, db, pending_result_id=pending_result_id, action=action,
                            target_type=target_type, target_id=quarantine_id, provenance=provenance,
                            intent=item, result='not_found', error='quarantine entry not found',
                            status_code=status.HTTP_404_NOT_FOUND, detail='quarantine entry not found', cause=exc)
    except FileExistsError as exc:
        _direct_known_error(store, db, pending_result_id=pending_result_id, action=action,
                            target_type=target_type, target_id=quarantine_id, provenance=provenance,
                            intent=item, result='conflict', error='job already exists',
                            status_code=status.HTTP_409_CONFLICT, detail='job already exists', cause=exc)
    except OfficeJobCorruptionError as exc:
        _direct_known_error(store, db, pending_result_id=pending_result_id, action=action,
                            target_type=target_type, target_id=quarantine_id, provenance=provenance,
                            intent=item, result='corrupt', error='quarantine entry is corrupt',
                            status_code=status.HTTP_409_CONFLICT, detail=str(exc), cause=exc)
    except OfficeJobCapacityError as exc:
        _direct_known_error(store, db, pending_result_id=pending_result_id, action=action,
                            target_type=target_type, target_id=quarantine_id, provenance=provenance,
                            intent=item, result='capacity_rejected', error=str(exc),
                            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc), cause=exc)
    except Exception as exc:
        raise _unresolved_after_mutation_started(
            pending_result_id,
            'quarantine restoration outcome is unresolved',
        ) from exc
    response = OfficeJobQuarantineActionResponse(item=item, outcome=outcome)
    metadata = response.model_dump(mode='json')
    metadata['outcome'] = dict(outcome)
    persistence = _commit_pending_result_audit(
        store, db, pending_result_id=pending_result_id, action=action, target_type=target_type,
        target_id=quarantine_id, provenance=provenance, metadata=metadata, audit_status='success',
    )
    if persistence is not None:
        raise _unresolved_failure_response(
            'office job audit persistence failed',
            persistence,
            metadata=metadata,
        )
    return response


@router.delete(
    '/quarantine/{quarantine_id}',
    response_model=OfficeJobQuarantineActionResponse,
    responses=_DIRECT_MUTATION_FAILURE_RESPONSE,
    dependencies=[Depends(require_permission('admin.office.manage')), Depends(require_csrf)],
)
def delete_quarantine(
    quarantine_id: str,
    request: Request,
    db: Session = Depends(get_db),
    store: OfficeJobStore = Depends(get_office_job_store),
    actor: User = Depends(get_current_user),
) -> OfficeJobQuarantineActionResponse:
    action = 'office_jobs.quarantine.delete'
    target_type = 'office_job_quarantine'
    try:
        _reconcile_pending_result_audits(store, db, actor=actor)
        item = _get_quarantine_item(store, quarantine_id)
        item = {
            **item,
            '_replay_evidence': store.direct_mutation_replay_evidence(
                'quarantine_delete',
                quarantine_id,
            ),
        }
    except OfficeJobAuditPersistenceError as exc:
        raise _audit_persistence_failure_response(exc) from exc
    pending_result_id, original_provenance = _prepare_pending_result(
        store, actor=actor, request=request, action=action, target_type=target_type,
        target_id=quarantine_id, intent=item,
    )
    persistence = _persist_pending_intent_audit(
        db,
        pending_result_id=pending_result_id,
        action=action,
        target_type=target_type,
        target_id=quarantine_id,
        provenance=original_provenance,
        intent=item,
    )
    if persistence is not None:
        raise _unresolved_failure_response(
            'office job intent audit persistence failed',
            persistence,
            metadata={'intent': item},
        )
    provenance = _begin_pending_result_mutation(
        store, pending_result_id=pending_result_id, action=action, target_type=target_type,
        target_id=quarantine_id, fallback_provenance=original_provenance,
    )
    try:
        outcome = store.delete_quarantine_outcome(quarantine_id)
    except OfficeJobDirectMutationError as exc:
        raise _direct_mutation_partial_failure(
            store, db, pending_result_id=pending_result_id, action=action, target_type=target_type,
            target_id=quarantine_id, provenance=provenance, intent=item, exc=exc,
            error='quarantine deletion partially failed',
        ) from exc
    except FileNotFoundError as exc:
        _direct_known_error(store, db, pending_result_id=pending_result_id, action=action,
                            target_type=target_type, target_id=quarantine_id, provenance=provenance,
                            intent=item, result='not_found', error='quarantine entry not found',
                            status_code=status.HTTP_404_NOT_FOUND, detail='quarantine entry not found', cause=exc)
    except OfficeJobCorruptionError as exc:
        _direct_known_error(store, db, pending_result_id=pending_result_id, action=action,
                            target_type=target_type, target_id=quarantine_id, provenance=provenance,
                            intent=item, result='corrupt', error='quarantine entry is corrupt',
                            status_code=status.HTTP_409_CONFLICT, detail='quarantine entry is corrupt', cause=exc)
    except OfficeJobCapacityError as exc:
        _direct_known_error(store, db, pending_result_id=pending_result_id, action=action,
                            target_type=target_type, target_id=quarantine_id, provenance=provenance,
                            intent=item, result='capacity_rejected', error=str(exc),
                            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc), cause=exc)
    except Exception as exc:
        raise _unresolved_after_mutation_started(
            pending_result_id,
            'quarantine deletion outcome is unresolved',
        ) from exc
    response = OfficeJobQuarantineActionResponse(item=item, outcome=outcome)
    metadata = response.model_dump(mode='json')
    metadata['outcome'] = dict(outcome)
    persistence = _commit_pending_result_audit(
        store, db, pending_result_id=pending_result_id, action=action, target_type=target_type,
        target_id=quarantine_id, provenance=provenance, metadata=metadata, audit_status='success',
    )
    if persistence is not None:
        raise _unresolved_failure_response(
            'office job audit persistence failed',
            persistence,
            metadata=metadata,
        )
    return response


@router.delete(
    '/evidence/{management_token}',
    response_model=OfficeJobEvidenceDispositionResponse,
    responses=_DIRECT_MUTATION_FAILURE_RESPONSE,
    dependencies=[Depends(require_permission('admin.office.manage')), Depends(require_csrf)],
)
def dispose_corrupt_evidence(
    management_token: str,
    request: Request,
    db: Session = Depends(get_db),
    store: OfficeJobStore = Depends(get_office_job_store),
    actor: User = Depends(get_current_user),
) -> OfficeJobEvidenceDispositionResponse:
    if re.fullmatch(r'[0-9a-f]{32}', management_token) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='corrupt evidence token not found')
    action = 'office_jobs.evidence.dispose'
    target_type = 'office_job_corrupt_evidence'
    intent: dict[str, Any] = {'management_token': management_token}
    try:
        _reconcile_pending_result_audits(store, db, actor=actor)
        intent['_replay_evidence'] = store.corrupt_evidence_replay_evidence(management_token)
    except OfficeJobAuditPersistenceError as exc:
        raise _audit_persistence_failure_response(exc) from exc
    pending_result_id, original_provenance = _prepare_pending_result(
        store, actor=actor, request=request, action=action, target_type=target_type,
        target_id=management_token, intent=intent,
    )
    persistence = _persist_pending_intent_audit(
        db,
        pending_result_id=pending_result_id,
        action=action,
        target_type=target_type,
        target_id=management_token,
        provenance=original_provenance,
        intent=intent,
    )
    if persistence is not None:
        raise _unresolved_failure_response(
            'office job intent audit persistence failed',
            persistence,
            metadata={'intent': intent},
        )
    provenance = _begin_pending_result_mutation(
        store, pending_result_id=pending_result_id, action=action, target_type=target_type,
        target_id=management_token, fallback_provenance=original_provenance,
    )
    try:
        outcome = store.dispose_corrupt_evidence_outcome(management_token)
    except OfficeJobDirectMutationError as exc:
        raise _direct_mutation_partial_failure(
            store, db, pending_result_id=pending_result_id, action=action, target_type=target_type,
            target_id=management_token, provenance=provenance, intent=intent, exc=exc,
            error='corrupt evidence disposition partially failed',
        ) from exc
    except FileNotFoundError as exc:
        _direct_known_error(store, db, pending_result_id=pending_result_id, action=action,
                            target_type=target_type, target_id=management_token, provenance=provenance,
                            intent=intent, result='not_found', error='corrupt evidence token is unavailable',
                            status_code=status.HTTP_404_NOT_FOUND, detail='corrupt evidence token not found', cause=exc)
    except OfficeJobCorruptionError as exc:
        _direct_known_error(store, db, pending_result_id=pending_result_id, action=action,
                            target_type=target_type, target_id=management_token, provenance=provenance,
                            intent=intent, result='invalid_token',
                            error='corrupt evidence token no longer identifies managed evidence',
                            status_code=status.HTTP_409_CONFLICT,
                            detail='corrupt evidence token is no longer valid', cause=exc)
    except Exception as exc:
        raise _unresolved_after_mutation_started(
            pending_result_id,
            'corrupt evidence disposition outcome is unresolved',
        ) from exc
    response = OfficeJobEvidenceDispositionResponse(outcome=outcome)
    metadata = response.model_dump(mode='json')
    metadata['outcome'] = dict(outcome)
    persistence = _commit_pending_result_audit(
        store, db, pending_result_id=pending_result_id, action=action, target_type=target_type,
        target_id=management_token, provenance=provenance, metadata=metadata, audit_status='success',
    )
    if persistence is not None:
        raise _unresolved_failure_response(
            'office job audit persistence failed',
            persistence,
            metadata=metadata,
        )
    return response


@router.post(
    '/admin/purge',
    response_model=OfficeJobPurgeResponse,
    responses=_PURGE_FAILURE_RESPONSE,
    dependencies=[Depends(require_permission('admin.office.manage')), Depends(require_csrf)],
)
def purge_expired_jobs(
    request: Request,
    db: Session = Depends(get_db),
    store: OfficeJobStore = Depends(get_office_job_store),
    actor: User = Depends(get_current_user),
) -> OfficeJobPurgeResponse:
    action = 'office_jobs.purge_expired'
    target_type = 'office_job'
    target_id = 'retention'
    try:
        _reconcile_pending_result_audits(store, db, actor=actor)
    except OfficeJobAuditPersistenceError as exc:
        raise _audit_persistence_failure_response(exc) from exc
    intent = {'retention_days': store.retention_days}
    pending_result_id, original_provenance = _prepare_pending_result(
        store, actor=actor, request=request, action=action, target_type=target_type,
        target_id=target_id, intent=intent,
    )
    persistence = _persist_pending_intent_audit(
        db,
        pending_result_id=pending_result_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        provenance=original_provenance,
        intent=intent,
    )
    if persistence is not None:
        raise _unresolved_failure_response(
            'office job intent audit persistence failed',
            persistence,
            metadata={'intent': intent},
        )
    provenance = _begin_pending_result_mutation(
        store, pending_result_id=pending_result_id, action=action, target_type=target_type,
        target_id=target_id, fallback_provenance=original_provenance,
    )
    try:
        result = store.purge_expired()
    except OfficeJobPurgeError as exc:
        replay_evidence = exc.partial_result.get('_replay_evidence')
        partial_result = OfficeJobPurgeResponse(**exc.partial_result)
        metadata = {
            'error': 'office job purge partially failed',
            'intent': intent,
            'partial_result': partial_result.model_dump(mode='json'),
            '_replay_evidence': replay_evidence,
        }
        persistence = _commit_pending_result_audit(
            store, db, pending_result_id=pending_result_id, action=action, target_type=target_type,
            target_id=target_id, provenance=provenance, metadata=metadata, audit_status='partial_failure',
        )
        if persistence is not None and not (
            persistence.state == 'audit_persisted'
            and _metadata_requires_durability_replay(metadata)
        ):
            raise _unresolved_failure_response(
                'office job audit persistence failed',
                persistence,
                metadata=metadata,
            ) from exc
        detail = OfficeJobPurgePartialFailureDetail(
            error='office job purge partially failed',
            partial_result=partial_result,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail.model_dump(mode='json', exclude_none=True),
        ) from exc
    except Exception as exc:
        raise _unresolved_after_mutation_started(
            pending_result_id,
            'office job purge outcome is unresolved',
        ) from exc
    response = OfficeJobPurgeResponse(**result)
    metadata = response.model_dump(mode='json')
    persistence = _commit_pending_result_audit(
        store, db, pending_result_id=pending_result_id, action=action, target_type=target_type,
        target_id=target_id, provenance=provenance, metadata=metadata, audit_status='success',
    )
    if persistence is not None:
        raise _unresolved_failure_response(
            'office job audit persistence failed',
            persistence,
            metadata=metadata,
        )
    return response

@router.get(
    '/admin/pending-receipts',
    response_model=OfficeJobPendingReceiptInventoryResponse,
    dependencies=[Depends(require_permission('admin.office.manage'))],
)
def list_pending_receipts(
    store: OfficeJobStore = Depends(get_office_job_store),
) -> OfficeJobPendingReceiptInventoryResponse:
    return OfficeJobPendingReceiptInventoryResponse(**store.list_pending_receipt_inventory())


@router.post(
    '/admin/pending-receipts/{pending_result_id}/replay',
    response_model=OfficeJobPendingReceiptReplayResponse,
    dependencies=[Depends(require_permission('admin.office.manage')), Depends(require_csrf)],
)
def replay_pending_receipt(
    pending_result_id: str,
    request: Request,
    db: Session = Depends(get_db),
    store: OfficeJobStore = Depends(get_office_job_store),
    actor: User = Depends(get_current_user),
) -> OfficeJobPendingReceiptReplayResponse:
    if re.fullmatch(r'[0-9a-f]{32}', pending_result_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='pending receipt not found')
    _record_pending_receipt_replay_audit(
        db,
        actor=actor,
        request=request,
        pending_result_id=pending_result_id,
        audit_status='intent',
        result='requested',
    )
    try:
        _reconcile_pending_result_audit(
            store,
            db,
            pending_result_id=pending_result_id,
        )
    except FileNotFoundError as exc:
        _record_pending_receipt_replay_audit(
            db,
            actor=actor,
            request=request,
            pending_result_id=pending_result_id,
            audit_status='failure',
            result='not_found',
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='pending receipt not found',
        ) from exc
    except (OfficeJobCorruptionError, OfficeJobAuditPersistenceError, ValueError) as exc:
        _record_pending_receipt_replay_audit(
            db,
            actor=actor,
            request=request,
            pending_result_id=pending_result_id,
            audit_status='failure',
            result='unresolved',
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='pending receipt cannot be safely replayed',
        ) from exc
    except Exception as exc:
        _record_pending_receipt_replay_audit(
            db,
            actor=actor,
            request=request,
            pending_result_id=pending_result_id,
            audit_status='failure',
            result='failed',
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='pending receipt replay failed',
        ) from exc
    _record_pending_receipt_replay_audit(
        db,
        actor=actor,
        request=request,
        pending_result_id=pending_result_id,
        audit_status='success',
        result='replayed',
    )
    return OfficeJobPendingReceiptReplayResponse(
        pending_result_id=pending_result_id,
        replayed=True,
    )


@router.get('/{job_id}', response_model=OfficeJobDetailResponse)
def get_job(
    job_id: str,
    store: OfficeJobStore = Depends(get_office_job_store),
    user: User = Depends(get_current_user),
) -> OfficeJobDetailResponse:
    return OfficeJobDetailResponse(**_load_owned_job(store, job_id, user))


@router.delete(
    '/{job_id}',
    response_model=OfficeJobOwnerDeletionResponse,
    responses=_OWNER_DELETION_FAILURE_RESPONSE,
    dependencies=[Depends(require_permission('office.use')), Depends(require_csrf)],
)
def delete_job(
    job_id: str,
    request: Request,
    db: Session = Depends(get_db),
    store: OfficeJobStore = Depends(get_office_job_store),
    user: User = Depends(get_current_user),
) -> OfficeJobOwnerDeletionResponse:
    action = 'office_jobs.owner_delete'
    owner_id: int
    try:
        owner_id = strict_owner_id(user.id)
        _reconcile_pending_result_audits(store, db, actor=user)
        intent = store.owner_deletion_intent(job_id, owner_id)
    except OfficeJobAuditPersistenceError as exc:
        raise _audit_persistence_failure_response(exc) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='job not found') from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='job belongs to another user') from exc
    except OfficeJobCorruptionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='invalid job owner') from exc
    pending_result_id, original_provenance = _prepare_pending_result(
        store, actor=user, request=request, action=action, target_type='office_job',
        target_id=job_id, intent=intent,
    )
    persistence = _persist_pending_intent_audit(
        db,
        pending_result_id=pending_result_id,
        action=action,
        target_type='office_job',
        target_id=job_id,
        provenance=original_provenance,
        intent=intent,
    )
    if persistence is not None:
        raise _unresolved_failure_response(
            'office job intent audit persistence failed',
            persistence,
            metadata={'intent': intent},
        )
    provenance = _begin_pending_result_mutation(
        store, pending_result_id=pending_result_id, action=action, target_type='office_job',
        target_id=job_id, fallback_provenance=original_provenance,
    )
    try:
        outcome = store.delete_for_owner_outcome(job_id, owner_id)
    except OfficeJobOwnerDeletionError as exc:
        raise _owner_deletion_partial_failure(
            store, db, pending_result_id=pending_result_id, job_id=job_id,
            provenance=provenance, intent=intent, exc=exc,
        ) from exc
    except FileNotFoundError as exc:
        _direct_known_error(
            store,
            db,
            pending_result_id=pending_result_id,
            action=action,
            target_type='office_job',
            target_id=job_id,
            provenance=provenance,
            intent=intent,
            result='not_found',
            error='job became unavailable before deletion',
            status_code=status.HTTP_404_NOT_FOUND,
            detail='job not found',
            cause=exc,
        )
    except OfficeJobCorruptionError as exc:
        _direct_known_error(
            store,
            db,
            pending_result_id=pending_result_id,
            action=action,
            target_type='office_job',
            target_id=job_id,
            provenance=provenance,
            intent=intent,
            result='corrupt',
            error=str(exc),
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
            cause=exc,
        )
    except Exception as exc:
        raise _unresolved_after_mutation_started(
            pending_result_id,
            'office job deletion outcome is unresolved',
        ) from exc
    if outcome is None:
        _direct_known_error(
            store,
            db,
            pending_result_id=pending_result_id,
            action=action,
            target_type='office_job',
            target_id=job_id,
            provenance=provenance,
            intent=intent,
            result='ownership_changed',
            error='job ownership changed before deletion',
            status_code=status.HTTP_404_NOT_FOUND,
            detail='job not found',
            cause=None,
        )
    response = OfficeJobOwnerDeletionResponse(outcome=outcome)
    metadata = response.model_dump(mode='json')
    persistence = _commit_pending_result_audit(
        store, db, pending_result_id=pending_result_id, action=action, target_type='office_job',
        target_id=job_id, provenance=provenance, metadata=metadata, audit_status='success',
    )
    if persistence is not None:
        raise _unresolved_failure_response(
            'office job audit persistence failed',
            persistence,
            metadata=metadata,
        )
    return response


@router.get('/{job_id}/artifacts/{filename}')
def get_artifact(
    job_id: str,
    filename: str,
    store: OfficeJobStore = Depends(get_office_job_store),
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    try:
        lease = store.open_artifact_read_lease(job_id, filename, strict_owner_id(user.id))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='artifact not found') from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='job belongs to another user') from exc
    except OfficeJobCorruptionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='invalid job owner') from exc
    return StreamingResponse(
        _stream_artifact(lease),
        media_type=lease.media_type,
        headers={
            'content-disposition': f"attachment; filename*=utf-8''{quote(lease.filename)}",
            'content-length': str(lease.size_bytes),
        },
        background=BackgroundTask(lease.close),
    )


def _bundle_not_materialized_failure(
    store: OfficeJobStore,
    db: Session,
    *,
    pending_result_id: str,
    action: str,
    target_type: str,
    target_id: str,
    provenance: dict[str, Any],
    intent: dict[str, Any],
    result: str,
    error: str,
    status_code: int,
    detail: str,
) -> HTTPException:
    metadata = _sanitized_receipt_metadata(
        {
            'intent': intent,
            'outcome': {
                'operation': action,
                'result': 'not_materialized',
                'materialization_result': result,
            },
            'error': error,
        }
    )
    persistence = _commit_pending_result_audit(
        store,
        db,
        pending_result_id=pending_result_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        provenance=provenance,
        metadata=metadata,
        audit_status='partial_failure',
    )
    if persistence is not None:
        return _unresolved_failure_response(
            'office job audit persistence failed',
            persistence,
            metadata=metadata,
        )
    return HTTPException(status_code=status_code, detail=detail)


def _cleanup_temporary_bundle(
    store: OfficeJobStore,
    pending_result_id: str,
    actor_id: int,
) -> None:
    """Replay the durable cleanup receipt; failures stay replayable on disk."""
    background_db = get_session_factory()()
    try:
        for pending in store.list_pending_results_for_actor(actor_id):
            if pending['pending_result_id'] != pending_result_id:
                continue
            _replay_temporary_bundle_cleanup(
                store,
                background_db,
                pending=pending,
                receipt_state=_receipt_state_from_record(pending),
                provenance=dict(pending['request_provenance']),
                metadata=dict(pending.get('audit_metadata', {})),
                action=str(pending['action']),
                target_type=str(pending['target_type']),
                target_id=str(pending['target_id']),
                intent=dict(pending['intent']),
            )
            return
    finally:
        background_db.close()


@router.get('/{job_id}/bundle', responses=_BUNDLE_CLEANUP_FAILURE_RESPONSE)
def get_bundle(
    job_id: str,
    request: Request,
    db: Session = Depends(get_db),
    store: OfficeJobStore = Depends(get_office_job_store),
    user: User = Depends(get_current_user),
) -> FileResponse:
    try:
        _reconcile_pending_result_audits(store, db, actor=user)
    except OfficeJobAuditPersistenceError as exc:
        raise _audit_persistence_failure_response(exc) from exc
    _load_owned_job(store, job_id, user)

    action = 'office_jobs.bundle.cleanup'
    target_type = 'office_job_bundle'
    bundle_id = uuid4().hex
    target_id = f'bundle-{bundle_id}.zip'
    intent = {'job_id': job_id, 'bundle_id': bundle_id, 'bundle_name': target_id}
    pending_result_id, original_provenance = _prepare_pending_result(
        store,
        actor=user,
        request=request,
        action=action,
        target_type=target_type,
        target_id=target_id,
        intent=intent,
    )
    persistence = _persist_pending_intent_audit(
        db,
        pending_result_id=pending_result_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        provenance=original_provenance,
        intent=intent,
    )
    if persistence is not None:
        raise _unresolved_failure_response(
            'office job intent audit persistence failed',
            persistence,
            metadata={'intent': intent},
        )

    provenance = _begin_pending_result_mutation(
        store,
        pending_result_id=pending_result_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        fallback_provenance=original_provenance,
    )
    try:
        path = store.create_temporary_bundle(job_id, bundle_id=bundle_id)
    except FileNotFoundError as exc:
        raise _bundle_not_materialized_failure(
            store,
            db,
            pending_result_id=pending_result_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            provenance=provenance,
            intent=intent,
            result='not_found',
            error='job became unavailable before bundle materialization',
            status_code=status.HTTP_404_NOT_FOUND,
            detail='job not found',
        ) from exc
    except OfficeJobCorruptionError as exc:
        raise _bundle_not_materialized_failure(
            store,
            db,
            pending_result_id=pending_result_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            provenance=provenance,
            intent=intent,
            result='corrupt',
            error=str(exc),
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except OfficeJobCapacityError as exc:
        raise _bundle_not_materialized_failure(
            store,
            db,
            pending_result_id=pending_result_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            provenance=provenance,
            intent=intent,
            result='capacity_rejected',
            error=str(exc),
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise _unresolved_after_mutation_started(
            pending_result_id,
            'temporary bundle materialization outcome is unresolved',
        ) from exc

    try:
        intent, _ = _bind_temporary_bundle_cleanup_evidence(
            store,
            pending_result_id=pending_result_id,
            bundle_id=bundle_id,
            intent=intent,
        )
    except Exception as exc:
        raise _unresolved_after_mutation_started(
            pending_result_id,
            'temporary bundle cleanup evidence could not be persisted',
        ) from exc
    return FileResponse(
        path,
        filename=f'aeroone_{job_id}.zip',
        media_type='application/zip',
        background=BackgroundTask(
            _cleanup_temporary_bundle,
            store,
            pending_result_id,
            strict_owner_id(user.id),
        ),
    )