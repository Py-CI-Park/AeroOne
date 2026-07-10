from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import secrets

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.modules.auth.models import User
from app.operations.credential_rotation import (
    CredentialBundle,
    CredentialRotationError,
    RotationErrorCode,
    UserCredential,
)
from app.operations.windows_dpapi import protect_for_current_user, unprotect_for_current_user


class BundlePreparationRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    database_url: str = Field(repr=False, pattern=r'^sqlite:///')
    admin_username: str
    bundle_path: Path


@dataclass(frozen=True, slots=True)
class BundlePreparationResult:
    user_count: int


def inspect_credential_scope(database_url: str, admin_username: str) -> int:
    engine = create_engine(database_url)
    with Session(engine) as session:
        usernames = tuple(session.scalars(select(User.username).order_by(User.id)).all())
    if not usernames:
        raise CredentialRotationError(RotationErrorCode.EMPTY_USER_SET)
    if admin_username not in usernames:
        raise CredentialRotationError(RotationErrorCode.ADMIN_NOT_FOUND)
    return len(usernames)


def prepare_credential_bundle(request: BundlePreparationRequest) -> BundlePreparationResult:
    engine = create_engine(request.database_url)
    with Session(engine) as session:
        usernames = tuple(session.scalars(select(User.username).order_by(User.id)).all())
    inspect_credential_scope(request.database_url, request.admin_username)
    bundle = CredentialBundle(
        admin_username=request.admin_username,
        jwt_secret_key=secrets.token_hex(32),
        users=tuple(
            UserCredential(username=username, password=secrets.token_urlsafe(36))
            for username in usernames
        ),
    )
    protected = protect_for_current_user(bundle.model_dump_json().encode('utf-8'))
    request.bundle_path.write_bytes(protected)
    return BundlePreparationResult(user_count=len(usernames))


def load_credential_bundle(bundle_path: Path) -> CredentialBundle:
    plaintext = bytearray(unprotect_for_current_user(bundle_path.read_bytes()))
    try:
        return CredentialBundle.model_validate_json(plaintext)
    finally:
        plaintext[:] = b'\0' * len(plaintext)
