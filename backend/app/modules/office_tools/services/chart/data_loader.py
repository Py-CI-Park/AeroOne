"""차트 데이터 로더 — MVP ``svc02_chart_studio/data_loader.py`` 포팅.

CSV/XLSX/JSON 을 pandas DataFrame 으로 읽고 프로필(행/열/샘플)을 만든다. xlsx 는
``openpyxl`` 이 있을 때만 지원하며(BUILD_CONTRACT §2.5 선택 의존), 미설치 시 명시적
``ValueError`` 로 안내해 라우트가 422 로 돌려준다. 인코딩은 한국어 환경을 고려해 여러
후보를 순차 시도한다. 무한대(inf)는 JSON 직렬화 안전을 위해 NaN 으로 치환한다.
"""

from __future__ import annotations

import json
from importlib.util import find_spec
from io import BytesIO
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

# 지원 확장자. xlsx/xlsm 은 openpyxl 설치 여부에 따라 런타임에 다시 확인한다.
SUPPORTED_DATA_SUFFIXES = {'.csv', '.xlsx', '.xlsm', '.json'}
_EXCEL_SUFFIXES = {'.xlsx', '.xlsm'}
_CSV_ENCODINGS = ('utf-8-sig', 'utf-8', 'cp949', 'euc-kr')


def _unique_columns(columns) -> list[str]:
    """중복/빈 열 이름을 안정적으로 유일화한다(``col`` → ``col``, ``col_2`` …)."""

    seen: dict[str, int] = {}
    result: list[str] = []
    for raw in columns:
        base = str(raw).strip() or 'column'
        count = seen.get(base, 0)
        seen[base] = count + 1
        result.append(base if count == 0 else f'{base}_{count + 1}')
    return result


def _read_csv(data: bytes) -> pd.DataFrame:
    last_error: Exception | None = None
    for encoding in _CSV_ENCODINGS:
        try:
            return pd.read_csv(BytesIO(data), encoding=encoding)
        except UnicodeDecodeError as exc:
            last_error = exc
    raise ValueError(f'CSV 를 해독하지 못했습니다: {last_error}')


def _read_excel(data: bytes) -> pd.DataFrame:
    if find_spec('openpyxl') is None:
        raise ValueError('xlsx 지원 라이브러리(openpyxl)가 설치되어 있지 않습니다. CSV 나 JSON 을 사용하세요.')
    return pd.read_excel(BytesIO(data), sheet_name=0, engine='openpyxl')


def _read_json(data: bytes) -> pd.DataFrame:
    try:
        parsed: Any = json.loads(data.decode('utf-8-sig'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f'유효하지 않은 JSON 데이터입니다: {exc}') from exc
    if isinstance(parsed, dict):
        parsed = parsed['data'] if isinstance(parsed.get('data'), list) else [parsed]
    if not isinstance(parsed, list):
        raise ValueError('JSON 은 객체 배열이거나 data 배열을 가진 객체여야 합니다')
    return pd.DataFrame(parsed)


def load_dataframe(filename: str, data: bytes, max_rows: int) -> pd.DataFrame:
    """업로드 바이트를 DataFrame 으로 로드하고 행수 상한/빈 파일을 시스템 경계에서 막는다."""

    suffix = Path(filename or '').suffix.lower()
    if suffix not in SUPPORTED_DATA_SUFFIXES:
        raise ValueError(f'지원하지 않는 데이터 확장자입니다: {suffix or "(없음)"}')
    if suffix == '.csv':
        frame = _read_csv(data)
    elif suffix in _EXCEL_SUFFIXES:
        frame = _read_excel(data)
    else:
        frame = _read_json(data)

    if frame.empty:
        raise ValueError('데이터 파일에 행이 없습니다')
    if len(frame) > max_rows:
        raise ValueError(f'데이터 행이 {len(frame):,}개로 상한 {max_rows:,}개를 초과했습니다')
    frame = frame.copy()
    frame.columns = _unique_columns(frame.columns)
    return frame.replace([np.inf, -np.inf], np.nan)


def dataframe_profile(frame: pd.DataFrame, sample_rows: int = 8) -> dict[str, Any]:
    """열별 dtype/결측/유일값과 앞부분 샘플을 JSON-safe 하게 요약한다."""

    columns = []
    for name in frame.columns:
        series = frame[name]
        columns.append(
            {
                'name': str(name),
                'dtype': str(series.dtype),
                'non_null': int(series.notna().sum()),
                'null': int(series.isna().sum()),
                'unique': int(series.nunique(dropna=True)),
                'numeric': bool(pd.api.types.is_numeric_dtype(series)),
                'datetime': bool(pd.api.types.is_datetime64_any_dtype(series)),
            }
        )
    head = frame.head(sample_rows)
    sample = head.where(pd.notna(head), None).to_dict(orient='records')
    # Timestamp/numpy 스칼라를 문자열로 낮춰 JSON 직렬화 안전을 보장한다.
    safe_sample = json.loads(json.dumps(sample, default=str, ensure_ascii=False))
    return {
        'row_count': int(len(frame)),
        'column_count': int(len(frame.columns)),
        'columns': columns,
        'sample': safe_sample,
    }
