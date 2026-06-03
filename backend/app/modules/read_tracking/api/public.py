from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.modules.auth.dependencies import get_db
from app.modules.read_tracking.schemas.read_event import ReadBeaconResponse
from app.modules.read_tracking.services.read_tracking_service import ReadTrackingService

router = APIRouter()


def get_read_tracking_service(db: Session = Depends(get_db)) -> ReadTrackingService:
    return ReadTrackingService(db)


def _client_ip(request: Request) -> str:
    # 리버스 프록시 없는 직결 전제(start_offline 은 uvicorn --host 0.0.0.0 직접 구동).
    # 따라서 request.client.host 가 곧 독자 LAN IP 다. X-Forwarded-For 는 위조 가능하므로
    # 기본 신뢰하지 않는다(프록시를 두게 되면 이 전제를 재검토해야 한다).
    if request.client is not None and request.client.host:
        return request.client.host
    return 'unknown'


@router.post('/{newsletter_id}/read', response_model=ReadBeaconResponse)
def record_newsletter_read(
    newsletter_id: int,
    request: Request,
    service: ReadTrackingService = Depends(get_read_tracking_service),
) -> ReadBeaconResponse:
    """공개 읽음 비콘. body 없음 · 무인증 · 무CSRF.

    브라우저가 백엔드를 직접 호출해야 request.client.host 가 독자 LAN IP 가 된다
    (SSR/프록시 경로는 Next 서버 IP 로 퇴화). 미존재 newsletter_id 는 404 + 행 미생성.
    auto_sync 의존성은 일부러 붙이지 않는다(폴더 스캔/lock 경합 회피).
    """
    service.record(newsletter_id, _client_ip(request))
    return ReadBeaconResponse(recorded=True)
