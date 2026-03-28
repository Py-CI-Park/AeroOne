from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.auth.dependencies import get_current_admin, get_db, get_settings
from app.modules.auth.schemas import AuthResponse, LoginRequest, UserResponse
from app.modules.auth.services import AuthError, AuthService

router = APIRouter()


@router.post('/login', response_model=AuthResponse)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)) -> AuthResponse:
    service = AuthService(db, settings.jwt_secret_key, settings.access_token_ttl_minutes)
    try:
        user, token, csrf_token = service.login(
            payload.username,
            payload.password,
            seed_username=settings.admin_username,
            seed_password=settings.admin_password,
        )
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    response.set_cookie(
        key=settings.admin_session_cookie_name,
        value=token,
        httponly=True,
        samesite='lax',
        secure=False,
        max_age=settings.access_token_ttl_minutes * 60,
        path='/',
    )
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=csrf_token,
        httponly=False,
        samesite='lax',
        secure=False,
        max_age=settings.access_token_ttl_minutes * 60,
        path='/',
    )
    return AuthResponse(user=UserResponse.model_validate(user), csrf_token=csrf_token)


@router.post('/logout')
def logout(response: Response, settings: Settings = Depends(get_settings)) -> dict[str, str]:
    response.delete_cookie(settings.admin_session_cookie_name, path='/')
    response.delete_cookie(settings.csrf_cookie_name, path='/')
    return {'status': 'ok'}


@router.get('/me', response_model=UserResponse)
def me(current_user=Depends(get_current_admin)) -> UserResponse:
    return UserResponse.model_validate(current_user)
