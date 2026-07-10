from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
import hashlib
import json

from app.modules.auth.models import User
from app.operations.credential_rotation_contracts import CredentialBundle


def _digest_json(value: tuple[tuple[str, str | int | bool | None], ...]) -> str:
    payload = json.dumps(value, ensure_ascii=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def material_fingerprint(bundle: CredentialBundle) -> str:
    material = (
        ("admin_username", bundle.admin_username),
        ("jwt_secret_key", bundle.jwt_secret_key),
        (
            "users",
            json.dumps(
                sorted((credential.username, credential.password) for credential in bundle.users),
                separators=(",", ":"),
            ),
        ),
    )
    return _digest_json(material)


def user_set_fingerprint(users: Sequence[User]) -> str:
    identity = tuple((str(user.id), user.username, user.role, user.is_active) for user in users)
    return hashlib.sha256(
        json.dumps(identity, ensure_ascii=True, separators=(",", ":")).encode()
    ).hexdigest()


def _canonical_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    aware = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return aware.astimezone(UTC).isoformat()


def state_fingerprint(users: Sequence[User], session_count: int) -> str:
    state = tuple(
        (
            str(user.id),
            user.username,
            user.role,
            user.is_active,
            user.session_version,
            user.password_hash,
            _canonical_datetime(user.password_changed_at),
        )
        for user in users
    )
    return hashlib.sha256(
        json.dumps((state, session_count), ensure_ascii=True, separators=(",", ":")).encode()
    ).hexdigest()
