"""office-tools 서버측 콘텐츠 검증 — MVP ``core/security.py`` 에서 포팅.

이번 빌드의 렌더링 결정(BUILD_CONTRACT §2.5)에 따라 서버는 차트/다이어그램 산출물을
렌더하지 않고 소스만 만든다. 다이어그램 스튜디오(svc03)가 쓰는 ``validate_mermaid`` 와,
보고서 스튜디오(svc01)가 이미지 임베드/오프라인 검증에 쓰는 ``sanitize_svg`` /
``validate_offline_html`` 을 이식한다. 셋 다 파이썬 표준 라이브러리(``re`` / ``xml``)만
쓰므로 신규 의존성(``cairosvg``/``bleach``)을 도입하지 않는다. 보고서 본문의 원시 HTML
정제는 뉴스레터 ``sanitize_html_fragment`` 를 재사용하고 여기서는 다루지 않는다.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

# 브라우저 Mermaid 렌더에서 XSS/외부호출로 이어질 수 있는 지시어. 하나라도 있으면 거부.
_FORBIDDEN_MERMAID = (
    r'\bclick\b',      # click 상호작용 → JS 콜백/링크
    r'javascript\s*:',  # javascript: 스킴
    r'<\s*script',      # 인라인 스크립트
    r'<\s*iframe',      # 임베드 프레임
    r'%%\{\s*init',     # init 디렉티브(테마/보안레벨 우회)
)

# 요청 유형별 허용 시작 문법. 소스 첫 유효 줄이 이 접두 중 하나로 시작해야 한다.
_ALLOWED_PREFIXES: dict[str, tuple[str, ...]] = {
    'flowchart': ('flowchart ', 'graph '),
    'sequence': ('sequenceDiagram',),
    'state': ('stateDiagram-v2', 'stateDiagram'),
    'gantt': ('gantt',),
}

_MAX_MERMAID_CHARS = 50_000


def validate_mermaid(source: str, requested_type: str | None = None) -> tuple[str, list[str]]:
    """Mermaid 소스를 정규화·검증한다. 위반 시 ``ValueError``.

    반환은 ``(정규화된 소스, 경고 목록)``. 현재 경고는 비어 있으나, 호출부가
    다른 경고와 합쳐 job.json 에 남길 수 있도록 시그니처를 유지한다.
    """

    cleaned = source.strip().replace('\x00', '')
    if len(cleaned) > _MAX_MERMAID_CHARS:
        raise ValueError(f'Mermaid 소스가 {_MAX_MERMAID_CHARS}자 상한을 초과했습니다')
    for pattern in _FORBIDDEN_MERMAID:
        if re.search(pattern, cleaned, flags=re.I):
            raise ValueError('Mermaid 소스에 금지된 지시어가 포함되어 있습니다')
    first = next(
        (line.strip() for line in cleaned.splitlines() if line.strip() and not line.strip().startswith('%%')),
        '',
    )
    if requested_type and requested_type in _ALLOWED_PREFIXES:
        if not first.startswith(_ALLOWED_PREFIXES[requested_type]):
            raise ValueError(f'Mermaid 소스가 요청 유형과 다릅니다: {requested_type}')
    elif not any(
        first.startswith(prefix)
        for prefixes in _ALLOWED_PREFIXES.values()
        for prefix in prefixes
    ):
        raise ValueError('지원하지 않는 Mermaid 다이어그램 유형입니다')
    return cleaned, []


# --- 보고서 스튜디오(svc01) 검증 ---------------------------------------------------

# SVG 이미지 임베드 시 실행/외부호출로 이어질 수 있는 자식 태그. 발견 시 제거한다.
_FORBIDDEN_SVG_TAGS = {'script', 'foreignObject', 'iframe', 'object', 'embed', 'audio', 'video'}

# 오프라인 순도 검증: 산출 HTML 안의 외부(http/https) 리소스 참조를 경고로 수집한다.
_OFFLINE_CHECKS: tuple[tuple[str, str], ...] = (
    (r"<(?:script|img|iframe|source|video|audio)\b[^>]+(?:src|poster)\s*=\s*['\"]https?://", '외부 리소스 URL이 포함되어 있습니다.'),
    (r"<link\b[^>]+href\s*=\s*['\"]https?://", '외부 스타일시트 URL이 포함되어 있습니다.'),
    (r"@import\s+url\(['\"]?https?://", 'CSS 외부 import가 포함되어 있습니다.'),
)


def _svg_local(tag: str) -> str:
    """네임스페이스 접두(``{ns}tag``)를 제거한 로컬 태그명을 돌려준다."""

    return tag.rsplit('}', 1)[-1]


def sanitize_svg(svg_text: str) -> str:
    """SVG 를 파싱해 실행 태그/이벤트 속성/외부 참조를 제거하고 재직렬화한다.

    DOCTYPE/ENTITY 선언은 XXE 방지를 위해 거부한다. 위반 시 ``ValueError``.
    """

    if len(svg_text) > 5_000_000:
        raise ValueError('SVG 크기가 5 MB 상한을 초과했습니다')
    if re.search(r'<!DOCTYPE|<!ENTITY', svg_text, flags=re.I):
        raise ValueError('DOCTYPE/ENTITY 선언은 허용하지 않습니다')
    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError as exc:
        raise ValueError(f'유효하지 않은 SVG: {exc}') from exc

    for parent in list(root.iter()):
        for child in list(parent):
            if _svg_local(child.tag) in _FORBIDDEN_SVG_TAGS:
                parent.remove(child)
        for key in list(parent.attrib):
            local_key = _svg_local(key).lower()
            value = parent.attrib[key]
            if local_key.startswith('on'):
                del parent.attrib[key]
            elif local_key in {'href', 'xlink:href'} and re.match(
                r'\s*(?:https?://|javascript:|data:text/html)', value, flags=re.I
            ):
                del parent.attrib[key]
            elif 'url(' in value and re.search(r"url\(\s*['\"]?https?://", value, flags=re.I):
                del parent.attrib[key]

    if _svg_local(root.tag) != 'svg':
        raise ValueError('루트 요소가 svg 가 아닙니다')
    return ET.tostring(root, encoding='unicode')


def validate_offline_html(html_text: str) -> list[str]:
    """산출 HTML 이 외부 리소스를 참조하는지 검사해 경고 목록을 돌려준다(폐쇄망 순도)."""

    warnings: list[str] = []
    for pattern, message in _OFFLINE_CHECKS:
        if re.search(pattern, html_text, flags=re.I):
            warnings.append(message)
    return warnings
