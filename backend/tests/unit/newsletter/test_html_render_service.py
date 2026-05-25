from app.modules.newsletter.services.html_render_service import HtmlRenderService
from app.modules.shared.storage.service import StorageService


def test_html_render_serves_trusted_local_html_raw(settings) -> None:
    storage_service = StorageService(settings)
    service = HtmlRenderService(storage_service)

    html = service.render('newsletter_20260206.html')

    # 로컬 뉴스레터는 신뢰 콘텐츠라 원본 그대로 서빙한다. JS 렌더 방식 산출물의
    # 본문이 살아있도록 <script> 등을 보존(격리는 프론트 sandbox iframe 담당).
    assert '<script' in html


def test_sanitize_html_still_strips_scripts_for_markdown_path(settings) -> None:
    storage_service = StorageService(settings)
    service = HtmlRenderService(storage_service)

    cleaned = service.sanitize_html(
        '<div><script>alert(1)</script>'
        '<a href="https://example.com">link</a>'
        '<img src="image.png"/></div>'
    )

    # Markdown 변환 경로는 신뢰도가 낮아 sanitize_html 을 계속 적용한다.
    assert '<script' not in cleaned
    assert 'src="image.png"' not in cleaned
    assert 'noopener noreferrer' in cleaned
