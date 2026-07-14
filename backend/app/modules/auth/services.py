from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import (
    PasswordCandidateError,
    PasswordHashError,
    PASSWORD_MIN_LENGTH,
    create_access_token,
    create_csrf_token,
    hash_password,
    is_retired_password,
    password_hash_uses_retired_password,
    validate_password_candidate,
    verify_password,
)
from app.db.session import Database
from app.modules.admin.models import LoginEvent
from app.modules.auth.models import User
from app.modules.auth.repositories import UserRepository

# A persisted sentinel distinguishes restricted setup accounts from legacy NULL timestamps.
_FIRST_CHANGE_REQUIRED_AT = datetime(1970, 1, 1, tzinfo=UTC)


def requires_password_change(user: User) -> bool:
    changed_at = user.password_changed_at
    if changed_at is None:
        return False
    if changed_at.tzinfo is None:
        changed_at = changed_at.replace(tzinfo=UTC)
    else:
        changed_at = changed_at.astimezone(UTC)
    return changed_at == _FIRST_CHANGE_REQUIRED_AT

def require_password_change(user: User, *, invalidate_sessions: bool = True) -> None:
    user.password_changed_at = _FIRST_CHANGE_REQUIRED_AT
    if invalidate_sessions:
        user.session_version += 1


def set_user_password(
    user: User,
    password: str,
    *,
    password_change_required: bool,
    field_name: str = 'Password',
    minimum_length: int = PASSWORD_MIN_LENGTH,
    previous_password: str | None = None,
    invalidate_sessions: bool = True,
) -> str:
    candidate = validate_password_candidate(
        password,
        field_name=field_name,
        minimum_length=minimum_length,
    )
    if previous_password is not None and candidate == previous_password:
        raise PasswordCandidateError(
            f'{field_name} must differ from the current password'
        )
    user.password_hash = hash_password(candidate)
    if password_change_required:
        require_password_change(user, invalidate_sessions=invalidate_sessions)
    else:
        user.password_changed_at = datetime.now(UTC)
        if invalidate_sessions:
            user.session_version += 1
    return candidate


class AuthError(ValueError):
    pass


class AuthService:
    def __init__(self, db: Session, secret_key: str, ttl_minutes: int) -> None:
        self.db = db
        self.secret_key = secret_key
        self.ttl_minutes = ttl_minutes
        self.user_repository = UserRepository(db)

    def preflight_configured_admin(
        self,
        username: str,
        bootstrap_password: str | None,
    ) -> None:
        user = self.user_repository.get_by_username(username)
        retired_active_users: list[User] = []
        invalid_hash_usernames: list[str] = []
        for active_user in self.db.scalars(
            select(User).where(User.is_active.is_(True)).order_by(User.id)
        ):
            try:
                if password_hash_uses_retired_password(active_user.password_hash):
                    retired_active_users.append(active_user)
            except PasswordHashError:
                invalid_hash_usernames.append(active_user.username)
        if invalid_hash_usernames:
            raise RuntimeError(
                'Active accounts have invalid password hashes: '
                f'{", ".join(invalid_hash_usernames)}. Reset those accounts before starting the service.'
            )
        retired_other_usernames = [
            active_user.username
            for active_user in retired_active_users
            if user is None or active_user.id != user.id
        ]
        if retired_other_usernames:
            raise RuntimeError(
                'Active accounts use the retired password: '
                f'{", ".join(retired_other_usernames)}. Reset those accounts to unique passwords '
                'before starting the service.'
            )
        if bootstrap_password is not None:
            try:
                bootstrap_password = validate_password_candidate(
                    bootstrap_password,
                    field_name='ADMIN_PASSWORD',
                )
            except PasswordCandidateError as exc:
                raise RuntimeError(
                    'Configured administrator bootstrap password is invalid'
                ) from exc

        if user is None:
            if bootstrap_password is None:
                return
            user = User(username=username, password_hash='', role='admin', is_active=True)
            set_user_password(
                user,
                bootstrap_password,
                password_change_required=True,
                field_name='ADMIN_PASSWORD',
                invalidate_sessions=False,
            )
            self.db.add(user)
            self.db.flush()
            return

        try:
            configured_user_uses_retired_password = password_hash_uses_retired_password(
                user.password_hash
            )
        except PasswordHashError as exc:
            raise RuntimeError(
                f'Configured administrator {user.username!r} has an invalid password hash. '
                'Reset the account before starting the service.'
            ) from exc
        if configured_user_uses_retired_password:
            if bootstrap_password is None:
                raise RuntimeError(
                    f'Configured administrator {user.username!r} uses retired credentials and '
                    'cannot be resolved without ADMIN_PASSWORD'
                )
            set_user_password(
                user,
                bootstrap_password,
                password_change_required=True,
                field_name='ADMIN_PASSWORD',
            )
            self.db.flush()
            return

        if (
            bootstrap_password is not None
            and verify_password(bootstrap_password, user.password_hash)
            and not requires_password_change(user)
        ):
            require_password_change(user)
            self.db.flush()

    def login(
        self,
        username: str,
        password: str,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[object, str, str]:
        user = self.user_repository.get_by_username(username)
        valid_password = False
        if user is not None and user.is_active and not is_retired_password(password):
            try:
                valid_password = verify_password(password, user.password_hash)
            except PasswordHashError:
                valid_password = False
        if not valid_password:
            self.db.add(LoginEvent(user_id=user.id if user else None, username=username[:100], ip_address=ip_address, user_agent=user_agent[:500] if user_agent else None, status='failure'))
            self.db.flush()
            raise AuthError('Invalid credentials')
        assert user is not None
        csrf_token = create_csrf_token()
        token = create_access_token(
            self.secret_key,
            str(user.id),
            user.role,
            csrf_token,
            self.ttl_minutes,
            session_version=user.session_version,
        )
        user.last_login_at = datetime.now(UTC)
        self.db.add(LoginEvent(user_id=user.id, username=username[:100], ip_address=ip_address, user_agent=user_agent[:500] if user_agent else None, status='success'))
        self.db.flush()
        return user, token, csrf_token

def preflight_configured_admin(database: Database, settings: Settings) -> None:
    with database.session() as session:
        AuthService(
            session,
            settings.jwt_secret_key,
            settings.access_token_ttl_minutes,
        ).preflight_configured_admin(
            settings.admin_username,
            settings.admin_bootstrap_password,
        )
