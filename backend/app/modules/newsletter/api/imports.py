from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.auth.dependencies import get_db, get_settings, require_csrf
from app.modules.newsletter.schemas.newsletter import SyncResultResponse
from app.modules.newsletter.services.newsletter_import_service import NewsletterImportService

router = APIRouter()


@router.post('/newsletters/sync', response_model=SyncResultResponse, dependencies=[Depends(require_csrf)])
def sync_newsletters(db: Session = Depends(get_db), settings: Settings = Depends(get_settings)) -> SyncResultResponse:
    result = NewsletterImportService(db, settings.import_root).sync()
    return SyncResultResponse(**asdict(result))
