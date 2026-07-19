"""문서 양식별 개조식 구조 — 위계 기호 단위 검증(gongmuwon §5.2)."""

from __future__ import annotations

from app.modules.aero_work.document_formats import format_document


def test_onepage_summary_and_bullets() -> None:
    paras = format_document('onepage', '보고', '요약 문장\n항목 하나\n항목 둘')
    assert paras[0] == '보고'
    assert paras[1].startswith('□ 요약')
    assert any(p.strip().startswith('◦') for p in paras)


def test_official_receiver_title_numbering() -> None:
    paras = format_document('official', '협조 요청', '가나다\n라마바')
    assert paras[0].startswith('수신')
    assert any(p.startswith('제목') for p in paras)
    assert '1. 가나다' in paras
    assert paras[-1].endswith('끝.')


def test_full_roman_numerals() -> None:
    paras = format_document('full', '계획', '배경\n목표')
    assert 'Ⅰ. 배경' in paras
    assert 'Ⅱ. 목표' in paras


def test_email_greeting_and_signature() -> None:
    paras = format_document('email', '회신', '본문 내용')
    assert paras[0].startswith('제목:')
    assert '안녕하세요.' in paras
    assert paras[-1].endswith('드림')


def test_freeform_keeps_lines() -> None:
    assert format_document('freeform', 'T', 'a\nb') == ['T', 'a', 'b']


def test_unknown_format_defaults_onepage() -> None:
    paras = format_document('bogus', 'T', 'x')
    assert paras[0] == 'T'
    assert paras[1].startswith('□ 요약')
