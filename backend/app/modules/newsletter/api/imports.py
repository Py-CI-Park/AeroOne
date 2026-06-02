from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.auth.dependencies import get_db, get_settings, require_csrf
from app.modules.newsletter.schemas.newsletter import SyncResultResponse
from app.modules.newsletter.services.newsletter_autosync_service import compute_signature
from app.modules.newsletter.services.newsletter_import_service import NewsletterImportService

router = APIRouter()


@router.post('/newsletters/sync', response_model=SyncResultResponse, dependencies=[Depends(require_csrf)])
def sync_newsletters(request: Request, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)) -> SyncResultResponse:
    result = NewsletterImportService(db, settings.import_root).sync()
    # 수동 sync 도 자동 동기화의 베이스라인 시그니처를 함께 갱신한다. 그래야 폴더가
    # 바뀌지 않은 상태에서 이어지는 공개 읽기가 sync 를 재실행해 (예: HTML <title> 로)
    # 관리자가 방금 수정한 메타데이터를 덮어쓰지 않는다.
    state = getattr(request.app.state, 'autosync_state', None)
    if state is not None:
        with state.lock:
            state.signature = compute_signature(settings.import_root)
    return SyncResultResponse(**asdict(result))
