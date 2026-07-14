"""보고서 HTML 렌더 — 경량 경로(BUILD_CONTRACT §2.5).

MVP 는 벤더 ``build_report.py`` 를 subprocess 로 호출했지만, 이번 빌드는 신규 의존성/
벤더 자산을 도입하지 않는다. 대신 AeroOne 이 이미 쓰는 ``markdown`` 패키지로 본문을
변환하고, 뉴스레터 ``sanitize_html_fragment`` 로 정제한 뒤, 인라인 CSS 만 가진 자립형
HTML 문서로 감싼다. 외부 CDN/폰트/스크립트가 전혀 없어 폐쇄망에서 그대로 열린다.
"""

from __future__ import annotations

import html as html_lib

import markdown as markdown_lib

from app.modules.newsletter.services.html_render_service import sanitize_html_fragment

# 인라인 스타일만 사용한다(외부 폰트/CDN 0). 시스템 폰트 스택으로 폐쇄망 마찰을 없앤다.
_REPORT_CSS = """
:root { color-scheme: light dark; }
* { box-sizing: border-box; }
body { margin: 0; padding: 2.5rem 1.25rem; background: #f4f5f7; color: #1b2733;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Malgun Gothic', sans-serif;
  line-height: 1.7; }
main { max-width: 860px; margin: 0 auto; background: #ffffff; border-radius: 14px;
  padding: 2.5rem 2.75rem; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
.report-eyebrow { font-size: 0.72rem; letter-spacing: 0.18em; text-transform: uppercase;
  color: #6b7684; margin: 0 0 0.5rem; }
.report-title { font-size: 1.9rem; margin: 0 0 0.35rem; line-height: 1.25; }
.report-subtitle { font-size: 1.05rem; color: #45525f; margin: 0 0 1rem; }
.report-meta { font-size: 0.8rem; color: #6b7684; margin: 0 0 1.75rem;
  border-bottom: 1px solid #e2e6ea; padding-bottom: 1rem; }
.report-body h1, .report-body h2, .report-body h3 { line-height: 1.3; margin: 1.8rem 0 0.7rem; }
.report-body h2 { border-bottom: 1px solid #e2e6ea; padding-bottom: 0.3rem; }
.report-body img { max-width: 100%; height: auto; border-radius: 8px; }
.report-body pre { background: #0f172a; color: #e2e8f0; padding: 1rem; border-radius: 8px;
  overflow-x: auto; font-size: 0.85rem; }
.report-body code { font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', monospace; }
.report-body table { border-collapse: collapse; width: 100%; margin: 1rem 0; }
.report-body th, .report-body td { border: 1px solid #d7dde2; padding: 0.5rem 0.7rem; text-align: left; }
.report-body blockquote { border-left: 3px solid #94a3b8; margin: 1rem 0; padding: 0.2rem 1rem; color: #475569; }
@media (prefers-color-scheme: dark) {
  body { background: #10161d; color: #e6edf3; }
  main { background: #161d26; box-shadow: none; }
  .report-subtitle { color: #adb9c4; }
  .report-body h2 { border-color: #24303c; }
  .report-body th, .report-body td { border-color: #2a3742; }
}
""".strip()


def markdown_to_body(markdown_text: str) -> str:
    """Markdown 을 sanitize 된 HTML 본문 조각으로 변환한다(뉴스레터와 동일 확장)."""

    rendered = markdown_lib.markdown(
        markdown_text,
        extensions=['tables', 'fenced_code', 'sane_lists', 'toc'],
    )
    return sanitize_html_fragment(rendered)


def _meta_line(version: str, tags: str) -> str:
    """버전/태그 메타 문자열을 만든다(둘 다 비면 빈 문자열)."""

    parts: list[str] = []
    if version.strip():
        parts.append(f'버전 {version.strip()}')
    if tags.strip():
        parts.append(tags.strip())
    return ' · '.join(parts)


def render_report_html(
    *,
    body_html: str,
    title: str,
    subtitle: str = '',
    version: str = '',
    tags: str = '',
    eyebrow: str = 'AEROONE REPORT',
) -> str:
    """정제된 본문을 인라인 CSS 자립형 HTML 문서로 감싼다(외부 리소스 0)."""

    safe_title = html_lib.escape(title)
    subtitle_html = f'<p class="report-subtitle">{html_lib.escape(subtitle)}</p>' if subtitle.strip() else ''
    meta = _meta_line(version, tags)
    meta_html = f'<p class="report-meta">{html_lib.escape(meta)}</p>' if meta else ''
    return (
        '<!doctype html>\n'
        '<html lang="ko">\n<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f'<title>{safe_title}</title>\n'
        f'<style>{_REPORT_CSS}</style>\n'
        '</head>\n<body>\n<main>\n'
        f'<p class="report-eyebrow">{html_lib.escape(eyebrow)}</p>\n'
        f'<h1 class="report-title">{safe_title}</h1>\n'
        f'{subtitle_html}\n{meta_html}\n'
        f'<div class="report-body">\n{body_html}\n</div>\n'
        '</main>\n</body>\n</html>\n'
    )
