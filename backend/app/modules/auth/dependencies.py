from __future__ import annotations

import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import decode_access_token
from app.db.session import get_db_session
from app.modules.admin.permissions import has_permission
from app.modules.auth.models import User
from app.modules.auth.repositories import UserRepository


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
    user = UserRepository(db).get_by_id(int(payload['sub']))
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid user')
    token_session_version = payload.get('ver')
    if token_session_version is not None and int(token_session_version) != user.session_version:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Session expired')
    request.state.auth_payload = payload
    request.state.current_user = user
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
    except HTTPException:
        return None
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
