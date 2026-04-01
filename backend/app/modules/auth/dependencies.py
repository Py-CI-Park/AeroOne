from __future__ import annotations

import jwt
from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import decode_access_token
from app.db.session import get_db_session
from app.modules.auth.repositories import UserRepository
from app.modules.auth.models import User


def get_db(db: Session = Depends(get_db_session)) -> Session:
    return db


def get_current_admin(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    token = request.cookies.get(settings.admin_session_cookie_name)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Authentication required')
    try:
        payload = decode_access_token(token, settings.jwt_secret_key)
    except jwt.PyJWTError as exc:  # pragma: no cover - library mapping
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid session') from exc
    user = UserRepository(db).get_by_id(int(payload['sub']))
    if not user or not user.is_active or user.role != 'admin':
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid admin user')
    request.state.auth_payload = payload
    return user


def require_csrf(
    request: Request,
    _: User = Depends(get_current_admin),
            settings: Settings = Depends(get_settings),
            csrf_cookie: str | None = Cookie(default=None, alias='csrf_token'),
        ) -> None:
    header_value = request.headers.get('x-csrf-token')
    payload = getattr(request.state, 'auth_payload', None)
    expected = payload.get('csrf') if payload else None
    if not header_value or not csrf_cookie or header_value != csrf_cookie or header_value != expected:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='CSRF validation failed')
