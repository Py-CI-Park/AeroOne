from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.auth.models import User


class UserRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_username(self, username: str) -> User | None:
        return self.session.scalar(select(User).where(User.username == username))

    def get_by_id(self, user_id: int) -> User | None:
        return self.session.get(User, user_id)

    def save(self, user: User) -> User:
        self.session.add(user)
        self.session.flush()
        return user

    def create(self, *, username: str, password_hash: str, role: str = 'admin', email: str | None = None) -> User:
        user = User(username=username, password_hash=password_hash, role=role, email=email, is_active=True)
        return self.save(user)
