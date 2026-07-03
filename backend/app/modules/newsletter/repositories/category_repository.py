from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.newsletter.models.category import Category


class CategoryRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_all(self, *, include_inactive: bool = False) -> list[Category]:
        stmt = select(Category).order_by(Category.sort_order, Category.name)
        if not include_inactive:
            stmt = stmt.where(Category.is_active.is_(True))
        return list(self.db.scalars(stmt).all())

    def get(self, category_id: int) -> Category | None:
        return self.db.get(Category, category_id)

    def get_by_slug(self, slug: str) -> Category | None:
        return self.db.scalar(select(Category).where(Category.slug == slug))

    def create(self, name: str, slug: str, description: str | None = None) -> Category:
        category = Category(name=name, slug=slug, description=description)
        self.db.add(category)
        self.db.flush()
        return category
