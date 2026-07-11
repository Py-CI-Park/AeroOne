"""차트 스튜디오(svc02) 도메인 스펙 — MVP ``svc02_chart_studio/schemas.py`` 포팅.

``ChartSpec`` 은 LLM/규칙엔진이 제안하고 pandas 집계가 소비하는 단일 계약이다. 브라우저
ECharts 렌더 결정(BUILD_CONTRACT §2.5)에 맞춰 서버는 이 스펙에서 ECharts option(JSON)만
만들고 SVG/PNG 는 만들지 않는다. 값의 상·하한은 pydantic 이 시스템 경계에서 강제한다.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

# 브라우저 ECharts 로 렌더할 수 있는 차트 유형. 서버는 이 유형만 집계·직렬화한다.
ChartType = Literal['bar', 'line', 'area', 'scatter', 'pie', 'histogram']
Aggregation = Literal['none', 'sum', 'mean', 'count', 'min', 'max']
SortMode = Literal['none', 'x_asc', 'x_desc', 'value_asc', 'value_desc']
Orientation = Literal['vertical', 'horizontal']


class ChartSpec(BaseModel):
    """차트 한 장을 결정하는 스펙. LLM 응답/수동 입력 모두 이 형태로 정규화된다."""

    type: ChartType = 'bar'
    title: str = Field(default='데이터 차트', max_length=200)
    x: str | None = None
    y: list[str] = Field(default_factory=list, max_length=8)
    group: str | None = None
    aggregation: Aggregation = 'sum'
    sort: SortMode = 'none'
    limit: int = Field(default=30, ge=1, le=100)
    orientation: Orientation = 'vertical'
    x_label: str | None = Field(default=None, max_length=100)
    y_label: str | None = Field(default=None, max_length=100)

    @field_validator('y', mode='before')
    @classmethod
    def normalize_y(cls, value):
        """y 는 콤마 문자열/None 도 허용하고 항상 열 이름 리스트로 정규화한다."""

        if value is None:
            return []
        if isinstance(value, str):
            return [item.strip() for item in value.split(',') if item.strip()]
        return value

    def validate_columns(self, columns: list[str]) -> None:
        """참조 열이 실제 데이터 열 안에 있는지, 유형별 필수 축이 있는지 검증한다."""

        allowed = set(columns)
        referenced = [item for item in [self.x, self.group, *self.y] if item]
        missing = sorted(set(referenced) - allowed)
        if missing:
            raise ValueError(f'차트 스펙이 존재하지 않는 열을 참조합니다: {missing}')
        if self.type in {'bar', 'line', 'area', 'pie'} and not self.x:
            raise ValueError(f'{self.type} 차트에는 x 열이 필요합니다')
        if self.type == 'scatter' and (not self.x or len(self.y) != 1):
            raise ValueError('산점도에는 x 와 정확히 하나의 y 열이 필요합니다')
        if self.type == 'histogram' and len(self.y) != 1:
            raise ValueError('히스토그램에는 정확히 하나의 숫자 y 열이 필요합니다')
