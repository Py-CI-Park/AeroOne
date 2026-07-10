from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum, unique
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.modules.admin.models import AdminAuditEvent, UserSessionActivity
from app.modules.auth.models import User


@unique
class RotationErrorCode(StrEnum):
    EMPTY_USER_SET = 'empty-user-set'
    CREDENTIAL_COUNT_MISMATCH = 'credential-count-mismatch'
    CREDENTIAL_IDENTITY_MISMATCH = 'credential-identity-mismatch'
    ADMIN_NOT_FOUND = 'admin-not-found'
    DUPLICATE_USERNAME = 'duplicate-username'
    DUPLICATE_PASSWORD = 'duplicate-password'
    INVARIANT_VIOLATION = 'invariant-violation'
    TEST_FAILPOINT = 'test-failpoint'


@dataclass(frozen=True, slots=True)
class CredentialRotationError(Exception):
    code: RotationErrorCode

    def __str__(self) -> str:
        return self.code.value


class UserCredential(BaseModel):
    model_config = ConfigDict(frozen=True)

    username: str
    password: str = Field(min_length=24, repr=False)


class CredentialBundle(BaseModel):
    model_config = ConfigDict(frozen=True)

    rotation_id: UUID = Field(default_factory=uuid4)
    admin_username: str
    jwt_secret_key: str = Field(min_length=32, repr=False)
    users: tuple[UserCredential, ...]


class RotationRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    database_url: str = Field(repr=False, pattern=r'^sqlite:///')
    bundle: CredentialBundle = Field(repr=False)
    fail_before_commit: bool = False


class RotationMarker(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_count_before: int
    user_count_after: int
    password_count_changed: int
    session_count_before: int
    session_count_after: int


@dataclass(frozen=True, slots=True)
class RotationResult:
    user_count_before: int
    user_count_after: int
    password_count_changed: int
    session_count_before: int
    session_count_after: int


@dataclass(frozen=True, slots=True)
class RotationVerificationResult:
    user_count: int
    password_count_verified: int
    session_count: int


def rotate_all_credentials(request: RotationRequest) -> RotationResult:
    bundle = request.bundle
    credential_by_username = {credential.username: credential for credential in bundle.users}
    if len(credential_by_username) != len(bundle.users):
        raise CredentialRotationError(RotationErrorCode.DUPLICATE_USERNAME)
    if len({credential.password for credential in bundle.users}) != len(bundle.users):
        raise CredentialRotationError(RotationErrorCode.DUPLICATE_PASSWORD)

    engine = create_engine(request.database_url)
    with Session(engine) as session, session.begin():
        existing_marker = session.scalar(
            select(AdminAuditEvent).where(
                AdminAuditEvent.action == 'security.credential_rotation',
                AdminAuditEvent.target_id == str(bundle.rotation_id),
            )
        )
        if existing_marker is not None:
            if existing_marker.metadata_json is None:
                raise CredentialRotationError(RotationErrorCode.INVARIANT_VIOLATION)
            marker = RotationMarker.model_validate_json(existing_marker.metadata_json)
            return RotationResult(
                user_count_before=marker.user_count_before,
                user_count_after=marker.user_count_after,
                password_count_changed=marker.password_count_changed,
                session_count_before=marker.session_count_before,
                session_count_after=marker.session_count_after,
            )
        users = list(session.scalars(select(User).order_by(User.id)).all())
        if not users:
            raise CredentialRotationError(RotationErrorCode.EMPTY_USER_SET)
        if len(users) != len(bundle.users):
            raise CredentialRotationError(RotationErrorCode.CREDENTIAL_COUNT_MISMATCH)
        if {user.username for user in users} != set(credential_by_username):
            raise CredentialRotationError(RotationErrorCode.CREDENTIAL_IDENTITY_MISMATCH)
        if bundle.admin_username not in credential_by_username:
            raise CredentialRotationError(RotationErrorCode.ADMIN_NOT_FOUND)

        session_count_before = int(session.scalar(select(func.count()).select_from(UserSessionActivity)) or 0)
        authorization_state = {
            user.id: (user.role, user.is_active, user.session_version, user.password_hash)
            for user in users
        }
        changed_at = datetime.now(UTC)
        for user in users:
            credential = credential_by_username[user.username]
            user.password_hash = hash_password(credential.password)
            user.password_changed_at = changed_at
            user.session_version += 1
        session.execute(delete(UserSessionActivity))
        session.flush()

        passwords_changed = 0
        for user in users:
            role, is_active, session_version, password_hash = authorization_state[user.id]
            if (user.role, user.is_active, user.session_version) != (role, is_active, session_version + 1):
                raise CredentialRotationError(RotationErrorCode.INVARIANT_VIOLATION)
            if user.password_hash == password_hash or user.password_changed_at is None:
                raise CredentialRotationError(RotationErrorCode.INVARIANT_VIOLATION)
            passwords_changed += 1
        if request.fail_before_commit:
            raise CredentialRotationError(RotationErrorCode.TEST_FAILPOINT)

        marker = RotationMarker(
            user_count_before=len(users),
            user_count_after=len(users),
            password_count_changed=passwords_changed,
            session_count_before=session_count_before,
            session_count_after=0,
        )
        session.add(
            AdminAuditEvent(
                action='security.credential_rotation',
                target_type='system',
                target_id=str(bundle.rotation_id),
                status='success',
                metadata_json=marker.model_dump_json(),
            )
        )

    return RotationResult(
        user_count_before=len(users),
        user_count_after=len(users),
        password_count_changed=passwords_changed,
        session_count_before=session_count_before,
        session_count_after=0,
    )


def verify_rotation_state(request: RotationRequest) -> RotationVerificationResult:
    bundle = request.bundle
    credential_by_username = {credential.username: credential for credential in bundle.users}
    engine = create_engine(request.database_url)
    with Session(engine) as session:
        users = list(session.scalars(select(User).order_by(User.id)).all())
        marker = session.scalar(
            select(AdminAuditEvent).where(
                AdminAuditEvent.action == 'security.credential_rotation',
                AdminAuditEvent.target_id == str(bundle.rotation_id),
            )
        )
        session_count = int(session.scalar(select(func.count()).select_from(UserSessionActivity)) or 0)
    if marker is None or len(users) != len(bundle.users):
        raise CredentialRotationError(RotationErrorCode.INVARIANT_VIOLATION)
    if {user.username for user in users} != set(credential_by_username) or session_count != 0:
        raise CredentialRotationError(RotationErrorCode.INVARIANT_VIOLATION)
    verified = sum(
        verify_password(credential_by_username[user.username].password, user.password_hash)
        for user in users
    )
    if verified != len(users):
        raise CredentialRotationError(RotationErrorCode.INVARIANT_VIOLATION)
    return RotationVerificationResult(
        user_count=len(users),
        password_count_verified=verified,
        session_count=session_count,
    )
