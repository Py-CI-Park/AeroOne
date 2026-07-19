"""문서 양식(종이) 미리보기 HTML 렌더 — 양식별 위계 마커·sanitize 단위 검증(gongmuwon §5.3)."""

from __future__ import annotations

import pytest

from app.modules.aero_work.document_preview import UnknownFormat, render_preview_html


def test_official_has_letterhead_receiver_and_approval_line() -> None:
    html = render_preview_html('official', '협조 요청', ['자료 제출 협조', '기한 엄수'])
    assert 'OOO 기관' in html
    assert '수신' in html
    assert '제목' in html
    assert '1. 자료 제출 협조' in html
    assert '끝.' in html
    assert '담당' in html and '검토' in html and '결재' in html  # 결재선


def test_onepage_centers_title_and_uses_numbered_hierarchy() -> None:
    html = render_preview_html('onepage', '보고', ['핵심 요약', '세부 항목 하나', '세부 항목 둘'])
    assert '<h1' in html and 'text-align:center' in html
    assert '1. 핵심 요약' in html
    assert '가. 세부 항목 하나' in html
    assert '나. 세부 항목 둘' in html


def test_full_report_uses_roman_chapter_headers() -> None:
    html = render_preview_html('full', '계획', ['추진 배경', '세부 계획'])
    assert 'Ⅰ. 추진 배경' in html
    assert 'Ⅱ. 세부 계획' in html


def test_email_has_recipient_subject_table_and_signature() -> None:
    html = render_preview_html('email', '회신', ['본문 내용입니다'])
    assert '수신' in html
    assert '<table' in html
    assert '제목' in html and '회신' in html
    assert '안녕하세요.' in html
    assert '드림' in html


def test_freeform_keeps_title_and_paragraphs_without_hierarchy_markers() -> None:
    html = render_preview_html('freeform', '메모', ['첫 줄', '둘째 줄'])
    assert '메모' in html
    assert '첫 줄' in html and '둘째 줄' in html
    assert '□' not in html and 'Ⅰ.' not in html


def test_user_text_is_escaped_not_injected_as_html() -> None:
    html = render_preview_html('onepage', '<script>alert(1)</script>', ['<img src=x onerror=alert(2)>'])
    assert '<script>' not in html
    assert '&lt;script&gt;' in html
    assert '<img' not in html
    assert '&lt;img' in html


def test_no_external_resources_or_script_tags() -> None:
    html = render_preview_html('official', '보통', ['본문'])
    assert '<script' not in html
    assert 'http://' not in html and 'https://' not in html
    assert 'src=' not in html


def test_unknown_format_raises() -> None:
    with pytest.raises(UnknownFormat):
        render_preview_html('bogus', 't', ['x'])
