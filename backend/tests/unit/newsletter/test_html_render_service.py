from app.modules.newsletter.services.html_render_service import HtmlRenderService
from app.modules.shared.storage.service import StorageService


def test_render_keeps_scripts_but_strips_external_resources(settings) -> None:
    storage_service = StorageService(settings)
    service = HtmlRenderService(storage_service)

    # 신뢰 로컬 HTML 의 인라인 스크립트(본문 주입 JS)는 보존된다.
    html = service.render('newsletter_20260206.html')
    assert '<script' in html

    # 폐쇄망 순도: 외부로 자동 요청을 내보내는 참조만 차단한다.
    cleaned = service.strip_external_resources(
        '<html><head>'
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?x">'
        '<style>.x{color:red}</style></head>'
        '<body><script>render()</script>'
        '<img src="https://cdn.example.com/a.png">'
        '<img src="data:image/png;base64,AAAA">'
        '<a href="https://example.com">link</a></body></html>'
    )

    assert '<script' in cleaned  # 인라인 스크립트 보존
    assert '<style' in cleaned  # 인라인 스타일 보존
    assert 'fonts.googleapis.com' not in cleaned  # 외부 <link> 제거
    assert 'cdn.example.com' not in cleaned  # 외부 img src 제거
    assert 'data:image/png' in cleaned  # data: 리소스 보존
    assert 'noopener noreferrer' in cleaned  # 외부 <a> 는 보존 + 새 탭


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
