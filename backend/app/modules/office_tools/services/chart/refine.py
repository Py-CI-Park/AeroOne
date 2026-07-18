"""차트 스펙 리파인 — 직전 ChartSpec 을 사용자 명령으로 부분 수정한다.

``rule_refine_chart_spec`` 은 결정적 키워드 규칙(유형/방향/정렬/표시 수/누적/제목)으로
직전 스펙을 최소 변경한다. 적용 가능한 변경이 하나도 없으면 직전 스펙을 그대로 유지하고
경고를 남긴다. ``llm_refine_chart_spec`` 은 활성 LLM 연결로 직전 스펙 JSON + 사용자 명령을
주고 패치된 ChartSpec 을 제안받아 ``spec_builder`` 와 같은 방식(``_extract_json``)으로
파싱·검증한다. 두 경로 모두 실제 데이터 열만 참조하도록 ``validate_columns`` 로 막는다.
"""

from __future__ import annotations

import json
import re
from typing import Any

import pandas as pd

from app.modules.ai.openai_client import OpenAiCompatibleClient

from .data_loader import dataframe_profile
from .schemas import ChartSpec
from .spec_builder import _extract_json

_LLM_REFINE_SYSTEM_PROMPT = (
    '당신은 데이터 시각화 설계기다. 기존 ChartSpec 과 사용자의 수정 명령을 보고, '
    '기존 스펙을 사용자 명령대로 최소 변경한 ChartSpec JSON 하나만 반환한다.\n'
    '명령과 무관한 필드는 기존 값을 그대로 유지한다.\n'
    '허용 type: bar, line, area, scatter, pie, histogram.\n'
    '허용 aggregation: none, sum, mean, count, min, max.\n'
    '허용 sort: none, x_asc, x_desc, value_asc, value_desc.\n'
    '허용 orientation: vertical, horizontal.\n'
    '반드시 실제 columns 목록에 있는 열 이름만 사용한다. 계산 결과나 수치를 추측하지 않는다.\n'
    '스키마: {"type":"bar","title":"...","x":"column or null","y":["column"],"group":null,'
    '"aggregation":"sum","sort":"none","limit":30,"orientation":"vertical","stacked":false,"x_label":null,"y_label":null}.\n'
    'raw reasoning 은 반환하지 않는다.'
)

_TYPE_KEYWORDS: dict[str, list[str]] = {
    'histogram': ['히스토그램', 'histogram', '분포'],
    'scatter': ['산점도', 'scatter'],
    'pie': ['파이', 'pie', '비중'],
    'area': ['영역', 'area'],
    # 단독 '선'/'라인' 은 '우선'·'온라인' 등과 오탐하므로 복합어만 허용한다.
    'line': ['선형', '선 그래프', '선그래프', '꺾은선', '라인 차트', '라인차트', '라인으로', 'line', '추이', '시계열'],
    'bar': ['막대', 'bar'],
}

_ORIENTATION_KEYWORDS: dict[str, list[str]] = {
    'horizontal': ['가로', 'horizontal'],
    'vertical': ['세로', 'vertical'],
}

_SORT_NONE_KEYWORDS = ['정렬 없애', '정렬없애', '정렬 해제', '정렬해제']
_SORT_VALUE_DESC_KEYWORDS = ['값 내림', '큰 순', '크기순', '내림차순']
_SORT_VALUE_ASC_KEYWORDS = ['값 오름', '작은 순', '오름차순']
_SORT_X_DESC_KEYWORDS = ['역순']
_SORT_X_ASC_KEYWORDS = ['이름순', '이름 순', '가나다', 'x 순', 'x순']

_STACKED_OFF_KEYWORDS = ['누적 해제', '누적해제', '스택 해제', '스택해제', '누적 풀', '누적을 풀', '스택 풀']
_STACKED_ON_KEYWORDS = ['누적', '스택', 'stacked']

_LIMIT_PATTERNS = [
    re.compile(r'상위\s*(\d+)'),
    re.compile(r'(\d+)\s*개만'),
    re.compile(r'top\s*(\d+)', re.IGNORECASE),
]

_TITLE_PATTERN = re.compile(r'제목을\s*(.+?)\s*(?:으로|로)\b')


def _match_any(lower_prompt: str, keywords: list[str]) -> bool:
    return any(keyword in lower_prompt for keyword in keywords)


