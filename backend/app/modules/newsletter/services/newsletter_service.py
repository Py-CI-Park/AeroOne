from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.newsletter.models.newsletter import AssetType, Newsletter, NewsletterAsset, SourceType
from app.modules.newsletter.repositories.category_repository import CategoryRepository
from app.modules.newsletter.repositories.newsletter_repository import NewsletterRepository
from app.modules.newsletter.repositories.tag_repository import TagRepository
from app.modules.newsletter.schemas.newsletter import (
    AdminNewsletterDetailResponse,
    CategoryResponse,
    NewsletterAssetResponse,
    NewsletterCreateRequest,
    NewsletterDetailResponse,
    NewsletterListItem,
    NewsletterUpdateRequest,
    TagResponse,
)
from app.modules.newsletter.services.utils import slugify
from app.modules.shared.storage.service import StorageService


class NewsletterService:
    def __init__(self, db: Session, settings: Settings, storage_service: StorageService) -> None:
        self.db = db
        self.settings = settings
        self.storage_service = storage_service
        self.newsletter_repository = NewsletterRepository(db)
        self.category_repository = CategoryRepository(db)
        self.tag_repository = TagRepository(db)

    def list_public(
        self,
        *,
        q: str | None = None,
        category: str | None = None,
        tag: str | None = None,
        source_type: SourceType | None = None,
    ) -> list[NewsletterListItem]:
        newsletters = self.newsletter_repository.list_public(
            q=q,
            category=category,
            tag=tag,
            source_type=source_type,
        )
        return [self.serialize_newsletter(newsletter) for newsletter in newsletters]

    def list_admin(self) -> list[NewsletterListItem]:
        return [self.serialize_newsletter(newsletter) for newsletter in self.newsletter_repository.list_admin()]

    def get_detail_by_slug(self, slug: str) -> NewsletterDetailResponse:
        newsletter = self.newsletter_repository.get_by_slug(slug)
        if not newsletter or not newsletter.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Newsletter not found')
        return self.serialize_detail(newsletter)

    def get_admin_detail(self, newsletter_id: int) -> AdminNewsletterDetailResponse:
        newsletter = self.get_detail_by_id(newsletter_id, allow_inactive=True)
        return self.serialize_admin_detail(newsletter)

    def get_detail_by_id(self, newsletter_id: int, *, allow_inactive: bool = False) -> Newsletter:
        newsletter = self.newsletter_repository.get_by_id(newsletter_id)
        if not newsletter or (not allow_inactive and not newsletter.is_active):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Newsletter not found')
        return newsletter

    def create_newsletter(self, payload: NewsletterCreateRequest) -> NewsletterDetailResponse:
        slug = slugify(payload.title, fallback='newsletter')
        source_identifier = f'markdown-{slug}'
        if self.newsletter_repository.get_by_source_identifier(source_identifier):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Newsletter already exists')
        newsletter = Newsletter(
            title=payload.title,
            slug=slug,
            description=payload.description,
            summary=payload.summary,
            source_type=payload.source_type,
            source_identifier=source_identifier,
            published_at=payload.published_at,
            is_active=payload.is_active,
        )
        if payload.category_id:
            newsletter.category = self.category_repository.get(payload.category_id)
        newsletter.tags = self.tag_repository.get_many(payload.tag_ids)
        if payload.source_type == SourceType.MARKDOWN:
            markdown_relative = self.storage_service.save_markdown_text(
                self.settings.markdown_root,
                slug,
                payload.markdown_body or f'# {payload.title}\n',
            )
            newsletter.markdown_file_path = markdown_relative
            newsletter.assets.append(
                NewsletterAsset(
                    asset_type=AssetType.MARKDOWN,
                    file_path=markdown_relative,
                    is_primary=True,
                )
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Manual creation supports markdown source_type only',
            )
        self.db.add(newsletter)
        self.db.flush()
        return self.serialize_detail(newsletter)

    def update_newsletter(self, newsletter_id: int, payload: NewsletterUpdateRequest) -> NewsletterDetailResponse:
        newsletter = self.get_detail_by_id(newsletter_id, allow_inactive=True)
        if payload.title is not None:
            newsletter.title = payload.title
            if newsletter.source_identifier.startswith('markdown-'):
                newsletter.slug = slugify(payload.title, fallback=newsletter.slug)
        if payload.description is not None:
            newsletter.description = payload.description
        if payload.summary is not None:
            newsletter.summary = payload.summary
        if payload.source_type is not None:
            newsletter.source_type = payload.source_type
        if payload.published_at is not None:
            newsletter.published_at = payload.published_at
        if payload.category_id is not None:
            newsletter.category = self.category_repository.get(payload.category_id) if payload.category_id else None
        if payload.tag_ids is not None:
            newsletter.tags = self.tag_repository.get_many(payload.tag_ids)
        if payload.is_active is not None:
            newsletter.is_active = payload.is_active
        if payload.markdown_body is not None:
            if newsletter.source_type != SourceType.MARKDOWN:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail='markdown_body requires markdown source_type',
                )
            slug = newsletter.slug or slugify(newsletter.title, fallback='newsletter')
            markdown_relative = self.storage_service.save_markdown_text(
                self.settings.markdown_root,
                slug,
                payload.markdown_body,
            )
            newsletter.markdown_file_path = markdown_relative
            asset = next(
                (asset for asset in newsletter.assets if asset.asset_type == AssetType.MARKDOWN),
                None,
            )
            if asset is None:
                asset = NewsletterAsset(
                    asset_type=AssetType.MARKDOWN,
                    file_path=markdown_relative,
                    is_primary=True,
                )
                newsletter.assets.append(asset)
            asset.file_path = markdown_relative
            asset.is_primary = True
        self.db.flush()
        return self.serialize_detail(newsletter)

    def soft_delete(self, newsletter_id: int) -> dict[str, str]:
        newsletter = self.get_detail_by_id(newsletter_id, allow_inactive=True)
        newsletter.is_active = False
        self.db.flush()
        return {'status': 'ok'}

    def set_thumbnail(self, newsletter_id: int, relative_thumbnail_path: str) -> dict[str, str]:
        newsletter = self.get_detail_by_id(newsletter_id, allow_inactive=True)
        newsletter.thumbnail_path = relative_thumbnail_path
        self.db.flush()
        return {'thumbnail_path': relative_thumbnail_path}

    def serialize_newsletter(self, newsletter: Newsletter) -> NewsletterListItem:
        return NewsletterListItem(
            id=newsletter.id,
            title=newsletter.title,
            slug=newsletter.slug,
            description=newsletter.description,
            source_type=newsletter.source_type,
            thumbnail_url=self._thumbnail_url(newsletter.thumbnail_path),
            published_at=newsletter.published_at,
            category=CategoryResponse.model_validate(newsletter.category) if newsletter.category else None,
            tags=[TagResponse.model_validate(tag) for tag in newsletter.tags],
            available_assets=self._asset_responses(newsletter),
        )

    def serialize_detail(self, newsletter: Newsletter) -> NewsletterDetailResponse:
        base = self.serialize_newsletter(newsletter)
        primary_asset = next((asset for asset in newsletter.assets if asset.is_primary), None)
        default_asset = primary_asset.asset_type if primary_asset else AssetType(newsletter.source_type.value)
        return NewsletterDetailResponse(
            **base.model_dump(),
            summary=newsletter.summary,
            markdown_file_path=newsletter.markdown_file_path,
            default_asset_type=default_asset,
        )

    def serialize_admin_detail(self, newsletter: Newsletter) -> AdminNewsletterDetailResponse:
        detail = self.serialize_detail(newsletter)
        markdown_body = None
        if newsletter.source_type == SourceType.MARKDOWN and newsletter.markdown_file_path:
            markdown_body = self.storage_service.read_managed_text(newsletter.markdown_file_path)
        detail_payload = detail.model_dump()
        detail_payload['available_assets'] = self._asset_responses(newsletter, include_file_paths=True)
        return AdminNewsletterDetailResponse(
            **detail_payload,
            is_active=newsletter.is_active,
            thumbnail_path=newsletter.thumbnail_path,
            source_file_path=newsletter.source_file_path,
            source_identifier=newsletter.source_identifier,
            markdown_body=markdown_body,
        )

    def _asset_responses(self, newsletter: Newsletter, *, include_file_paths: bool = False) -> list[NewsletterAssetResponse]:
        responses: list[NewsletterAssetResponse] = []
        for asset in sorted(newsletter.assets, key=lambda item: item.asset_type.value):
            responses.append(
                NewsletterAssetResponse(
                    asset_type=asset.asset_type,
                    content_url=f'/api/v1/newsletters/{newsletter.id}/content/{asset.asset_type.value}',
                    download_url=f'/api/v1/newsletters/{newsletter.id}/download/{asset.asset_type.value}',
                    is_primary=asset.is_primary,
                    file_path=asset.file_path if include_file_paths else None,
                )
            )
        return responses

    def _thumbnail_url(self, thumbnail_path: str | None) -> str | None:
        return f'/storage/{thumbnail_path}' if thumbnail_path else None
