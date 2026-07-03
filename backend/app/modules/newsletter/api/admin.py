from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.admin.audit import record_admin_audit
from app.modules.auth.dependencies import get_current_user, get_db, get_settings, require_csrf, require_permission
from app.modules.auth.models import User
from app.modules.newsletter.repositories.category_repository import CategoryRepository
from app.modules.newsletter.repositories.tag_repository import TagRepository
from app.modules.newsletter.models.tag import Tag
from app.modules.newsletter.schemas.admin import ThumbnailUploadResponse
from app.modules.newsletter.schemas.newsletter import (
    AdminNewsletterDetailResponse,
    CategoryResponse,
    NewsletterCreateRequest,
    NewsletterDetailResponse,
    NewsletterListItem,
    NewsletterUpdateRequest,
    TagResponse,
    TaxonomyCreateRequest,
    TaxonomyUpdateRequest,
)
from app.modules.newsletter.services.newsletter_service import NewsletterService
from app.modules.newsletter.services.utils import slugify
from app.modules.shared.storage.service import StorageService

router = APIRouter()


def get_storage_service(settings: Settings = Depends(get_settings)) -> StorageService:
    return StorageService(settings.import_root, settings.managed_storage_root)


def get_newsletter_service(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    storage_service: StorageService = Depends(get_storage_service),
) -> NewsletterService:
    return NewsletterService(db, settings, storage_service)


@router.get('/newsletters', response_model=list[NewsletterListItem], dependencies=[Depends(require_permission('admin.newsletters.read'))])
def list_admin_newsletters(
    q: str | None = None,
    status: str | None = None,
    service: NewsletterService = Depends(get_newsletter_service),
) -> list[NewsletterListItem]:
    return service.list_admin(q=q, status=status)


@router.get('/newsletters/{newsletter_id}', response_model=AdminNewsletterDetailResponse, dependencies=[Depends(require_permission('admin.newsletters.read'))])
def get_admin_newsletter(newsletter_id: int, service: NewsletterService = Depends(get_newsletter_service)) -> AdminNewsletterDetailResponse:
    return service.get_admin_detail(newsletter_id)


