from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.modules.admin.models import UserSessionActivity
from app.modules.auth.models import User
from app.operations.credential_rotation_audit import RotationRecord, record_rotation
from app.operations.credential_rotation_contracts import (
    CredentialBundle,
    CredentialRotationError,
    RotationErrorCode,
    RotationRequest,
    RotationResult,
    RotationVerificationResult,
    UserCredential,
    validate_active_admin,
)
from app.operations.credential_rotation_models import (
    CredentialRotationDatabaseState,
    CredentialRotationLedger,
)
from app.operations.credential_rotation_fingerprints import material_fingerprint, state_fingerprint


@dataclass(frozen=True, slots=True)
class RotationTransactionPreflight:
    user_count: int
    session_count: int


def _database_state(session: Session, bundle: CredentialBundle) -> CredentialRotationDatabaseState:
    state = session.get(CredentialRotationDatabaseState, 1)
    if state is None:
        state = CredentialRotationDatabaseState(database_id=str(bundle.database_id))
        session.add(state)
        session.flush()
        return state
    if state.database_id != str(bundle.database_id):
        raise CredentialRotationError(RotationErrorCode.DATABASE_IDENTITY_MISMATCH)
    return state


def ensure_database_identity(database_url: str) -> UUID:
    engine = create_engine(database_url)
    with engine.connect() as connection:
        _ = connection.exec_driver_sql("BEGIN IMMEDIATE")
        with Session(bind=connection) as session:
            state = session.get(CredentialRotationDatabaseState, 1)
            if state is None:
                state = CredentialRotationDatabaseState(database_id=str(uuid4()))
                session.add(state)
                session.flush()
            database_id = UUID(state.database_id)
        connection.commit()
    return database_id


def _existing_result(
    ledger: CredentialRotationLedger,
    bundle: CredentialBundle,
    material_fingerprint: str,
    users: list[User],
    session_count: int,
) -> RotationResult:
    binding = (
        ledger.database_id == str(bundle.database_id)
        and ledger.material_fingerprint == material_fingerprint
        and ledger.post_state_fingerprint == state_fingerprint(users, session_count)
    )
    if not binding:
        raise CredentialRotationError(RotationErrorCode.ROTATION_BINDING_MISMATCH)
    return RotationResult(
        user_count_before=ledger.user_count_before,
        user_count_after=ledger.user_count_after,
        password_count_changed=ledger.password_count_changed,
        session_count_before=ledger.session_count_before,
        session_count_after=ledger.session_count_after,
    )


def _rotate_in_transaction(session: Session, request: RotationRequest) -> RotationResult:
    bundle = request.bundle
    bundle_fingerprint = material_fingerprint(bundle)
    users = list(session.scalars(select(User).order_by(User.id)).all())
    session_count = int(session.scalar(select(func.count()).select_from(UserSessionActivity)) or 0)
    existing = session.get(CredentialRotationLedger, str(bundle.rotation_id))
    if existing is not None:
        return _existing_result(existing, bundle, bundle_fingerprint, users, session_count)
    reused = session.scalar(
        select(CredentialRotationLedger).where(
            CredentialRotationLedger.material_fingerprint == bundle_fingerprint
        )
    )
    if reused is not None:
        raise CredentialRotationError(RotationErrorCode.CREDENTIAL_MATERIAL_REUSED)
    _ = _database_state(session, bundle)
    return _apply_rotation(session, request, users, session_count, bundle_fingerprint)


def find_existing_rotation_result(
    session: Session,
    request: RotationRequest,
) -> RotationResult | None:
    bundle = request.bundle
    users = list(session.scalars(select(User).order_by(User.id)).all())
    session_count = int(session.scalar(select(func.count()).select_from(UserSessionActivity)) or 0)
    ledger = session.get(CredentialRotationLedger, str(bundle.rotation_id))
    if ledger is None:
        return None
    state = session.get(CredentialRotationDatabaseState, 1)
    if state is None or state.database_id != str(bundle.database_id):
        raise CredentialRotationError(RotationErrorCode.DATABASE_IDENTITY_MISMATCH)
    return _existing_result(
        ledger,
        bundle,
        material_fingerprint(bundle),
        users,
        session_count,
    )


def validate_rotation_transaction(
    session: Session,
    request: RotationRequest,
) -> RotationTransactionPreflight:
    users = list(session.scalars(select(User).order_by(User.id)).all())
    session_count = int(session.scalar(select(func.count()).select_from(UserSessionActivity)) or 0)
    _validate_rotation_scope(
        users,
        request.bundle,
        {credential.username: credential for credential in request.bundle.users},
    )
    state = session.get(CredentialRotationDatabaseState, 1)
    if state is None or state.database_id != str(request.bundle.database_id):
        raise CredentialRotationError(RotationErrorCode.DATABASE_IDENTITY_MISMATCH)
    return RotationTransactionPreflight(
        user_count=len(users),
        session_count=session_count,
    )


