from __future__ import annotations

from dataclasses import dataclass
import json

from sqlalchemy.orm import Session

from app.modules.admin.models import AdminAuditEvent
from app.modules.auth.models import User
from app.operations.credential_rotation_contracts import RotationRequest, RotationResult
from app.operations.credential_rotation_fingerprints import user_set_fingerprint
from app.operations.credential_rotation_models import CredentialRotationLedger


@dataclass(frozen=True, slots=True)
class RotationRecord:
    request: RotationRequest
    result: RotationResult
    material_fingerprint: str
    pre_state_fingerprint: str
    post_state_fingerprint: str
    users: tuple[User, ...]


def record_rotation(session: Session, record: RotationRecord) -> None:
    request = record.request
    result = record.result
    session.add(
        CredentialRotationLedger(
            rotation_id=str(request.bundle.rotation_id),
            database_id=str(request.bundle.database_id),
            material_fingerprint=record.material_fingerprint,
            user_set_fingerprint=user_set_fingerprint(record.users),
            pre_state_fingerprint=record.pre_state_fingerprint,
            post_state_fingerprint=record.post_state_fingerprint,
            user_count_before=result.user_count_before,
            user_count_after=result.user_count_after,
            password_count_changed=result.password_count_changed,
            session_count_before=result.session_count_before,
            session_count_after=result.session_count_after,
        )
    )
    session.add(
        AdminAuditEvent(
            action="security.credential_rotation",
            target_type="system",
            target_id=str(request.bundle.rotation_id),
            status="success",
            metadata_json=json.dumps(
                {
                    "user_count_before": result.user_count_before,
                    "user_count_after": result.user_count_after,
                    "password_count_changed": result.password_count_changed,
                    "session_count_before": result.session_count_before,
                    "session_count_after": result.session_count_after,
                },
                separators=(",", ":"),
            ),
        )
    )