def _detect_type(lower_prompt: str) -> str | None:
    for chart_type, keywords in _TYPE_KEYWORDS.items():
        if _match_any(lower_prompt, keywords):
            return chart_type
    return None


def _detect_orientation(lower_prompt: str) -> str | None:
    for orientation, keywords in _ORIENTATION_KEYWORDS.items():
        if _match_any(lower_prompt, keywords):
            return orientation
    return None


def _detect_sort(lower_prompt: str) -> str | None:
    if _match_any(lower_prompt, _SORT_NONE_KEYWORDS):
        return 'none'
    if _match_any(lower_prompt, _SORT_VALUE_DESC_KEYWORDS):
        return 'value_desc'
    if _match_any(lower_prompt, _SORT_VALUE_ASC_KEYWORDS):
        return 'value_asc'
    if _match_any(lower_prompt, _SORT_X_DESC_KEYWORDS):
        return 'x_desc'
    if _match_any(lower_prompt, _SORT_X_ASC_KEYWORDS):
        return 'x_asc'
    return None


def _detect_limit(lower_prompt: str) -> int | None:
    for pattern in _LIMIT_PATTERNS:
        match = pattern.search(lower_prompt)
        if match:
            value = int(match.group(1))
            return max(1, min(100, value))
    return None


def _detect_stacked(lower_prompt: str) -> bool | None:
    if _match_any(lower_prompt, _STACKED_OFF_KEYWORDS):
        return False
    if _match_any(lower_prompt, _STACKED_ON_KEYWORDS):
        return True
    return None


def _detect_title(prompt: str) -> str | None:
    match = _TITLE_PATTERN.search(prompt)
    if match:
        title = match.group(1).strip()
        if title:
            return title[:200]
    return None


def rule_refine_chart_spec(previous: ChartSpec, prompt: str) -> tuple[ChartSpec, list[str]]:
    """결정적 키워드 규칙으로 직전 ChartSpec 을 최소 변경한다. (스펙, 경고) 반환."""

    lower_prompt = prompt.lower()
    patch: dict[str, Any] = {}

    # '온라인(으로)' 의 '라인으로' 부분 문자열 오탐을 막기 위해 유형 감지 전에 마스킹한다.
    chart_type = _detect_type(lower_prompt.replace('온라인', ''))
    if chart_type:
        patch['type'] = chart_type

    orientation = _detect_orientation(lower_prompt)
    if orientation:
        patch['orientation'] = orientation

    sort_mode = _detect_sort(lower_prompt)
    if sort_mode:
        patch['sort'] = sort_mode

    limit = _detect_limit(lower_prompt)
    if limit is not None:
        patch['limit'] = limit

    stacked = _detect_stacked(lower_prompt)
    if stacked is not None:
        patch['stacked'] = stacked

    title = _detect_title(prompt)
    if title:
        patch['title'] = title

    if not patch:
        return previous.model_copy(deep=True), ['요청에서 적용할 수 있는 차트 변경을 찾지 못했습니다. 직전 차트 설정을 그대로 사용했습니다.']

    refined = previous.model_copy(update=patch, deep=True)
    return refined, []


def llm_refine_chart_spec(
    frame: pd.DataFrame,
    previous: ChartSpec,
    prompt: str,
    client: OpenAiCompatibleClient,
) -> tuple[ChartSpec, dict[str, Any]]:
    """활성 LLM 연결로 직전 스펙을 사용자 명령대로 패치받아 파싱·검증한다. 실패 시 예외 → 호출부가 규칙 기반으로 폴백."""

    profile = dataframe_profile(frame, sample_rows=6)
    user = (
        '기존 ChartSpec:\n'
        + previous.model_dump_json()
        + '\n\n사용자 수정 명령:\n'
        + (prompt or '기존 스펙을 유지')
        + '\n\n데이터 프로필:\n'
        + json.dumps(profile, ensure_ascii=False, indent=2)
    )
    content = client.chat(
        [
            {'role': 'system', 'content': _LLM_REFINE_SYSTEM_PROMPT},
            {'role': 'user', 'content': user},
        ],
        max_tokens=1800,
    )
    payload = _extract_json(content)
    spec = ChartSpec.model_validate(payload)
    spec.validate_columns([str(c) for c in frame.columns])
    return spec, {'model': client.model}
