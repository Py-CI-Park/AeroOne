from app.modules.newsletter.services.html_render_service import HtmlRenderService
from app.modules.shared.storage.service import StorageService


def test_html_sanitize_removes_scripts_and_relative_src(settings) -> None:
    storage_service = StorageService(settings)
    service = HtmlRenderService(storage_service)

    html = service.render('newsletter_20260206.html')

    assert '<script' not in html
    assert 'src="image.png"' not in html
    assert 'noopener noreferrer' in html
