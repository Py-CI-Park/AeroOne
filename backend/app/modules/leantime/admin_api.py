"""Leantime 연결 레지스트리 관리자 API.

``main.py`` 에서 ``/api/v1/admin`` prefix 로 include 한다(LLM 연결 레지스트리 admin API와
동일한 패턴). 읽기는 ``admin.leantime.read``, 변경은 ``admin.leantime.manage`` +
``require_csrf`` 로 게이트하고, 모든 변경(및 verify)은 감사기록을 남긴다. 감사 스냅샷·응답
DTO 어디에도 평문 키는 넣지 않는다(마스킹 값만, 게다가 공개 ``redact_audit_metadata`` 계약이
``api_key`` 포함 키를 한 번 더 REDACT 한다).

Leantime 자체와의 통신은 ``rpc_client.LeantimeRpcClient`` (공식 JSON-RPC 화이트리스트
경계) 로만 이뤄지며, 이 모듈은 Leantime DB/세션에 절대 접근하지 않는다. 클라이언트는
호출 시점에 지연 임포트해 테스트가 모듈을 monkeypatch 할 수 있게 한다.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.admin.audit import record_admin_audit
from app.modules.auth.dependencies import get_current_user, get_db, get_settings, require_csrf, require_permission
from app.modules.auth.models import User
from app.modules.leantime.connection_service import LeantimeConnectionService
from app.modules.leantime.models import LeantimeConnection
from app.modules.leantime.schemas import (
    LeantimeConnectionCreate,
    LeantimeConnectionResponse,
    LeantimeConnectionUpdate,
)

router = APIRouter()


class LeantimeRotateKeyRequest(BaseModel):
    api_key: str = Field(min_length=1, max_length=2000)


class LeantimeVerifyResponse(BaseModel):
    status: str  # 'ok' | 'unreachable' | 'auth_failed' | 'error'
    detail: str | None = None


def _serialize(service: LeantimeConnectionService, connection: LeantimeConnection) -> LeantimeConnectionResponse:
    return LeantimeConnectionResponse(
        id=connection.id,
        name=connection.name,
        base_url=connection.base_url,
        is_enabled=connection.is_enabled,
        verify_tls=connection.verify_tls,
        api_key_masked=service.masked_key(connection),
        created_at=connection.created_at,
        updated_at=connection.updated_at,
    )


def _audit_snapshot(service: LeantimeConnectionService, connection: LeantimeConnection) -> dict[str, object]:
    return {
        'id': connection.id,
        'name': connection.name,
        'base_url': connection.base_url,
        'is_enabled': connection.is_enabled,
        'verify_tls': connection.verify_tls,
        'api_key_masked': service.masked_key(connection),
    }


def _get_or_404(service: LeantimeConnectionService, connection_id: int) -> LeantimeConnection:
    connection = service.get(connection_id)
    if connection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Leantime connection not found')
    return connection


@router.get(
    '/leantime-connections',
    response_model=list[LeantimeConnectionResponse],
    dependencies=[Depends(require_permission('admin.leantime.read'))],
)
def list_leantime_connections(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> list[LeantimeConnectionResponse]:
    service = LeantimeConnectionService(db, settings)
    return [_serialize(service, connection) for connection in service.list()]


@router.post(
    '/leantime-connections',
    response_model=LeantimeConnectionResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission('admin.leantime.manage')), Depends(require_csrf)],
)
def create_leantime_connection(
    payload: LeantimeConnectionCreate,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    actor: User = Depends(get_current_user),
) -> LeantimeConnectionResponse:
    service = LeantimeConnectionService(db, settings)
    connection = service.create(payload)
    record_admin_audit(
        db,
        actor=actor,
        action='leantime_connection.create',
        target_type='leantime_connection',
        target_id=connection.id,
        request=request,
        after=_audit_snapshot(service, connection),
    )
    return _serialize(service, connection)


@router.get(
    '/leantime-connections/{connection_id}',
    response_model=LeantimeConnectionResponse,
    dependencies=[Depends(require_permission('admin.leantime.read'))],
)
def get_leantime_connection(
    connection_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> LeantimeConnectionResponse:
    service = LeantimeConnectionService(db, settings)
    connection = _get_or_404(service, connection_id)
    return _serialize(service, connection)


@router.patch(
    '/leantime-connections/{connection_id}',
    response_model=LeantimeConnectionResponse,
    dependencies=[Depends(require_permission('admin.leantime.manage')), Depends(require_csrf)],
)
def update_leantime_connection(
    connection_id: int,
    payload: LeantimeConnectionUpdate,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    actor: User = Depends(get_current_user),
) -> LeantimeConnectionResponse:
    service = LeantimeConnectionService(db, settings)
    before = _audit_snapshot(service, _get_or_404(service, connection_id))
    connection = service.update(connection_id, payload)
    if connection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Leantime connection not found')
    record_admin_audit(
        db,
        actor=actor,
        action='leantime_connection.update',
        target_type='leantime_connection',
        target_id=connection.id,
        request=request,
        before=before,
        after=_audit_snapshot(service, connection),
    )
    return _serialize(service, connection)


@router.put(
    '/leantime-connections/{connection_id}',
    response_model=LeantimeConnectionResponse,
    dependencies=[Depends(require_permission('admin.leantime.manage')), Depends(require_csrf)],
)
def replace_leantime_connection(
    connection_id: int,
    payload: LeantimeConnectionUpdate,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    actor: User = Depends(get_current_user),
) -> LeantimeConnectionResponse:
    return update_leantime_connection(connection_id, payload, request, db, settings, actor)


@router.delete(
    '/leantime-connections/{connection_id}',
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permission('admin.leantime.manage')), Depends(require_csrf)],
)
def delete_leantime_connection(
    connection_id: int,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    actor: User = Depends(get_current_user),
) -> Response:
    service = LeantimeConnectionService(db, settings)
    before = _audit_snapshot(service, _get_or_404(service, connection_id))
    service.delete(connection_id)
    record_admin_audit(
        db,
        actor=actor,
        action='leantime_connection.delete',
        target_type='leantime_connection',
        target_id=connection_id,
        request=request,
        before=before,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    '/leantime-connections/{connection_id}/rotate-key',
    response_model=LeantimeConnectionResponse,
    dependencies=[Depends(require_permission('admin.leantime.manage')), Depends(require_csrf)],
)
def rotate_leantime_connection_key(
    connection_id: int,
    payload: LeantimeRotateKeyRequest,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    actor: User = Depends(get_current_user),
) -> LeantimeConnectionResponse:
    service = LeantimeConnectionService(db, settings)
    _get_or_404(service, connection_id)
    connection = service.rotate_key(connection_id, payload.api_key)
    assert connection is not None  # 위 _get_or_404 로 존재 보장.
    record_admin_audit(
        db,
        actor=actor,
        action='leantime_connection.rotate_key',
        target_type='leantime_connection',
        target_id=connection.id,
        request=request,
        after=_audit_snapshot(service, connection),
    )
    return _serialize(service, connection)


@router.post(
    '/leantime-connections/{connection_id}/verify',
    response_model=LeantimeVerifyResponse,
    dependencies=[Depends(require_permission('admin.leantime.manage')), Depends(require_csrf)],
)
def verify_leantime_connection(
    connection_id: int,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    actor: User = Depends(get_current_user),
) -> LeantimeVerifyResponse:
    from app.modules.leantime.rpc_client import (
        LeantimeAuthError,
        LeantimeProtocolError,
        LeantimeRpcClient,
        LeantimeRpcError,
        LeantimeUnavailable,
    )

    service = LeantimeConnectionService(db, settings)
    connection = _get_or_404(service, connection_id)
    try:
        # 저장 키가 복호화 불가(예: 시크릿 회전으로 MAC 불일치)면 500 대신 status='error'.
        api_key = service.decrypted_key(connection)
    except ValueError:
        result = LeantimeVerifyResponse(status='error', detail='stored credential is unusable; re-register the API key')
    else:
        client = LeantimeRpcClient(
            connection.base_url,
            api_key,
            verify_tls=connection.verify_tls,
        )
        try:
            client.list_projects()
        except LeantimeAuthError:
            result = LeantimeVerifyResponse(status='auth_failed', detail='Leantime rejected the scoped API key')
        except LeantimeUnavailable:
            result = LeantimeVerifyResponse(status='unreachable', detail='Leantime did not respond')
        except (LeantimeRpcError, LeantimeProtocolError) as exc:
            # 예외 문자열은 어댑터가 안전하게 만들어 낸 것으로, 키/URL 쿼리스트링을 포함하지 않는다.
            result = LeantimeVerifyResponse(status='error', detail=str(exc))
        else:
            result = LeantimeVerifyResponse(status='ok', detail=None)
    record_admin_audit(
        db,
        actor=actor,
        action='leantime_connection.verify',
        target_type='leantime_connection',
        target_id=connection.id,
        request=request,
        metadata={'status': result.status},
    )
    return result
