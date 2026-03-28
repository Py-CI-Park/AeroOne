from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.modules.newsletter.models.newsletter import AssetType, SourceType


class CategoryResponse(BaseModel):
    id: int
    name: str
    slug: str
    description: str | None = None

    class Config:
        from_attributes = True


class TagResponse(BaseModel):
    id: int
    name: str
    slug: str

    class Config:
        from_attributes = True


class NewsletterAssetResponse(BaseModel):
    asset_type: AssetType
    content_url: str
    download_url: str
    is_primary: bool


class NewsletterListItem(BaseModel):
    id: int
    title: str
    slug: str
    description: str | None = None
    source_type: SourceType
    thumbnail_url: str | None = None
    published_at: datetime | None = None
    category: CategoryResponse | None = None
    tags: list[TagResponse] = Field(default_factory=list)
    available_assets: list[NewsletterAssetResponse] = Field(default_factory=list)


class NewsletterDetailResponse(NewsletterListItem):
    summary: str | None = None
    markdown_file_path: str | None = None
    default_asset_type: AssetType


class NewsletterCreateRequest(BaseModel):
    title: str
    description: str | None = None
    summary: str | None = None
    source_type: SourceType = SourceType.MARKDOWN
    published_at: datetime | None = None
    category_id: int | None = None
    tag_ids: list[int] = Field(default_factory=list)
    is_active: bool = True
    markdown_body: str | None = None


class NewsletterUpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    summary: str | None = None
    source_type: SourceType | None = None
    published_at: datetime | None = None
    category_id: int | None = None
    tag_ids: list[int] | None = None
    is_active: bool | None = None
    markdown_body: str | None = None


class TaxonomyCreateRequest(BaseModel):
    name: str
    description: str | None = None


class SyncResultResponse(BaseModel):
    created: int
    updated: int
    deactivated: int
    skipped: int
    issues: int
