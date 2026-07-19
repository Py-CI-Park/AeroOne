"""문서 양식별 개조식 구조 — 자유 본문을 양식(시행문/1페이지/풀버전/이메일/임의형식)의 위계로 정리한다.

gongmuwon 사용설명서 §5.2 의 양식별 위계 기호를 규칙 기반으로 재현한다(LLM 구조 생성은 후속에서
같은 문단 리스트에 얹는다). 반환은 문단 리스트로, ``hwpx_generator.build_hwpx_document`` 가 그대로 조립한다.

  onepage(1페이지)  □ 요약(두괄식) / □ 섹션 / ◦ 항목
  official(시행문)  수신 / 제목 / 1.·가.·1) / 붙임·끝
  full(풀버전)      Ⅰ.·Ⅱ. 장 구성 + 개조식
  email(이메일)     제목 / 인사 / 본문 / 맺음 / 서명
  freeform(임의형식) 제목 + 원문 유지
"""

from __future__ import annotations

FORMATS = ('onepage', 'official', 'full', 'email', 'freeform')
FORMAT_LABELS = {
    'onepage': '1페이지 보고서',
    'official': '시행문',
    'full': '풀버전 보고서',
    'email': '이메일',
    'freeform': '임의형식',
}

_ROMANS = ('Ⅰ', 'Ⅱ', 'Ⅲ', 'Ⅳ', 'Ⅴ', 'Ⅵ', 'Ⅶ', 'Ⅷ', 'Ⅸ', 'Ⅹ')


def _lines(body: str) -> list[str]:
    return [line.strip() for line in (body or '').splitlines() if line.strip()]


def _onepage(title: str, lines: list[str]) -> list[str]:
    out = [title]
    if lines:
        out.append(f'□ 요약: {lines[0]}')
    if len(lines) > 1:
        out.append('□ 세부 내용')
        out.extend(f'  ◦ {line}' for line in lines[1:])
    return out


def _official(title: str, lines: list[str]) -> list[str]:
    out = ['수신  수신자 제위', f'제목  {title}']
    for index, line in enumerate(lines, 1):
        out.append(f'{index}. {line}')
    out.append('붙임  없음.       끝.')
    return out


def _full(title: str, lines: list[str]) -> list[str]:
    out = [title]
    for index, line in enumerate(lines):
        out.append(f'{_ROMANS[index % len(_ROMANS)]}. {line}')
    if not lines:
        out.append('Ⅰ. 추진 배경')
    return out


def _email(title: str, lines: list[str]) -> list[str]:
    out = [f'제목: {title}', '안녕하세요.']
    out.extend(lines)
    out.extend(['감사합니다.', '보내는 사람 드림'])
    return out


def format_document(fmt: str, title: str, body: str) -> list[str]:
    title = (title or '무제').strip() or '무제'
    lines = _lines(body)
    if fmt == 'official':
        return _official(title, lines)
    if fmt == 'full':
        return _full(title, lines)
    if fmt == 'email':
        return _email(title, lines)
    if fmt == 'freeform':
        return [title, *lines]
    return _onepage(title, lines)
