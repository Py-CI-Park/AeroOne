from __future__ import annotations

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.modules.newsletter.models.newsletter import AssetType, Newsletter, NewsletterAsset, SourceType
from app.modules.newsletter.models.tag import Tag
from app.modules.newsletter.models.category import Category


class NewsletterRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def base_query(self) -> Select[tuple[Newsletter]]:
        return select(Newsletter).options(joinedload(Newsletter.assets), joinedload(Newsletter.tags), joinedload(Newsletter.category))

    def list_public(self, *, q: str | None = None, category: str | None = None, tag: str | None = None, source_type: SourceType | None = None) -> list[Newsletter]:
        stmt = self.base_query().where(Newsletter.is_active.is_(True)).order_by(Newsletter.published_at.desc().nullslast(), Newsletter.created_at.desc())
        if q:
            like = f'%{q.lower()}%'
            stmt = stmt.outerjoin(Newsletter.tags).where(
                or_(
                    func.lower(Newsletter.title).like(like),
                    func.lower(func.coalesce(Newsletter.description, '')).like(like),
                    func.lower(func.coalesce(Tag.name, '')).like(like),
                )
            )
        if category:
            stmt = stmt.join(Newsletter.category).where(Category.slug == category)
        if tag:
            stmt = stmt.join(Newsletter.tags).where(Tag.slug == tag)
        if source_type:
            stmt = stmt.where(Newsletter.source_type == source_type)
        return list(self.db.execute(stmt.distinct()).scalars().unique().all())

    def list_admin(self) -> list[Newsletter]:
        stmt = self.base_query().order_by(Newsletter.updated_at.desc())
        return list(self.db.execute(stmt).scalars().unique().all())

    def get_by_slug(self, slug: str) -> Newsletter | None:
        stmt = self.base_query().where(Newsletter.slug == slug)
        return self.db.execute(stmt).scalars().unique().first()

    def get_by_id(self, newsletter_id: int) -> Newsletter | None:
        stmt = self.base_query().where(Newsletter.id == newsletter_id)
        return self.db.execute(stmt).scalars().unique().first()

    def get_by_source_identifier(self, identifier: str) -> Newsletter | None:
        stmt = self.base_query().where(Newsletter.source_identifier == identifier)
        return self.db.execute(stmt).scalars().unique().first()

    def list_imported_with_external_assets(self) -> list[Newsletter]:
        stmt = self.base_query().join(Newsletter.assets).where(NewsletterAsset.asset_type.in_([AssetType.HTML, AssetType.PDF])).distinct()
        return list(self.db.execute(stmt).scalars().unique().all())
