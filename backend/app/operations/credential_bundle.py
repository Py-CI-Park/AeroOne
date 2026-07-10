from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import secrets
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.modules.auth.models import User
from app.operations.credential_rotation import (
    CredentialBundle,
    CredentialRotationError,
    RotationErrorCode,
    UserCredential,
    ensure_database_identity,
    validate_active_admin,
)
from app.operations.windows_dpapi import (
    DpapiPurpose,
    protect_for_current_user,
    unprotect_for_current_user,
)


class BundlePreparationRequest(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, strict=True, extra="forbid")

    database_url: str = Field(repr=False, pattern=r"^sqlite:///")
    admin_username: str
    bundle_path: Path


@dataclass(frozen=True, slots=True)
class BundlePreparationResult:
    user_count: int


def inspect_credential_scope(database_url: str, admin_username: str) -> int:
    engine = create_engine(database_url)
    with Session(engine) as session:
        users = list(session.scalars(select(User).order_by(User.id)).all())
    if not users:
        raise CredentialRotationError(RotationErrorCode.EMPTY_USER_SET)
    validate_active_admin(users, admin_username)
    return len(users)


def prepare_credential_bundle(request: BundlePreparationRequest) -> BundlePreparationResult:
    engine = create_engine(request.database_url)
    with Session(engine) as session:
        users = list(session.scalars(select(User).order_by(User.id)).all())
    if not users:
        raise CredentialRotationError(RotationErrorCode.EMPTY_USER_SET)
    validate_active_admin(users, request.admin_username)
    bundle = CredentialBundle(
        database_id=ensure_database_identity(request.database_url),
        admin_username=request.admin_username,
        jwt_secret_key=secrets.token_hex(32),
        users=tuple(
            UserCredential(username=user.username, password=secrets.token_urlsafe(36))
            for user in users
        ),
    )
    protected = protect_for_current_user(
        bundle.model_dump_json().encode("utf-8"),
        DpapiPurpose.CREDENTIAL_BUNDLE,
    )
    _ = request.bundle_path.write_bytes(protected)
    return BundlePreparationResult(user_count=len(users))


def load_credential_bundle(bundle_path: Path) -> CredentialBundle:
    plaintext = bytearray(
        unprotect_for_current_user(
            bundle_path.read_bytes(),
            DpapiPurpose.CREDENTIAL_BUNDLE,
        )
    )
    try:
        return CredentialBundle.model_validate_json(plaintext)
    finally:
        plaintext[:] = b"\0" * len(plaintext)