def rotate_credentials_on_connection(
    connection: Connection,
    request: RotationRequest,
) -> RotationResult:
    with Session(bind=connection) as session:
        return rotate_credentials_in_session(session, request)


def rotate_credentials_in_session(
    session: Session,
    request: RotationRequest,
) -> RotationResult:
    result = _rotate_in_transaction(session, request)
    session.flush()
    return result


def _apply_rotation(
    session: Session,
    request: RotationRequest,
    users: list[User],
    session_count_before: int,
    material_fingerprint: str,
) -> RotationResult:
    bundle = request.bundle
    credential_by_username = {credential.username: credential for credential in bundle.users}
    _validate_rotation_scope(users, bundle, credential_by_username)
    pre_state = state_fingerprint(users, session_count_before)
    authorization_state = {
        user.id: (user.role, user.is_active, user.session_version, user.password_hash)
        for user in users
    }
    changed_at = datetime.now(UTC)
    for user in users:
        user.password_hash = hash_password(credential_by_username[user.username].password)
        user.password_changed_at = changed_at
        user.session_version += 1
    _ = session.execute(delete(UserSessionActivity))
    session.flush()
    _verify_authorization_state(users, authorization_state)
    if request.fail_before_commit:
        raise CredentialRotationError(RotationErrorCode.TEST_FAILPOINT)
    post_state = state_fingerprint(users, 0)
    result = RotationResult(
        user_count_before=len(users),
        user_count_after=len(users),
        password_count_changed=len(users),
        session_count_before=session_count_before,
        session_count_after=0,
    )
    record_rotation(
        session,
        RotationRecord(
            request=request,
            result=result,
            material_fingerprint=material_fingerprint,
            pre_state_fingerprint=pre_state,
            post_state_fingerprint=post_state,
            users=tuple(users),
        ),
    )
    return result


def _validate_rotation_scope(
    users: list[User],
    bundle: CredentialBundle,
    credential_by_username: dict[str, UserCredential],
) -> None:
    if not users:
        raise CredentialRotationError(RotationErrorCode.EMPTY_USER_SET)
    if len(credential_by_username) != len(bundle.users):
        raise CredentialRotationError(RotationErrorCode.DUPLICATE_USERNAME)
    if len({credential.password for credential in bundle.users}) != len(bundle.users):
        raise CredentialRotationError(RotationErrorCode.DUPLICATE_PASSWORD)
    if len(users) != len(bundle.users):
        raise CredentialRotationError(RotationErrorCode.CREDENTIAL_COUNT_MISMATCH)
    if {user.username for user in users} != set(credential_by_username):
        raise CredentialRotationError(RotationErrorCode.CREDENTIAL_IDENTITY_MISMATCH)
    validate_active_admin(users, bundle.admin_username)


def _verify_authorization_state(
    users: list[User],
    authorization_state: dict[int, tuple[str, bool, int, str]],
) -> None:
    for user in users:
        role, is_active, session_version, password_hash = authorization_state[user.id]
        if (user.role, user.is_active, user.session_version) != (
            role,
            is_active,
            session_version + 1,
        ):
            raise CredentialRotationError(RotationErrorCode.INVARIANT_VIOLATION)
        if user.password_hash == password_hash or user.password_changed_at is None:
            raise CredentialRotationError(RotationErrorCode.INVARIANT_VIOLATION)


def rotate_all_credentials(request: RotationRequest) -> RotationResult:
    engine = create_engine(request.database_url)
    with engine.connect() as connection:
        _ = connection.exec_driver_sql("BEGIN IMMEDIATE")
        result = rotate_credentials_on_connection(connection, request)
        connection.commit()
    return result


def verify_rotation_state(request: RotationRequest) -> RotationVerificationResult:
    engine = create_engine(request.database_url)
    with Session(engine) as session:
        users = list(session.scalars(select(User).order_by(User.id)).all())
        ledger = session.get(CredentialRotationLedger, str(request.bundle.rotation_id))
        session_count = int(
            session.scalar(select(func.count()).select_from(UserSessionActivity)) or 0
        )
    if ledger is None:
        raise CredentialRotationError(RotationErrorCode.INVARIANT_VIOLATION)
    _ = _existing_result(
        ledger, request.bundle, material_fingerprint(request.bundle), users, session_count
    )
    credentials = {credential.username: credential for credential in request.bundle.users}
    verified = sum(
        verify_password(credentials[user.username].password, user.password_hash) for user in users
    )
    if verified != len(users):
        raise CredentialRotationError(RotationErrorCode.INVARIANT_VIOLATION)
    return RotationVerificationResult(
        user_count=len(users),
        password_count_verified=verified,
        session_count=session_count,
    )
