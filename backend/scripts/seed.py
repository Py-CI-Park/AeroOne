from __future__ import annotations

from datetime import UTC, datetime
from sqlalchemy import select

from app.core.config import Settings
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import Database
from app.modules.auth.repositories import UserRepository
from app.modules.newsletter.models.category import Category
from app.modules.newsletter.models.newsletter import AssetType, Newsletter, NewsletterAsset, SourceType
from app.modules.newsletter.models.tag import Tag
from app.modules.newsletter.services.newsletter_import_service import ImportResult, NewsletterImportService


def _sync_external_newsletters(settings: Settings, session) -> ImportResult | None:
    if not settings.import_root.exists():
        return None
    return NewsletterImportService(session, settings.import_root).sync()


def main() -> None:
    settings = Settings()
    settings.ensure_directories()
    database = Database(settings.database_url)
    Base.metadata.create_all(bind=database.engine)
    sync_result: ImportResult | None = None

    sample_markdown_path = settings.markdown_root / 'sample-welcome.md'
    if not sample_markdown_path.exists():
        sample_markdown_path.write_text('# AeroOne 샘플\n\nSeed markdown document.', encoding='utf-8')

    with database.session() as session:
        user_repo = UserRepository(session)
        admin = user_repo.get_by_username(settings.admin_username)
        if admin is None:
            user_repo.create(username=settings.admin_username, password_hash=hash_password(settings.admin_password))

        category = session.scalar(select(Category).where(Category.slug == 'briefing'))
        if category is None:
            category = Category(name='브리핑', slug='briefing', description='기본 브리핑 카테고리')
            session.add(category)
            session.flush()

        tag = session.scalar(select(Tag).where(Tag.slug == 'aerospace'))
        if tag is None:
            tag = Tag(name='항공우주', slug='aerospace')
            session.add(tag)
            session.flush()

        newsletter = session.scalar(select(Newsletter).where(Newsletter.source_identifier == 'markdown-sample-welcome'))
        if newsletter is None:
            newsletter = Newsletter(
                title='AeroOne 샘플 Markdown',
                slug='aeroone-sample-markdown',
                description='Markdown 렌더링 검증용 샘플 문서',
                summary='샘플 Markdown summary',
                source_type=SourceType.MARKDOWN,
                source_identifier='markdown-sample-welcome',
                markdown_file_path='markdown/newsletters/sample-welcome.md',
                published_at=datetime(2026, 3, 27, tzinfo=UTC),
                is_active=True,
                category=category,
            )
            newsletter.tags.append(tag)
            newsletter.assets.append(
                NewsletterAsset(
                    asset_type=AssetType.MARKDOWN,
                    file_path='markdown/newsletters/sample-welcome.md',
                    is_primary=True,
                )
            )
            session.add(newsletter)

        sync_result = _sync_external_newsletters(settings, session)

    if sync_result is None:
        print('seed complete (external sync skipped: import root not found)')
    else:
        print(
            'seed complete '
            f'(external sync: created={sync_result.created}, updated={sync_result.updated}, '
            f'deactivated={sync_result.deactivated}, skipped={sync_result.skipped}, issues={sync_result.issues})'
        )


if __name__ == '__main__':
    main()