@router.post('/newsletters', response_model=NewsletterDetailResponse, dependencies=[Depends(require_permission('admin.newsletters.write')), Depends(require_csrf)])
def create_newsletter(
    payload: NewsletterCreateRequest,
    request: Request,
    service: NewsletterService = Depends(get_newsletter_service),
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NewsletterDetailResponse:
    result = service.create_newsletter(payload)
    record_admin_audit(db, actor=actor, action='newsletter.create', target_type='newsletter', target_id=result.id, request=request, after=result.model_dump())
    return result


@router.patch('/newsletters/{newsletter_id}', response_model=NewsletterDetailResponse, dependencies=[Depends(require_permission('admin.newsletters.write')), Depends(require_csrf)])
def update_newsletter(
    newsletter_id: int,
    payload: NewsletterUpdateRequest,
    request: Request,
    service: NewsletterService = Depends(get_newsletter_service),
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NewsletterDetailResponse:
    before = service.serialize_admin_detail(service.get_detail_by_id(newsletter_id, allow_inactive=True)).model_dump()
    result = service.update_newsletter(newsletter_id, payload, actor_id=actor.id)
    record_admin_audit(db, actor=actor, action='newsletter.update', target_type='newsletter', target_id=newsletter_id, request=request, before=before, after=result.model_dump())
    return result


@router.delete('/newsletters/{newsletter_id}', dependencies=[Depends(require_permission('admin.newsletters.write')), Depends(require_csrf)])
def delete_newsletter(
    newsletter_id: int,
    request: Request,
    service: NewsletterService = Depends(get_newsletter_service),
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    before = service.serialize_admin_detail(service.get_detail_by_id(newsletter_id, allow_inactive=True)).model_dump()
    result = service.soft_delete(newsletter_id, actor_id=actor.id)
    record_admin_audit(db, actor=actor, action='newsletter.archive', target_type='newsletter', target_id=newsletter_id, request=request, before=before, after=result)
    return result


@router.post('/newsletters/{newsletter_id}/thumbnail', response_model=ThumbnailUploadResponse, dependencies=[Depends(require_permission('admin.newsletters.write')), Depends(require_csrf)])
async def upload_thumbnail(
    newsletter_id: int,
    request: Request,
    file: UploadFile = File(...),
    service: NewsletterService = Depends(get_newsletter_service),
    storage_service: StorageService = Depends(get_storage_service),
    settings: Settings = Depends(get_settings),
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ThumbnailUploadResponse:
    relative_path = await storage_service.save_thumbnail(file, settings.thumbnails_root)
    result = ThumbnailUploadResponse(**service.set_thumbnail(newsletter_id, relative_path))
    record_admin_audit(db, actor=actor, action='newsletter.thumbnail', target_type='newsletter', target_id=newsletter_id, request=request, after=result.model_dump())
    return result


@router.get('/categories', response_model=list[CategoryResponse], dependencies=[Depends(require_permission('admin.taxonomy.read'))])
def list_categories(db: Session = Depends(get_db)) -> list[CategoryResponse]:
    repository = CategoryRepository(db)
    return [CategoryResponse.model_validate(category) for category in repository.list_all(include_inactive=True)]


@router.post('/categories', response_model=CategoryResponse, dependencies=[Depends(require_permission('admin.taxonomy.manage')), Depends(require_csrf)])
def create_category(
    payload: TaxonomyCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> CategoryResponse:
    category = CategoryRepository(db).create(payload.name, slugify(payload.name), payload.description)
    if payload.sort_order is not None:
        category.sort_order = payload.sort_order
    if payload.is_active is not None:
        category.is_active = payload.is_active
    result = CategoryResponse.model_validate(category)
    record_admin_audit(db, actor=actor, action='category.create', target_type='category', target_id=category.id, request=request, after=result.model_dump())
    return result


@router.patch('/categories/{category_id}', response_model=CategoryResponse, dependencies=[Depends(require_permission('admin.taxonomy.manage')), Depends(require_csrf)])
def update_category(
    category_id: int,
    payload: TaxonomyUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> CategoryResponse:
    repository = CategoryRepository(db)
    category = repository.get(category_id)
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Category not found')
    before = CategoryResponse.model_validate(category).model_dump()
    if payload.name is not None:
        category.name = payload.name
        category.slug = slugify(payload.name)
    if payload.description is not None:
        category.description = payload.description
    if payload.sort_order is not None:
        category.sort_order = payload.sort_order
    if payload.is_active is not None:
        category.is_active = payload.is_active
    db.flush()
    result = CategoryResponse.model_validate(category)
    record_admin_audit(db, actor=actor, action='category.update', target_type='category', target_id=category.id, request=request, before=before, after=result.model_dump())
    return result


@router.get('/tags', response_model=list[TagResponse], dependencies=[Depends(require_permission('admin.taxonomy.read'))])
def list_tags(db: Session = Depends(get_db)) -> list[TagResponse]:
    repository = TagRepository(db)
    return [TagResponse.model_validate(tag) for tag in repository.list_all(include_inactive=True)]


@router.post('/tags', response_model=TagResponse, dependencies=[Depends(require_permission('admin.taxonomy.manage')), Depends(require_csrf)])
def create_tag(
    payload: TaxonomyCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> TagResponse:
    tag = TagRepository(db).create(payload.name, slugify(payload.name))
    if payload.sort_order is not None:
        tag.sort_order = payload.sort_order
    if payload.is_active is not None:
        tag.is_active = payload.is_active
    result = TagResponse.model_validate(tag)
    record_admin_audit(db, actor=actor, action='tag.create', target_type='tag', target_id=tag.id, request=request, after=result.model_dump())
    return result


@router.patch('/tags/{tag_id}', response_model=TagResponse, dependencies=[Depends(require_permission('admin.taxonomy.manage')), Depends(require_csrf)])
def update_tag(
    tag_id: int,
    payload: TaxonomyUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> TagResponse:
    tag = db.get(Tag, tag_id)
    if tag is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Tag not found')
    before = TagResponse.model_validate(tag).model_dump()
    if payload.name is not None:
        tag.name = payload.name
        tag.slug = slugify(payload.name)
    if payload.sort_order is not None:
        tag.sort_order = payload.sort_order
    if payload.is_active is not None:
        tag.is_active = payload.is_active
    db.flush()
    result = TagResponse.model_validate(tag)
    record_admin_audit(db, actor=actor, action='tag.update', target_type='tag', target_id=tag.id, request=request, before=before, after=result.model_dump())
    return result