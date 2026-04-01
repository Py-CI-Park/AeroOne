from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.auth.dependencies import get_current_admin, get_db, get_settings, require_csrf
from app.modules.newsletter.repositories.category_repository import CategoryRepository
from app.modules.newsletter.repositories.tag_repository import TagRepository
from app.modules.newsletter.schemas.admin import ThumbnailUploadResponse
from app.modules.newsletter.schemas.newsletter import AdminNewsletterDetailResponse, CategoryResponse, NewsletterCreateRequest, NewsletterDetailResponse, NewsletterListItem, NewsletterUpdateRequest, TagResponse, TaxonomyCreateRequest
from app.modules.newsletter.services.newsletter_service import NewsletterService
from app.modules.newsletter.services.utils import slugify
from app.modules.shared.storage.service import StorageService

router = APIRouter()


def get_storage_service(settings: Settings = Depends(get_settings)) -> StorageService:
    return StorageService(settings.import_root, settings.managed_storage_root)


def get_newsletter_service(db: Session = Depends(get_db), settings: Settings = Depends(get_settings), storage_service: StorageService = Depends(get_storage_service)) -> NewsletterService:
    return NewsletterService(db, settings, storage_service)


@router.get('/newsletters', response_model=list[NewsletterListItem], dependencies=[Depends(get_current_admin)])
def list_admin_newsletters(service: NewsletterService = Depends(get_newsletter_service)) -> list[NewsletterListItem]:
    return service.list_admin()


@router.get('/newsletters/{newsletter_id}', response_model=AdminNewsletterDetailResponse, dependencies=[Depends(get_current_admin)])
def get_admin_newsletter(newsletter_id: int, service: NewsletterService = Depends(get_newsletter_service)) -> AdminNewsletterDetailResponse:
    return service.get_admin_detail(newsletter_id)


@router.post('/newsletters', response_model=NewsletterDetailResponse, dependencies=[Depends(require_csrf)])
def create_newsletter(payload: NewsletterCreateRequest, service: NewsletterService = Depends(get_newsletter_service)) -> NewsletterDetailResponse:
    return service.create_newsletter(payload)


@router.patch('/newsletters/{newsletter_id}', response_model=NewsletterDetailResponse, dependencies=[Depends(require_csrf)])
def update_newsletter(newsletter_id: int, payload: NewsletterUpdateRequest, service: NewsletterService = Depends(get_newsletter_service)) -> NewsletterDetailResponse:
    return service.update_newsletter(newsletter_id, payload)


@router.delete('/newsletters/{newsletter_id}', dependencies=[Depends(require_csrf)])
def delete_newsletter(newsletter_id: int, service: NewsletterService = Depends(get_newsletter_service)) -> dict[str, str]:
    return service.soft_delete(newsletter_id)


@router.post('/newsletters/{newsletter_id}/thumbnail', response_model=ThumbnailUploadResponse, dependencies=[Depends(require_csrf)])
async def upload_thumbnail(newsletter_id: int, file: UploadFile = File(...), service: NewsletterService = Depends(get_newsletter_service), storage_service: StorageService = Depends(get_storage_service), settings: Settings = Depends(get_settings)) -> ThumbnailUploadResponse:
    relative_path = await storage_service.save_thumbnail(file, settings.thumbnails_root)
    return ThumbnailUploadResponse(**service.set_thumbnail(newsletter_id, relative_path))


@router.get('/categories', response_model=list[CategoryResponse], dependencies=[Depends(get_current_admin)])
def list_categories(db: Session = Depends(get_db)) -> list[CategoryResponse]:
    repository = CategoryRepository(db)
    return [CategoryResponse.model_validate(category) for category in repository.list_all()]


@router.post('/categories', response_model=CategoryResponse, dependencies=[Depends(require_csrf)])
def create_category(payload: TaxonomyCreateRequest, db: Session = Depends(get_db)) -> CategoryResponse:
    category = CategoryRepository(db).create(payload.name, slugify(payload.name), payload.description)
    return CategoryResponse.model_validate(category)


@router.get('/tags', response_model=list[TagResponse], dependencies=[Depends(get_current_admin)])
def list_tags(db: Session = Depends(get_db)) -> list[TagResponse]:
    repository = TagRepository(db)
    return [TagResponse.model_validate(tag) for tag in repository.list_all()]


@router.post('/tags', response_model=TagResponse, dependencies=[Depends(require_csrf)])
def create_tag(payload: TaxonomyCreateRequest, db: Session = Depends(get_db)) -> TagResponse:
    tag = TagRepository(db).create(payload.name, slugify(payload.name))
    return TagResponse.model_validate(tag)
