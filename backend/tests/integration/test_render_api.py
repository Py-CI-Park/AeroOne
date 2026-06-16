from __future__ import annotations

import markdown

from app.modules.newsletter.services.html_render_service import sanitize_html_fragment

ENDPOINT = '/api/v1/render'


def test_render_markdown_returns_table_html(client) -> None:
    text = '# H\n\n| a | b |\n|---|---|\n| 1 | 2 |'
    response = client.post(ENDPOINT, json={'type': 'markdown', 'text': text})

    assert response.status_code == 200
    html = response.json()['html']
    assert '<h1>' in html
    assert '<table>' in html


def test_render_html_strips_dangerous_markup(client) -> None:
    text = '<script>alert(1)</script><p onclick="x">hi</p><iframe></iframe>'
    response = client.post(ENDPOINT, json={'type': 'html', 'text': text})

    assert response.status_code == 200
    html = response.json()['html']
    # script/iframe 는 통째로 제거, on* 핸들러는 삭제, 본문 <p>hi</p> 는 보존.
    assert '<script>' not in html
    assert 'alert(1)' not in html
    assert '<iframe>' not in html
    assert 'onclick' not in html
    assert '<p>hi</p>' in html


def test_render_rejects_extra_path_field(client) -> None:
    # extra='forbid' — 몰래 끼워넣은 file/path 필드는 422 로 거부(경로탈출 표면 차단).
    response = client.post(ENDPOINT, json={'type': 'html', 'text': 'x', 'path': '../secret'})

    assert response.status_code == 422


def test_render_rejects_oversized_text(client) -> None:
    # 1MB 초과 입력은 렌더 DoS 방지를 위해 422.
    response = client.post(ENDPOINT, json={'type': 'markdown', 'text': 'a' * 1_000_001})

    assert response.status_code == 422


def test_render_markdown_matches_pure_pipeline(client) -> None:
    # 계약: 엔드포인트 출력 == markdown.markdown(...) + sanitize_html_fragment(...).
    # 입력은 순수 텍스트뿐이며 파일/스토리지를 읽지 않는다.
    text = '# Title\n\nBody **bold** text.\n\n| a | b |\n|---|---|\n| 1 | 2 |'
    expected = sanitize_html_fragment(
        markdown.markdown(text, extensions=['tables', 'fenced_code', 'sane_lists'])
    )

    response = client.post(ENDPOINT, json={'type': 'markdown', 'text': text})

    assert response.status_code == 200
    assert response.json()['html'] == expected


def test_render_html_matches_pure_pipeline(client) -> None:
    text = '<p onclick="evil()">keep</p><script>nope()</script>'
    expected = sanitize_html_fragment(text)

    response = client.post(ENDPOINT, json={'type': 'html', 'text': text})

    assert response.status_code == 200
    assert response.json()['html'] == expected
