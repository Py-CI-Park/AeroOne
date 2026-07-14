"""Leantime 읽기 전용 프록시 API — projects/tasks/calendar.

``main.py`` 에서 ``/api/v1/leantime`` prefix 로 include 한다(이 슬라이스에서는 라우터를
연결하지 않는다). 모든 엔드포인트는 로그인 + ``leantime.read`` 권한을 요구하며, 활성 연결이
없거나 Leantime 호출이 실패해도 절대 500 을 내지 않고 ``degraded=True`` 봉투를 200 으로
돌려준다. 스코프 API 키는 ``decrypted_key`` 로만 서버 내부에서 취급하고 응답/로그 어디에도
넣지 않는다.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.auth.dependencies import get_db, get_settings, require_permission
from app.modules.leantime.connection_service import LeantimeConnectionService
from app.modules.leantime.rpc_client import (
    LeantimeAuthError,
    LeantimeProtocolError,
    LeantimeRpcClient,
    LeantimeRpcError,
    LeantimeUnavailable,
)
from app.modules.leantime.schemas import LeantimeReadResponse

router = APIRouter(dependencies=[Depends(require_permission('leantime.read'))], tags=['leantime-read'])


def _fetched_at() -> str:
    return datetime.now(UTC).isoformat()


def _degraded(reason: str) -> LeantimeReadResponse:
    return LeantimeReadResponse(items=[], degraded=True, reason=reason, fetched_at=_fetched_at())


def _run_read(db: Session, settings: Settings, op) -> LeantimeReadResponse:
    """활성 연결을 해석해 읽기 op 를 실행한다. 어떤 실패도 500 대신 degraded 봉투로 낮춘다."""

    service = LeantimeConnectionService(db, settings)
    connection = service.resolve_active()
    if connection is None:
        return _degraded('not_configured')
    try:
        # 저장 키가 복호화 불가(예: jwt_secret_key 회전으로 MAC 불일치)면 500 대신 degraded.
        api_key = service.decrypted_key(connection)
    except ValueError:
        return _degraded('credential_error')
    client = LeantimeRpcClient(
        base_url=connection.base_url,
        api_key=api_key,
        verify_tls=connection.verify_tls,
    )
    try:
        items = op(client)
    except LeantimeAuthError:
        return _degraded('auth_failed')
    except (LeantimeUnavailable, LeantimeRpcError, LeantimeProtocolError):
        return _degraded('upstream_unavailable')
    return LeantimeReadResponse(items=items, degraded=False, reason=None, fetched_at=_fetched_at())


@router.get('/projects', response_model=LeantimeReadResponse)
def list_projects(db: Session = Depends(get_db), settings: Settings = Depends(get_settings)) -> LeantimeReadResponse:
    return _run_read(db, settings, lambda client: client.list_projects())


@router.get('/tasks', response_model=LeantimeReadResponse)
def list_tasks(db: Session = Depends(get_db), settings: Settings = Depends(get_settings)) -> LeantimeReadResponse:
    return _run_read(db, settings, lambda client: client.list_tasks())


@router.get('/calendar', response_model=LeantimeReadResponse)
def list_calendar(
    start: str,
    end: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> LeantimeReadResponse:
    return _run_read(db, settings, lambda client: client.list_calendar(start, end))
