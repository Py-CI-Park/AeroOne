from app.modules.newsletter.models.newsletter import AssetType
from app.modules.newsletter.repositories.newsletter_repository import NewsletterRepository
from app.modules.newsletter.services.newsletter_import_service import NewsletterImportService


def test_sync_creates_newsletter_with_assets(app, settings) -> None:
    with app.state.db.session() as session:
        service = NewsletterImportService(session, settings.import_root)
        result = service.sync()
        newsletter = NewsletterRepository(session).get_by_source_identifier('20260206')

    assert result.created == 1
    assert result.updated == 0
    assert newsletter is not None
    assert newsletter.source_type.value == 'html'
    assert {asset.asset_type for asset in newsletter.assets} == {AssetType.HTML, AssetType.PDF}
