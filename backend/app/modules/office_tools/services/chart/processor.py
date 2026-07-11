"""차트 집계·직렬화 — MVP ``svc02_chart_studio/processor.py`` 포팅(서버 렌더 제거).

pandas 로 데이터를 스펙에 맞춰 집계(``prepare_chart``)하고, 그 결과를 브라우저 ECharts
option(JSON)으로 직렬화(``echarts_option``)한다. matplotlib SVG/PNG 렌더는 이번 빌드에서
제거했다(BUILD_CONTRACT §2.5) — 미리보기는 프런트 ECharts 가 맡는다. 함수는 유형별
헬퍼로 쪼개 한 함수의 책임과 길이를 좁게 유지한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from .schemas import ChartSpec


@dataclass
class PreparedChart:
    """집계 결과(축 카테고리 + 시리즈)와 처리 중 경고를 담는 불변 전달체."""

    frame: pd.DataFrame
    categories: list[Any]
    series: list[dict[str, Any]]
    warnings: list[str]


def _json_value(value: Any) -> Any:
    """numpy/pandas 스칼라를 JSON 직렬화 가능한 파이썬 기본형으로 낮춘다."""

    if pd.isna(value):
        return None
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def _sort_frame(frame: pd.DataFrame, spec: ChartSpec, value_columns: list[str]) -> pd.DataFrame:
    if spec.sort == 'x_asc' and spec.x:
        return frame.sort_values(spec.x, ascending=True)
    if spec.sort == 'x_desc' and spec.x:
        return frame.sort_values(spec.x, ascending=False)
    if spec.sort in {'value_asc', 'value_desc'} and value_columns:
        return frame.sort_values(value_columns[0], ascending=spec.sort == 'value_asc')
    return frame


def _prepare_histogram(frame: pd.DataFrame, spec: ChartSpec) -> PreparedChart:
    column = spec.y[0]
    numeric = pd.to_numeric(frame[column], errors='coerce').dropna()
    if numeric.empty:
        raise ValueError(f'히스토그램 열에 숫자 값이 없습니다: {column}')
    bins = min(spec.limit, max(5, int(np.sqrt(len(numeric)))))
    counts, edges = np.histogram(numeric, bins=bins)
    labels = [f'{edges[i]:.3g}–{edges[i + 1]:.3g}' for i in range(len(counts))]
    out = pd.DataFrame({'bin': labels, 'count': counts})
    return PreparedChart(out, labels, [{'name': column, 'data': [int(v) for v in counts]}], [])


def _prepare_scatter(frame: pd.DataFrame, spec: ChartSpec) -> PreparedChart:
    x_col, y_col = spec.x, spec.y[0]
    out = frame[[x_col, y_col]].copy()
    out[x_col] = pd.to_numeric(out[x_col], errors='coerce')
    out[y_col] = pd.to_numeric(out[y_col], errors='coerce')
    out = out.dropna().head(spec.limit)
    if out.empty:
        raise ValueError('산점도에 유효한 숫자 쌍이 없습니다')
    points = [[float(x), float(y)] for x, y in out[[x_col, y_col]].to_numpy()]
    return PreparedChart(out, [], [{'name': y_col, 'data': points}], [])


def _aggregate(frame: pd.DataFrame, spec: ChartSpec) -> tuple[pd.DataFrame, list[str], list[str]]:
    """x/그룹/집계 규칙에 따라 집계 프레임과 값 열, 경고를 만든다."""

    x_col = spec.x
    working = frame.copy()
    working[x_col] = working[x_col].where(working[x_col].notna(), '(빈 값)')
    value_columns = list(spec.y)
    warnings: list[str] = []

    if spec.aggregation == 'count' or not value_columns:
        if spec.group:
            grouped = working.groupby([x_col, spec.group], dropna=False).size().reset_index(name='count')
            out = grouped.pivot(index=x_col, columns=spec.group, values='count').fillna(0).reset_index()
            value_columns = [str(c) for c in out.columns if str(c) != x_col]
        else:
            out = working.groupby(x_col, dropna=False).size().reset_index(name='count')
            value_columns = ['count']
    elif spec.group:
        if len(value_columns) != 1:
            warnings.append('group 열을 사용할 때는 첫 번째 y 열만 사용했습니다.')
        y_col = value_columns[0]
        working[y_col] = pd.to_numeric(working[y_col], errors='coerce')
        agg = 'sum' if spec.aggregation == 'none' else spec.aggregation
        grouped = working.groupby([x_col, spec.group], dropna=False)[y_col].agg(agg).reset_index()
        out = grouped.pivot(index=x_col, columns=spec.group, values=y_col).fillna(0).reset_index()
        value_columns = [str(c) for c in out.columns if str(c) != x_col]
    else:
        for column in value_columns:
            working[column] = pd.to_numeric(working[column], errors='coerce')
        if spec.aggregation == 'none':
            out = working[[x_col, *value_columns]].dropna(subset=value_columns, how='all')
        else:
            out = working.groupby(x_col, dropna=False)[value_columns].agg(spec.aggregation).reset_index()
    return out, value_columns, warnings


def prepare_chart(frame: pd.DataFrame, spec: ChartSpec) -> PreparedChart:
    """스펙을 검증하고 유형별로 집계해 카테고리/시리즈를 만든다."""

    spec.validate_columns([str(c) for c in frame.columns])
    if spec.type == 'histogram':
        return _prepare_histogram(frame, spec)
    if spec.type == 'scatter':
        return _prepare_scatter(frame, spec)

    out, value_columns, warnings = _aggregate(frame, spec)
    out.columns = [str(c) for c in out.columns]
    out = _sort_frame(out, spec, value_columns).head(spec.limit)
    if out.empty:
        raise ValueError('차트 집계 결과에 행이 없습니다')
    if spec.type == 'pie' and len(out) > 12:
        warnings.append('파이 차트 항목을 12개로 제한했습니다. 항목이 많으면 막대 차트를 권장합니다.')
        out = out.head(12)

    categories = [_json_value(v) for v in out[spec.x].tolist()]
    series: list[dict[str, Any]] = []
    for column in value_columns:
        data = [_json_value(v) for v in pd.to_numeric(out[column], errors='coerce').fillna(0).tolist()]
        series.append({'name': column, 'data': data})
    return PreparedChart(out, categories, series, warnings)


def _pie_option(spec: ChartSpec, prepared: PreparedChart) -> list[dict[str, Any]]:
    values = prepared.series[0]['data'] if prepared.series else []
    data = [{'name': str(name), 'value': value} for name, value in zip(prepared.categories, values)]
    return [{'type': 'pie', 'radius': ['35%', '65%'], 'data': data}]


def _cartesian_option(spec: ChartSpec, prepared: PreparedChart, base: dict[str, Any]) -> None:
    """bar/line/area/histogram 의 축과 시리즈를 base option 에 채운다."""

    horizontal = spec.orientation == 'horizontal' and spec.type == 'bar'
    category_axis = {'type': 'category', 'data': [str(v) for v in prepared.categories], 'axisLabel': {'interval': 0}}
    value_axis = {'type': 'value'}
    base['xAxis'] = value_axis if horizontal else category_axis
    base['yAxis'] = category_axis if horizontal else value_axis
    series_type = 'bar' if spec.type == 'histogram' else ('line' if spec.type in {'line', 'area'} else 'bar')
    base['series'] = []
    for item in prepared.series:
        series: dict[str, Any] = {'type': series_type, 'name': item['name'], 'data': item['data']}
        if spec.type == 'area':
            series['areaStyle'] = {}
        base['series'].append(series)


def echarts_option(spec: ChartSpec, prepared: PreparedChart) -> dict[str, Any]:
    """PreparedChart 를 브라우저 ECharts option(JSON)으로 직렬화한다."""

    base: dict[str, Any] = {
        'title': {'text': spec.title, 'left': 'center'},
        'tooltip': {'trigger': 'item' if spec.type in {'pie', 'scatter'} else 'axis'},
        'legend': {'top': 32},
        'toolbox': {'feature': {'saveAsImage': {'pixelRatio': 2}}},
        'animation': False,
    }
    if spec.type == 'pie':
        base['series'] = _pie_option(spec, prepared)
    elif spec.type == 'scatter':
        base['xAxis'] = {'type': 'value', 'name': spec.x_label or spec.x}
        base['yAxis'] = {'type': 'value', 'name': spec.y_label or spec.y[0]}
        base['series'] = [{'type': 'scatter', **item, 'symbolSize': 9} for item in prepared.series]
    else:
        _cartesian_option(spec, prepared, base)
    return base
