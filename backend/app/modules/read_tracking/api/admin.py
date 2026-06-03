from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.modules.auth.dependencies import get_current_admin, get_db, require_csrf
from app.modules.read_tracking.schemas.read_event import PurgeResponse, ReadEventsResponse
from app.modules.read_tracking.services.read_tracking_service import ReadTrackingService

router = APIRouter()


def get_read_tracking_service(db: Session = Depends(get_db)) -> ReadTrackingService:
    return ReadTrackingService(db)


@router.get('/read-events', response_model=ReadEventsResponse, dependencies=[Depends(get_current_admin)])
def list_read_events(
    newsletter_id: int | None = None,
    ip: str | None = None,
    service: ReadTrackingService = Depends(get_read_tracking_service),
) -> ReadEventsResponse:
    return ReadEventsResponse(**service.admin_overview(newsletter_id=newsletter_id, client_ip=ip))


@router.post('/read-events/purge', response_model=PurgeResponse, dependencies=[Depends(require_csrf)])
def purge_read_events(
    newsletter_id: int | None = None,
    service: ReadTrackingService = Depends(get_read_tracking_service),
) -> PurgeResponse:
    """읽음 기록 수동 정리. 보존은 무기한이므로 운영자가 필요할 때만 호출한다.

    newsletter_id 를 주면 해당 글만, 없으면 전체 삭제. 관리자 mutation 이므로
    get_current_admin + require_csrf 로 보호한다.
    """
    return PurgeResponse(deleted=service.purge(newsletter_id))
