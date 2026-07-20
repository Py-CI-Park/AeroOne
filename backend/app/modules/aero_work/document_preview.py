"""문서 양식(종이) 미리보기 — 서버측 HTML 근사 렌더러(gongmuwon 사용설명서 §5.3).

실제 HWPX(OWPML) 렌더(WASM 뷰어)는 범위 밖이다 — 여기서는 ``document_formats`` 가 만드는
위계(□/◦, 수신/제목/1./가./끝, Ⅰ./Ⅱ., 이메일 인사/서명)를 화이트리스트 HTML 태그 + inline
style 로 감싸 "종이처럼 보이는" 근사 조각만 만든다. A4 비율 페이지 프레임(흰 배경·그림자)은
프런트(``DocumentPanel``)가 감싸므로, 여기서는 본문 조각(fragment)만 반환한다.

Sanitize 원칙: 사용자 입력(title·paragraphs)은 전부 ``html.escape`` 로 이스케이프해 텍스트로만
삽입한다 — 새 태그는 이 모듈이 만드는 고정 화이트리스트뿐이고, 외부 리소스·``<script>``·
``on*=`` 핸들러는 전혀 쓰지 않는다(전부 inline style, 신규 의존성 0 — 폐쇄망 원칙).
"""

from __future__ import annotations

from html import escape

from app.modules.aero_work.document_formats import FORMATS, format_document

_BASE_FONT = "font-family:'Malgun Gothic','맑은 고딕',sans-serif; color:#111;"


class UnknownFormat(ValueError):
    """지원하지 않는 format_id (스키마 검증이 우선 걸러내지만 방어적으로도 둔다)."""


def _lines(paragraphs: list[str]) -> list[str]:
    return [p.strip() for p in (paragraphs or []) if (p or '').strip()]


def _title_header(title: str) -> str:
    return (
        f'<h1 style="{_BASE_FONT} text-align:center; font-size:20px; '
        f'margin:0 0 20px;">{escape(title)}</h1>'
    )


def _approval_line() -> str:
    """결재선 — 담당/검토/결재 3단 표(빈 칸, 서명은 실제 결재 시스템 몫)."""

    cell = 'border:1px solid #111; padding:6px 20px; text-align:center;'
    return (
        '<table style="margin:32px 0 0 auto; border-collapse:collapse; font-size:12px;">'
        f'<tr><td style="{cell}">담당</td><td style="{cell}">검토</td><td style="{cell}">결재</td></tr>'
        f'<tr><td style="{cell} height:40px;">&nbsp;</td>'
        f'<td style="{cell}">&nbsp;</td><td style="{cell}">&nbsp;</td></tr>'
        '</table>'
    )


def _render_official(title: str, paragraphs: list[str]) -> str:
    """시행문 — 기관명 머리글 + 문서번호/수신자 블록 + 본문(1./2./…) + 결재선."""

    lines = format_document('official', title, '\n'.join(_lines(paragraphs)))
    receiver, subject, *body_lines = lines
    body_lines, closing = body_lines[:-1], body_lines[-1]
    parts = [
        f'<div style="{_BASE_FONT} text-align:center; font-weight:bold; font-size:20px; '
        'border-bottom:2px solid #111; padding-bottom:8px; margin-bottom:12px;">OOO 기관</div>',
        '<div style="text-align:right; font-size:12px; color:#555; margin-bottom:12px;">'
        '문서번호&nbsp;&nbsp;OOO-0000</div>',
        f'<div style="{_BASE_FONT} margin-bottom:6px;">{escape(receiver)}</div>',
        f'<div style="{_BASE_FONT} font-weight:bold; font-size:16px; margin-bottom:16px;">{escape(subject)}</div>',
    ]
    parts.extend(f'<p style="{_BASE_FONT} margin:4px 0;">{escape(line)}</p>' for line in body_lines)
    parts.append(f'<div style="{_BASE_FONT} margin-top:12px;">{escape(closing)}</div>')
    parts.append(_approval_line())
    return ''.join(parts)


def _render_onepage(title: str, paragraphs: list[str]) -> str:
    """1페이지 보고서 — 제목 중앙 + ``format_document('onepage')`` 위계(□ 요약/세부, ◦ 항목)
    그대로 재사용한다(M2 — 이중 위계 로직 제거, 문서 다운로드용 위계와 화면 미리보기 위계가
    갈라지지 않게 한다)."""

    lines = format_document('onepage', title, '\n'.join(_lines(paragraphs)))
    _, *body_lines = lines
    parts = [_title_header(title)]
    for line in body_lines:
        if line.startswith('  ◦ '):
            parts.append(f'<p style="{_BASE_FONT} margin:4px 0 4px 24px;">{escape(line.strip())}</p>')
        else:
            parts.append(f'<p style="{_BASE_FONT} font-weight:bold; margin:6px 0;">{escape(line)}</p>')
    return ''.join(parts)


def _render_full(title: str, paragraphs: list[str]) -> str:
    """풀버전 보고서 — 제목 중앙 + 장 구성 위계(Ⅰ. Ⅱ.)."""

    lines = format_document('full', title, '\n'.join(_lines(paragraphs)))
    _, *chapters = lines
    parts = [_title_header(title)]
    parts.extend(
        f'<p style="{_BASE_FONT} font-weight:bold; margin:10px 0 4px;">{escape(chapter)}</p>'
        for chapter in chapters
    )
    return ''.join(parts)


def _render_email(title: str, paragraphs: list[str]) -> str:
    """이메일 — 수신/제목 헤더 표 + 인사/본문/맺음/서명."""

    body = _lines(paragraphs)
    cell = 'border:1px solid #ddd; padding:6px 10px; font-size:13px;'
    parts = [
        '<table style="width:100%; border-collapse:collapse; margin-bottom:16px;">'
        f'<tr><td style="{cell} width:60px; color:#555;">수신</td>'
        f'<td style="{cell}">수신자 제위</td></tr>'
        f'<tr><td style="{cell} color:#555;">제목</td>'
        f'<td style="{cell} font-weight:bold;">{escape(title)}</td></tr>'
        '</table>',
        f'<p style="{_BASE_FONT} margin:4px 0;">안녕하세요.</p>',
    ]
    parts.extend(f'<p style="{_BASE_FONT} margin:4px 0;">{escape(line)}</p>' for line in body)
    parts.append(f'<p style="{_BASE_FONT} margin:16px 0 0;">감사합니다.<br/>보내는 사람 드림</p>')
    return ''.join(parts)


def _render_freeform(title: str, paragraphs: list[str]) -> str:
    """임의형식 — 제목 + 원문 유지(위계 없음)."""

    parts = [_title_header(title)]
    parts.extend(f'<p style="{_BASE_FONT} margin:4px 0;">{escape(line)}</p>' for line in _lines(paragraphs))
    return ''.join(parts)


_RENDERERS = {
    'official': _render_official,
    'onepage': _render_onepage,
    'full': _render_full,
    'email': _render_email,
    'freeform': _render_freeform,
}


def render_preview_html(format_id: str, title: str, paragraphs: list[str]) -> str:
    """양식별 종이 느낌 HTML 조각을 만든다 — self-contained(inline style, 외부 리소스 0)."""

    if format_id not in FORMATS:
        raise UnknownFormat(f'지원하지 않는 양식입니다: {format_id}')
    title = (title or '무제').strip() or '무제'
    renderer = _RENDERERS[format_id]
    body = renderer(title, paragraphs)
    return f'<div style="{_BASE_FONT} background:#fff; padding:32px;">{body}</div>'
