from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.newsletter.models.tag import Tag


class TagRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_all(self) -> list[Tag]:
        return list(self.db.scalars(select(Tag).order_by(Tag.name)).all())

    def get_many(self, tag_ids: list[int]) -> list[Tag]:
        if not tag_ids:
            return []
        return list(self.db.scalars(select(Tag).where(Tag.id.in_(tag_ids))).all())

    def create(self, name: str, slug: str) -> Tag:
        tag = Tag(name=name, slug=slug)
        self.db.add(tag)
        self.db.flush()
        return tag
