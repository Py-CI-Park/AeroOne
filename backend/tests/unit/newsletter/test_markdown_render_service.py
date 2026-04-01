from app.modules.newsletter.services.html_render_service import HtmlRenderService
from app.modules.newsletter.services.markdown_render_service import MarkdownRenderService
from app.modules.shared.storage.service import StorageService


def test_markdown_render_returns_html(settings) -> None:
    storage = StorageService(settings)
    html_service = HtmlRenderService(storage)
    markdown_service = MarkdownRenderService(storage, html_service)

    rendered = markdown_service.render('markdown/newsletters/sample-welcome.md')

    assert '<h1>' in rendered
    assert 'Sample markdown body.' in rendered
