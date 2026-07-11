"""LLM 연결 레지스트리 관리자 API.

``main.py`` 에서 ``/api/v1/admin`` prefix 로 include 한다(기존 admin 프록시 재사용).
읽기는 ``admin.ai.read``, 변경은 ``admin.ai.manage`` + ``require_csrf`` 로 게이트하고,
모든 변경은 감사기록을 남긴다. 감사 스냅샷·응답 DTO 어디에도 평문 키는 넣지 않는다
(마스킹 값만, 게다가 audit._redact 가 ``api_key`` 포함 키를 한 번 더 REDACT 한다).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.admin.audit import record_admin_audit
from app.modules.ai.llm_connection_service import LlmConnectionService
from app.modules.ai.models import LlmConnection
from app.modules.ai.openai_client import LlmConnectionError
from app.modules.ai.schemas import (
    LlmConnectionCreate,
    LlmConnectionResponse,
    LlmConnectionUpdate,
    LlmVerifyResponse,
)
from app.modules.auth.dependencies import get_current_user, get_db, get_settings, require_csrf, require_permission
from app.modules.auth.models import User

router = APIRouter()


def _serialize(service: LlmConnectionService, connection: LlmConnection) -> LlmConnectionResponse:
    return LlmConnectionResponse(
        id=connection.id,
        name=connection.name,
        base_url=connection.base_url,
        default_model=connection.default_model,
        is_enabled=connection.is_enabled,
        is_default=connection.is_default,
        verify_tls=connection.verify_tls,
        api_key_masked=service.masked_key(connection),
        created_at=connection.created_at,
        updated_at=connection.updated_at,
    )


def _audit_snapshot(service: LlmConnectionService, connection: LlmConnection) -> dict[str, object]:
    return {
        'id': connection.id,
        'name': connection.name,
        'base_url': connection.base_url,
        'default_model': connection.default_model,
        'is_enabled': connection.is_enabled,
        'is_default': connection.is_default,
        'verify_tls': connection.verify_tls,
        'api_key_masked': service.masked_key(connection),
    }


def _get_or_404(service: LlmConnectionService, connection_id: int) -> LlmConnection:
    connection = service.get(connection_id)
    if connection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='LLM connection not found')
    return connection


@router.get(
    '/llm-connections',
    response_model=list[LlmConnectionResponse],
    dependencies=[Depends(require_permission('admin.ai.read'))],
)
def list_llm_connections(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> list[LlmConnectionResponse]:
    service = LlmConnectionService(db, settings)
    return [_serialize(service, connection) for connection in service.list()]


@router.post(
    '/llm-connections',
    response_model=LlmConnectionResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission('admin.ai.manage')), Depends(require_csrf)],
)
def create_llm_connection(
    payload: LlmConnectionCreate,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    actor: User = Depends(get_current_user),
) -> LlmConnectionResponse:
    service = LlmConnectionService(db, settings)
    connection = service.create(payload)
    record_admin_audit(
        db,
        actor=actor,
        action='llm_connection.create',
        target_type='llm_connection',
        target_id=connection.id,
        request=request,
        after=_audit_snapshot(service, connection),
    )
    return _serialize(service, connection)


@router.patch(
    '/llm-connections/{connection_id}',
    response_model=LlmConnectionResponse,
    dependencies=[Depends(require_permission('admin.ai.manage')), Depends(require_csrf)],
)
def update_llm_connection(
    connection_id: int,
    payload: LlmConnectionUpdate,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    actor: User = Depends(get_current_user),
) -> LlmConnectionResponse:
    service = LlmConnectionService(db, settings)
    before = _audit_snapshot(service, _get_or_404(service, connection_id))
    connection = service.update(connection_id, payload)
    if connection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='LLM connection not found')
    record_admin_audit(
        db,
        actor=actor,
        action='llm_connection.update',
        target_type='llm_connection',
        target_id=connection.id,
        request=request,
        before=before,
        after=_audit_snapshot(service, connection),
    )
    return _serialize(service, connection)


@router.delete(
    '/llm-connections/{connection_id}',
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permission('admin.ai.manage')), Depends(require_csrf)],
)
def delete_llm_connection(
    connection_id: int,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    actor: User = Depends(get_current_user),
) -> Response:
    service = LlmConnectionService(db, settings)
    before = _audit_snapshot(service, _get_or_404(service, connection_id))
    service.delete(connection_id)
    record_admin_audit(
        db,
        actor=actor,
        action='llm_connection.delete',
        target_type='llm_connection',
        target_id=connection_id,
        request=request,
        before=before,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    '/llm-connections/{connection_id}/default',
    response_model=LlmConnectionResponse,
    dependencies=[Depends(require_permission('admin.ai.manage')), Depends(require_csrf)],
)
def set_default_llm_connection(
    connection_id: int,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    actor: User = Depends(get_current_user),
) -> LlmConnectionResponse:
    service = LlmConnectionService(db, settings)
    _get_or_404(service, connection_id)
    connection = service.set_default(connection_id)
    assert connection is not None  # 위 _get_or_404 로 존재 보장.
    record_admin_audit(
        db,
        actor=actor,
        action='llm_connection.set_default',
        target_type='llm_connection',
        target_id=connection.id,
        request=request,
        after=_audit_snapshot(service, connection),
    )
    return _serialize(service, connection)


@router.post(
    '/llm-connections/{connection_id}/verify',
    response_model=LlmVerifyResponse,
    dependencies=[Depends(require_permission('admin.ai.manage')), Depends(require_csrf)],
)
def verify_llm_connection(
    connection_id: int,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    actor: User = Depends(get_current_user),
) -> LlmVerifyResponse:
    service = LlmConnectionService(db, settings)
    connection = _get_or_404(service, connection_id)
    try:
        models = service.client_for(connection).list_models()
    except LlmConnectionError as exc:
        result = LlmVerifyResponse(ok=False, models=[], detail=str(exc))
    else:
        result = LlmVerifyResponse(ok=True, models=models, detail=None)
    record_admin_audit(
        db,
        actor=actor,
        action='llm_connection.verify',
        target_type='llm_connection',
        target_id=connection.id,
        request=request,
        metadata={'ok': result.ok, 'model_count': len(result.models)},
    )
    return result


@router.get(
    '/llm-connections/{connection_id}/models',
    response_model=LlmVerifyResponse,
    dependencies=[Depends(require_permission('admin.ai.read'))],
)
def list_llm_connection_models(
    connection_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> LlmVerifyResponse:
    service = LlmConnectionService(db, settings)
    connection = _get_or_404(service, connection_id)
    try:
        models = service.client_for(connection).list_models()
    except LlmConnectionError as exc:
        return LlmVerifyResponse(ok=False, models=[], detail=str(exc))
    return LlmVerifyResponse(ok=True, models=models, detail=None)
