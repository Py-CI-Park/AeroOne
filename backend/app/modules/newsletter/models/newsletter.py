from __future__ import annotations

from datetime import datetime
import enum

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.modules.newsletter.models.tag import newsletter_tags


class SourceType(str, enum.Enum):
    HTML = 'html'
    PDF = 'pdf'
    MARKDOWN = 'markdown'


class AssetType(str, enum.Enum):
    HTML = 'html'
    PDF = 'pdf'
    MARKDOWN = 'markdown'


class Newsletter(Base):
    __tablename__ = 'newsletters'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[SourceType] = mapped_column(Enum(SourceType, name='sourcetype'), nullable=False)
    source_file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    markdown_file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    thumbnail_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_identifier: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    source_checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_mtime: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    category_id: Mapped[int | None] = mapped_column(ForeignKey('categories.id'), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    category = relationship('Category', back_populates='newsletters')
    assets = relationship('NewsletterAsset', back_populates='newsletter', cascade='all, delete-orphan')
    tags = relationship('Tag', secondary=newsletter_tags, back_populates='newsletters')


class NewsletterAsset(Base):
    __tablename__ = 'newsletter_assets'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    newsletter_id: Mapped[int] = mapped_column(ForeignKey('newsletters.id', ondelete='CASCADE'), nullable=False)
    asset_type: Mapped[AssetType] = mapped_column(Enum(AssetType, name='assettype'), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    newsletter = relationship('Newsletter', back_populates='assets')
