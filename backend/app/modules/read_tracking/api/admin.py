from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.modules.admin.audit import record_admin_audit
from app.modules.auth.dependencies import get_current_user, get_db, require_csrf, require_permission
from app.modules.auth.models import User
from app.modules.read_tracking.schemas.read_event import PurgeResponse, ReadEventsResponse
from app.modules.read_tracking.services.read_tracking_service import ReadTrackingService

router = APIRouter()


def get_read_tracking_service(db: Session = Depends(get_db)) -> ReadTrackingService:
    return ReadTrackingService(db)


@router.get('/read-events', response_model=ReadEventsResponse, dependencies=[Depends(require_permission('admin.read_tracking.read'))])
def list_read_events(
    newsletter_id: int | None = None,
    ip: str | None = None,
    service: ReadTrackingService = Depends(get_read_tracking_service),
) -> ReadEventsResponse:
    return ReadEventsResponse(**service.admin_overview(newsletter_id=newsletter_id, client_ip=ip))


@router.post('/read-events/purge', response_model=PurgeResponse, dependencies=[Depends(require_permission('admin.read_tracking.purge')), Depends(require_csrf)])
def purge_read_events(
    request: Request,
    newsletter_id: int | None = None,
    service: ReadTrackingService = Depends(get_read_tracking_service),
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PurgeResponse:
    """읽음 기록 수동 정리. 보존은 무기한이므로 운영자가 필요할 때만 호출한다.

    newsletter_id 를 주면 해당 글만, 없으면 전체 삭제. 관리자 mutation 이므로
    get_current_admin + require_csrf 로 보호한다.
    """
    deleted = service.purge(newsletter_id)
    record_admin_audit(db, actor=actor, action='read_events.purge', target_type='read_events', request=request, metadata={'newsletter_id': newsletter_id, 'deleted': deleted})
    return PurgeResponse(deleted=deleted)
