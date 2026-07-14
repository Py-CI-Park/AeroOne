from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import decode_access_token
from app.db.session import get_db_session
from app.modules.admin.models import UserSessionActivity
from app.modules.admin.permissions import has_permission
from app.modules.auth.models import User
from app.modules.auth.repositories import UserRepository

from app.modules.auth.services import requires_password_change


_FIRST_CHANGE_ALLOWED_PATHS = frozenset({
    '/api/v1/auth/change-password',
    '/api/v1/auth/logout',
    '/api/v1/auth/me',
})


def _record_session_activity(request: Request, db: Session, settings: Settings, user: User, token: str, payload: dict) -> None:
    now = datetime.now(UTC)
    debounce_seconds = max(int(settings.session_activity_debounce_seconds), 0)
    cutoff = now - timedelta(seconds=debounce_seconds)
    session_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()
    exp = payload.get('exp')
    expires_at = datetime.fromtimestamp(exp, UTC) if isinstance(exp, (int, float)) else None
    existing = db.execute(
        select(UserSessionActivity).where(
            UserSessionActivity.user_id == user.id,
            UserSessionActivity.session_hash == session_hash,
        )
    ).scalar_one_or_none()
    if existing is None:
        try:
            with db.begin_nested():
                db.add(
                    UserSessionActivity(
                        user_id=user.id,
                        session_hash=session_hash,
                        last_seen_at=now,
                        expires_at=expires_at,
                    )
                )
                db.flush()
            return
        except IntegrityError:
            existing = db.execute(
                select(UserSessionActivity).where(
                    UserSessionActivity.user_id == user.id,
                    UserSessionActivity.session_hash == session_hash,
                )
            ).scalar_one_or_none()
            if existing is None:
                raise
    last_seen = existing.last_seen_at
    if last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=UTC)
    if last_seen < cutoff:
        with db.begin_nested():
            existing.last_seen_at = now
            existing.expires_at = expires_at
            db.flush()


def get_db(db: Session = Depends(get_db_session)) -> Session:
    return db


def _current_user_from_request(request: Request, db: Session, settings: Settings) -> tuple[User, dict]:
    token = request.cookies.get(settings.admin_session_cookie_name)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Authentication required')
    try:
        payload = decode_access_token(token, settings.jwt_secret_key)
    except jwt.PyJWTError as exc:  # pragma: no cover - library mapping
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid session') from exc
    try:
        user_id = int(payload['sub'])
        token_session_version = payload['ver']
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid session') from exc
    if isinstance(token_session_version, bool) or not isinstance(token_session_version, int):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid session')
    user = UserRepository(db).get_by_id(user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid user')
    if token_session_version != user.session_version:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Session expired')
    if requires_password_change(user) and request.url.path not in _FIRST_CHANGE_ALLOWED_PATHS:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Password change required')
    request.state.auth_payload = payload
    request.state.current_user = user
    _record_session_activity(request, db, settings, user, token, payload)
    return user, payload


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    user, _payload = _current_user_from_request(request, db, settings)
    return user


def get_optional_user(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User | None:
    try:
        user, _payload = _current_user_from_request(request, db, settings)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            return None
        raise
    return user


def get_current_admin(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    user, _payload = _current_user_from_request(request, db, settings)
    if user.role != 'admin' or not has_permission(db, user, 'admin.users.read'):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid admin user')
    return user


def require_role(*roles: str):
    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Insufficient role')
        return current_user

    return dependency


def require_permission(permission_key: str):
    def dependency(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> User:
        if not has_permission(db, current_user, permission_key):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Insufficient permission')
        return current_user

    return dependency


def require_csrf(
    request: Request,
    _: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> None:
    header_value = request.headers.get('x-csrf-token')
    csrf_cookie = request.cookies.get(settings.csrf_cookie_name)
    payload = getattr(request.state, 'auth_payload', None)
    expected = payload.get('csrf') if payload else None
    if not header_value or not csrf_cookie or header_value != csrf_cookie or header_value != expected:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='CSRF validation failed')
