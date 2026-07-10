from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum, unique
from typing import ClassVar, override
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.modules.auth.models import User


@unique
class RotationErrorCode(StrEnum):
    EMPTY_USER_SET = "empty-user-set"
    CREDENTIAL_COUNT_MISMATCH = "credential-count-mismatch"
    CREDENTIAL_IDENTITY_MISMATCH = "credential-identity-mismatch"
    ADMIN_NOT_FOUND = "admin-not-found"
    ADMIN_ROLE_REQUIRED = "admin-role-required"
    ADMIN_ACTIVE_REQUIRED = "admin-active-required"
    ACTIVE_ADMIN_REQUIRED = "active-admin-required"
    DUPLICATE_USERNAME = "duplicate-username"
    DUPLICATE_PASSWORD = "duplicate-password"
    DATABASE_IDENTITY_MISMATCH = "database-identity-mismatch"
    ROTATION_BINDING_MISMATCH = "rotation-binding-mismatch"
    CREDENTIAL_MATERIAL_REUSED = "credential-material-reused"
    INVARIANT_VIOLATION = "invariant-violation"
    TEST_FAILPOINT = "test-failpoint"


class CredentialRotationError(Exception):
    code: RotationErrorCode

    def __init__(self, code: RotationErrorCode) -> None:
        self.code = code
        super().__init__(code.value)

    @override
    def __str__(self) -> str:
        return self.code.value


class UserCredential(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, strict=True, extra="forbid")

    username: str
    password: str = Field(min_length=24, repr=False)


class CredentialBundle(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, strict=True, extra="forbid")

    rotation_id: UUID = Field(default_factory=uuid4)
    database_id: UUID = Field(default_factory=uuid4)
    admin_username: str
    jwt_secret_key: str = Field(min_length=32, repr=False)
    users: tuple[UserCredential, ...]


class RotationRequest(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, strict=True, extra="forbid")

    database_url: str = Field(repr=False, pattern=r"^sqlite:///")
    bundle: CredentialBundle = Field(repr=False)
    fail_before_commit: bool = False


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


def validate_active_admin(users: list[User], admin_username: str) -> None:
    configured_admin = next((user for user in users if user.username == admin_username), None)
    if configured_admin is None:
        raise CredentialRotationError(RotationErrorCode.ADMIN_NOT_FOUND)
    if configured_admin.role != "admin":
        raise CredentialRotationError(RotationErrorCode.ADMIN_ROLE_REQUIRED)
    if not configured_admin.is_active:
        raise CredentialRotationError(RotationErrorCode.ADMIN_ACTIVE_REQUIRED)
    if not any(user.role == "admin" and user.is_active for user in users):
        raise CredentialRotationError(RotationErrorCode.ACTIVE_ADMIN_REQUIRED)
