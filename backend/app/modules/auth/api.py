from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import create_access_token, create_csrf_token, hash_password, verify_password
from app.modules.admin.audit import record_admin_audit
from app.modules.admin.permissions import list_user_permission_keys, list_user_resource_grants
from app.modules.auth.dependencies import get_current_user, get_db, get_settings, require_csrf
from app.modules.auth.schemas import AuthResponse, LoginRequest, PasswordChangeRequest, UserResponse
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
        secure=settings.secure_cookies,
        max_age=settings.access_token_ttl_minutes * 60,
        path='/',
    )
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=csrf_token,
        httponly=False,
        samesite='lax',
        secure=settings.secure_cookies,
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
def me(current_user=Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(current_user)


@router.get('/effective-permissions')
def effective_permissions(db: Session = Depends(get_db), current_user=Depends(get_current_user)) -> dict[str, object]:
    resources = [
        {'resource_type': resource_type, 'resource_id': resource_id, 'permission_key': permission_key}
        for resource_type, resource_id, permission_key in list_user_resource_grants(db, current_user)
    ]
    return {'permissions': sorted(list_user_permission_keys(db, current_user)), 'resources': resources}

def _set_session_cookies(response: Response, settings: Settings, token: str, csrf_token: str) -> None:
    response.set_cookie(
        key=settings.admin_session_cookie_name,
        value=token,
        httponly=True,
        samesite='lax',
        secure=settings.secure_cookies,
        max_age=settings.access_token_ttl_minutes * 60,
        path='/',
    )
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=csrf_token,
        httponly=False,
        samesite='lax',
        secure=settings.secure_cookies,
        max_age=settings.access_token_ttl_minutes * 60,
        path='/',
    )


@router.post('/change-password', response_model=AuthResponse)
def change_password(
    payload: PasswordChangeRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user=Depends(get_current_user),
    _csrf: None = Depends(require_csrf),
) -> AuthResponse:
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Current password is incorrect')
    new_password = payload.new_password.strip()
    if len(new_password) < 8:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='New password must be at least 8 characters')
    if new_password == payload.current_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='New password must differ from the current password')
    current_user.password_hash = hash_password(new_password)
    current_user.password_changed_at = datetime.now(UTC)
    current_user.session_version += 1
    db.flush()
    csrf_token = create_csrf_token()
    token = create_access_token(
        settings.jwt_secret_key,
        str(current_user.id),
        current_user.role,
        csrf_token,
        settings.access_token_ttl_minutes,
        current_user.session_version,
    )
    _set_session_cookies(response, settings, token, csrf_token)
    record_admin_audit(db, actor=current_user, action='account.password_change', target_type='user', target_id=current_user.id, request=request, metadata={'self': True})
    return AuthResponse(user=UserResponse.model_validate(current_user), csrf_token=csrf_token)
