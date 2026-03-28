from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.auth.dependencies import get_db, get_settings
from app.modules.newsletter.models.newsletter import AssetType, SourceType
from app.modules.newsletter.schemas.newsletter import NewsletterDetailResponse, NewsletterListItem
from app.modules.newsletter.services.html_render_service import HTML_CSP, HtmlRenderService
from app.modules.newsletter.services.markdown_render_service import MarkdownRenderService
from app.modules.newsletter.services.newsletter_service import NewsletterService
from app.modules.newsletter.services.pdf_delivery_service import PdfDeliveryService
from app.modules.shared.storage.service import StorageService

router = APIRouter()


def get_storage_service(settings: Settings = Depends(get_settings)) -> StorageService:
    return StorageService(settings.import_root, settings.managed_storage_root)


def get_newsletter_service(db: Session = Depends(get_db), settings: Settings = Depends(get_settings), storage_service: StorageService = Depends(get_storage_service)) -> NewsletterService:
    return NewsletterService(db, settings, storage_service)


@router.get('', response_model=list[NewsletterListItem])
def list_newsletters(q: str | None = None, category: str | None = None, tag: str | None = None, source_type: SourceType | None = None, service: NewsletterService = Depends(get_newsletter_service)) -> list[NewsletterListItem]:
    return service.list_public(q=q, category=category, tag=tag, source_type=source_type)


@router.get('/{slug}', response_model=NewsletterDetailResponse)
def get_newsletter(slug: str, service: NewsletterService = Depends(get_newsletter_service)) -> NewsletterDetailResponse:
    return service.get_detail_by_slug(slug)


@router.get('/{newsletter_id}/content/{asset_type}')
def get_newsletter_content(newsletter_id: int, asset_type: AssetType, response: Response, service: NewsletterService = Depends(get_newsletter_service), storage_service: StorageService = Depends(get_storage_service)):
    newsletter = service.get_detail_by_id(newsletter_id)
    asset = next((asset for asset in newsletter.assets if asset.asset_type == asset_type), None)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Asset not found')
    if asset_type == AssetType.PDF:
        path = PdfDeliveryService(storage_service).resolve_pdf_path(asset.file_path)
        return FileResponse(path, media_type='application/pdf', filename=path.name)
    response.headers['Content-Security-Policy'] = HTML_CSP
    if asset_type == AssetType.HTML:
        return {'asset_type': asset_type, 'content_html': HtmlRenderService(storage_service).render(asset.file_path)}
    return {'asset_type': asset_type, 'content_html': MarkdownRenderService(storage_service, HtmlRenderService(storage_service)).render(asset.file_path)}


@router.get('/{newsletter_id}/download/{asset_type}')
def download_newsletter_asset(newsletter_id: int, asset_type: AssetType, service: NewsletterService = Depends(get_newsletter_service), storage_service: StorageService = Depends(get_storage_service)):
    newsletter = service.get_detail_by_id(newsletter_id)
    asset = next((asset for asset in newsletter.assets if asset.asset_type == asset_type), None)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Asset not found')
    if asset_type == AssetType.MARKDOWN:
        path = storage_service.resolve_managed_relative_path(asset.file_path)
        media_type = 'text/markdown; charset=utf-8'
    elif asset_type == AssetType.PDF:
        path = storage_service.resolve_external_relative_path(asset.file_path)
        media_type = 'application/pdf'
    else:
        path = storage_service.resolve_external_relative_path(asset.file_path)
        media_type = 'text/html; charset=utf-8'
    return FileResponse(path, media_type=media_type, filename=path.name)
