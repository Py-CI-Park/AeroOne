"""차트 스튜디오(svc02) 서비스 패키지 — 데이터 → ECharts option.

라우트가 쓰는 공개 진입점만 노출한다. 서버 렌더(SVG/PNG) 없이 pandas 집계 결과를
브라우저 ECharts option 으로 직렬화한다(BUILD_CONTRACT §2.5).
"""

from __future__ import annotations

from .data_loader import dataframe_profile, load_dataframe
from .processor import echarts_option, prepare_chart
from .schemas import ChartSpec
from .service import generate_chart, inspect_data
from .spec_builder import auto_chart_spec, llm_chart_spec

__all__ = [
    'ChartSpec',
    'auto_chart_spec',
    'dataframe_profile',
    'echarts_option',
    'generate_chart',
    'inspect_data',
    'llm_chart_spec',
    'load_dataframe',
    'prepare_chart',
]
