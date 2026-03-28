from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# Ensure model metadata is imported for Alembic.
from app.modules.auth.models import User  # noqa: E402,F401
from app.modules.newsletter.models import Category, Newsletter, NewsletterAsset, Tag, newsletter_tags  # noqa: E402,F401
