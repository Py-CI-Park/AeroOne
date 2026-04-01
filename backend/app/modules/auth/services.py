from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.security import create_access_token, create_csrf_token, verify_password
from app.modules.auth.repositories import UserRepository


class AuthError(ValueError):
    pass


class AuthService:
    def __init__(self, db: Session, secret_key: str, ttl_minutes: int) -> None:
        self.db = db
        self.secret_key = secret_key
        self.ttl_minutes = ttl_minutes
        self.user_repository = UserRepository(db)

    def ensure_admin(self, username: str, password: str) -> None:
        if self.user_repository.get_by_username(username) is None:
            from app.core.security import hash_password

            self.user_repository.create(username=username, password_hash=hash_password(password))
            self.db.flush()

    def login(self, username: str, password: str, *, seed_username: str | None = None, seed_password: str | None = None) -> tuple[object, str, str]:
        if seed_username and seed_password:
            self.ensure_admin(seed_username, seed_password)
        user = self.user_repository.get_by_username(username)
        if not user or not user.is_active or not verify_password(password, user.password_hash):
            raise AuthError('Invalid credentials')
        csrf_token = create_csrf_token()
        token = create_access_token(self.secret_key, str(user.id), user.role, csrf_token, self.ttl_minutes)
        user.last_login_at = datetime.now(UTC)
        self.db.flush()
        return user, token, csrf_token
