"""차트 스펙 제안 — MVP ``svc02_chart_studio/spec_builder.py`` 포팅.

규칙 기반(``auto_chart_spec``)은 열의 dtype/날짜 여부와 목적 문장으로 결정적 스펙을
만든다. LLM 기반(``llm_chart_spec``)은 활성 연결(``OpenAiCompatibleClient.chat``)로
ChartSpec JSON 을 제안받아 파싱·검증한다. 두 경로 모두 실제 데이터 열만 참조하도록
``validate_columns`` 로 시스템 경계에서 막는다. LLM 실패/미설정은 호출부가 규칙 기반으로
폴백한다(경고 첨부).
"""

from __future__ import annotations

import json
import re
from typing import Any

import pandas as pd

from app.modules.ai.openai_client import OpenAiCompatibleClient

from .data_loader import dataframe_profile
from .schemas import ChartSpec

_LLM_SYSTEM_PROMPT = (
    '당신은 데이터 시각화 설계기다. 사용자의 데이터 프로필과 목적을 보고 ChartSpec JSON 하나만 반환한다.\n'
    '허용 type: bar, line, area, scatter, pie, histogram.\n'
    '허용 aggregation: none, sum, mean, count, min, max.\n'
    '허용 sort: none, x_asc, x_desc, value_asc, value_desc.\n'
    '허용 orientation: vertical, horizontal.\n'
    '반드시 실제 columns 목록에 있는 열 이름만 사용한다. 계산 결과나 수치를 추측하지 않는다.\n'
    '스키마: {"type":"bar","title":"...","x":"column or null","y":["column"],"group":null,'
    '"aggregation":"sum","sort":"none","limit":30,"orientation":"vertical","x_label":null,"y_label":null}.\n'
    'raw reasoning 은 반환하지 않는다.'
)


def _prompt_type(prompt: str) -> str | None:
    """목적 문장의 키워드로 선호 차트 유형을 추정한다(없으면 None)."""

    lower = prompt.lower()
    terms = {
        'scatter': ['scatter', '산점도', '상관'],
        'histogram': ['histogram', '히스토그램', '분포'],
        'pie': ['pie', '파이', '도넛', '비중', '구성비'],
        'line': ['line', '선형', '추이', '시계열', 'trend'],
        'area': ['area', '영역'],
        'bar': ['bar', '막대', '순위', '비교'],
    }
    for chart_type, keywords in terms.items():
        if any(keyword in lower for keyword in keywords):
            return chart_type
    return None


def _column_kinds(frame: pd.DataFrame) -> tuple[list[str], list[str], list[str]]:
    """열을 (숫자, 비숫자, 날짜형) 으로 분류한다."""

    numeric = [str(c) for c in frame.columns if pd.api.types.is_numeric_dtype(frame[c])]
    non_numeric = [str(c) for c in frame.columns if str(c) not in numeric]
    date_like: list[str] = []
    for column in non_numeric:
        sample = frame[column].dropna().astype(str).head(30)
        if not sample.empty:
            parsed = pd.to_datetime(sample, errors='coerce', format='mixed')
            if float(parsed.notna().mean()) >= 0.8:
                date_like.append(column)
    return numeric, non_numeric, date_like


def _default_type(numeric: list[str], non_numeric: list[str], date_like: list[str]) -> str:
    if date_like and numeric:
        return 'line'
    if non_numeric and numeric:
        return 'bar'
    if len(numeric) >= 2:
        return 'scatter'
    if numeric:
        return 'histogram'
    return 'bar'


def auto_chart_spec(frame: pd.DataFrame, prompt: str = '', requested_type: str | None = None) -> ChartSpec:
    """LLM 없이 결정적 규칙으로 ChartSpec 을 만든다(열 유형 + 목적 키워드)."""

    numeric, non_numeric, date_like = _column_kinds(frame)
    chart_type = requested_type or _prompt_type(prompt) or _default_type(numeric, non_numeric, date_like)
    title = prompt.strip()[:120] if prompt.strip() else '데이터 분석 차트'

    if chart_type == 'scatter':
        if len(numeric) < 2:
            raise ValueError('산점도에는 숫자 열이 최소 두 개 필요합니다')
        spec = ChartSpec(type='scatter', title=title, x=numeric[0], y=[numeric[1]], aggregation='none', limit=100)
    elif chart_type == 'histogram':
        if not numeric:
            raise ValueError('히스토그램에는 숫자 열이 필요합니다')
        spec = ChartSpec(type='histogram', title=title, y=[numeric[0]], aggregation='none', limit=30)
    else:
        x = (date_like or non_numeric or [str(frame.columns[0])])[0]
        y = [numeric[0]] if numeric else []
        many = frame[x].nunique(dropna=True) > 12
        spec = ChartSpec(
            type=chart_type,
            title=title,
            x=x,
            y=y,
            aggregation='sum' if numeric else 'count',
            sort='value_desc' if chart_type in {'bar', 'pie'} else 'x_asc',
            limit=20 if chart_type == 'pie' else 30,
            orientation='horizontal' if chart_type == 'bar' and many else 'vertical',
        )
    spec.validate_columns([str(c) for c in frame.columns])
    return spec


def _extract_json(text: str) -> dict[str, Any]:
    """LLM 응답에서 첫 JSON 객체를 파싱한다(코드펜스/잡음 허용)."""

    candidate = text.strip()
    if candidate.startswith('```'):
        candidate = re.sub(r'^```[a-zA-Z0-9]*\s*|\s*```$', '', candidate).strip()
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', candidate, flags=re.S)
        if not match:
            raise ValueError('LLM 응답에서 JSON 객체를 찾지 못했습니다')
        return json.loads(match.group(0))


def llm_chart_spec(
    frame: pd.DataFrame,
    prompt: str,
    client: OpenAiCompatibleClient,
) -> tuple[ChartSpec, dict[str, Any]]:
    """활성 LLM 연결로 ChartSpec 을 제안받아 파싱·검증한다. 실패 시 예외 → 라우트가 폴백."""

    profile = dataframe_profile(frame, sample_rows=6)
    user = (
        '사용자 목적:\n'
        + (prompt or '데이터를 가장 명확하게 설명하는 차트')
        + '\n\n데이터 프로필:\n'
        + json.dumps(profile, ensure_ascii=False, indent=2)
    )
    content = client.chat(
        [
            {'role': 'system', 'content': _LLM_SYSTEM_PROMPT},
            {'role': 'user', 'content': user},
        ],
        max_tokens=1800,
    )
    payload = _extract_json(content)
    spec = ChartSpec.model_validate(payload)
    spec.validate_columns([str(c) for c in frame.columns])
    return spec, {'model': client.model}
