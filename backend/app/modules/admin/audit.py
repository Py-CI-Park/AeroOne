from __future__ import annotations

import json
from typing import Any
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from fastapi import Request
from sqlalchemy.orm import Session

from app.modules.admin.models import AdminAuditEvent
from app.modules.auth.models import User

_SECRET_KEYS = {'password', 'password_hash', 'token', 'jwt', 'csrf', 'secret', 'api_key', 'prompt', 'answer', 'content', 'snippet', 'citation'}


def redact_audit_metadata(value: Any) -> Any:
    """Recursively remove sensitive values before audit or durable receipt storage."""
    if isinstance(value, dict):
        clean: dict[str, Any] = {}
        for key, item in value.items():
            lower = key.lower()
            if any(secret in lower for secret in _SECRET_KEYS):
                clean[key] = '[REDACTED]'
            else:
                clean[key] = redact_audit_metadata(item)
        return clean
    if isinstance(value, list):
        return [redact_audit_metadata(item) for item in value]
    return value


def _dumps(value: Any | None) -> str | None:
    if value is None:
        return None
    return json.dumps(redact_audit_metadata(value), ensure_ascii=False, sort_keys=True, default=str)


def _provenance_value(
    provenance: dict[str, Any] | None,
    key: str,
    fallback: Any,
) -> Any:
    if provenance is None:
        return fallback
    return provenance.get(key, fallback)


def _audit_actor_id(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else None


def _persisted_audit_actor_id(db: Session, value: Any) -> int | None:
    """Avoid a stale receipt actor turning an otherwise replayable audit into an FK failure."""
    actor_id = _audit_actor_id(value)
    if actor_id is None:
        return None
    return db.scalar(select(User.id).where(User.id == actor_id))


def record_admin_audit(
    db: Session,
    *,
    actor: User | None,
    action: str,
    target_type: str,
    target_id: str | int | None = None,
    request: Request | None = None,
    before: Any | None = None,
    after: Any | None = None,
    metadata: Any | None = None,
    status: str = 'success',
    provenance: dict[str, Any] | None = None,
    idempotency_key: str | None = None,
) -> AdminAuditEvent:
    """Append an audit event, returning the original event for idempotent replays."""
    if idempotency_key is not None:
        existing = db.execute(
            select(AdminAuditEvent).where(AdminAuditEvent.idempotency_key == idempotency_key)
        ).scalar_one_or_none()
        if existing is not None:
            return existing

    requested_actor_id = _audit_actor_id(
        _provenance_value(provenance, 'actor_id', actor.id if actor else None)
    )
    actor_id = _persisted_audit_actor_id(db, requested_actor_id)
    audit_metadata = (
        {**metadata, 'original_actor_id': requested_actor_id}
        if requested_actor_id is not None and actor_id is None and isinstance(metadata, dict)
        else metadata
    )
    event = AdminAuditEvent(
        actor_user_id=actor_id,
        actor_username=_provenance_value(
            provenance,
            'actor_username',
            actor.username if actor else None,
        ),
        actor_role=_provenance_value(provenance, 'actor_role', actor.role if actor else None),
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        method=_provenance_value(provenance, 'method', request.method if request else None),
        path=_provenance_value(
            provenance,
            'path',
            str(request.url.path) if request else None,
        ),
        status=status,
        ip_address=_provenance_value(
            provenance,
            'ip_address',
            request.client.host if request and request.client else None,
        ),
        user_agent=_provenance_value(
            provenance,
            'user_agent',
            request.headers.get('user-agent') if request else None,
        ),
        request_id=_provenance_value(
            provenance,
            'request_id',
            request.headers.get('x-request-id') if request else None,
        ),
        idempotency_key=idempotency_key,
        before_json=_dumps(before),
        after_json=_dumps(after),
        metadata_json=_dumps(audit_metadata),
    )
    # 병합: idempotency_key 기반 저장 로직(our) + AI provider 감사 메타데이터 생성기(1.14.0) 모두 보존
    if idempotency_key is None:
        db.add(event)
        db.flush()
        return event

    try:
        with db.begin_nested():
            db.add(event)
            db.flush()
        return event
    except IntegrityError:
        existing = db.execute(
            select(AdminAuditEvent).where(AdminAuditEvent.idempotency_key == idempotency_key)
        ).scalar_one_or_none()
        if existing is None:
            raise
        return existing


def build_ai_provider_audit_metadata(
    *,
    operation: str,
    result: str,
    reason_code: str,
    kind: str | None = None,
    selected_kind: str | None = None,
    compatible_state: str | None = None,
    config_version: int | None = None,
) -> dict[str, object]:
    """AI-provider 감사 메타데이터 생성기.

    명시적 allowlist 필드만 담는다. DTO/예외 객체/원문 URL/키/업스트림 응답 바디/DPAPI
    credential_binding_version 은 어떤 경로로도 이 함수에 전달되거나 감사 로그에
    남아서는 안 된다. 호출부는 반드시 안전한 원시값(str/int)만 키워드 인자로 넘겨야 한다.
    """
    snapshot: dict[str, object] = {
        'operation': operation,
        'result': result,
        'reason_code': reason_code,
    }
    if kind is not None:
        snapshot['kind'] = kind
    if selected_kind is not None:
        snapshot['selected_kind'] = selected_kind
    if compatible_state is not None:
        snapshot['compatible_state'] = compatible_state
    if config_version is not None:
        snapshot['config_version'] = config_version
    return snapshot
