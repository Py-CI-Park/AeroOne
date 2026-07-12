"""office-tools 공통 응답 스키마.

여기에는 공통 뼈대(health/capabilities)의 응답 모델과 각 도구의 요청/응답 스키마를
둔다. 지금은 다이어그램 스튜디오(svc03)의 생성 요청/스펙/응답이 채워져 있고,
보고서/차트 스키마는 각 도구 구현 단계에서 추가한다.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

# 다이어그램 유형(브라우저 Mermaid 렌더 대상). 서버는 소스만 만들고 검증한다.
DiagramType = Literal['flowchart', 'sequence', 'state', 'gantt']

# 서버측 입력 상한(BUILD_CONTRACT §2.4 "서버 검증"). 프런트 zod 와 값이 일치해야 한다.
MAX_DESCRIPTION_CHARS = 30_000
MAX_TITLE_CHARS = 200

# 보고서 스튜디오(svc01) 입력 상한/화이트리스트. 라우트가 이 값을 강제한다.
ReportAiMode = Literal['none', 'polish', 'executive']
MAX_REPORT_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_REPORT_MARKDOWN_CHARS = 200_000
REPORT_MARKDOWN_SUFFIXES = ('.md', '.markdown', '.txt')

# 차트 스튜디오(svc02) 입력 상한/화이트리스트. capabilities 의 limits 값과 일치한다.
ChartType = Literal['bar', 'line', 'area', 'scatter', 'pie', 'histogram']
MAX_CHART_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_CHART_DATA_ROWS = 100_000
CHART_DATA_SUFFIXES = ('.csv', '.xlsx', '.xlsm', '.json')


class OfficeSampleResponse(BaseModel):
    """각 스튜디오의 '예제 불러오기'용 샘플 데이터 + 폼 프리필 힌트."""

    key: str
    tool: Literal['report', 'chart', 'diagram']
    filename: str
    media_type: str
    title: str
    description: str
    content: str
    hints: dict[str, Any] = Field(default_factory=dict)


class OfficeHealth(BaseModel):
    status: str
    service: str


class OfficeServiceFlags(BaseModel):
    report: bool
    chart: bool
    diagram: bool


class OfficeLlmCapability(BaseModel):
    active: bool
    default_model: str | None
    fallback: str


class OfficeCapabilities(BaseModel):
    services: OfficeServiceFlags
    llm: OfficeLlmCapability
    limits: dict[str, int]


class DiagramGenerateRequest(BaseModel):
    """다이어그램 생성 요청. AI 보조를 켜면 활성 LLM 연결로 Mermaid 를 제안한다."""

    description: str = Field(min_length=1, max_length=MAX_DESCRIPTION_CHARS)
    diagram_type: DiagramType = 'flowchart'
    title: str = Field(default='', max_length=MAX_TITLE_CHARS)
    ai_assist: bool = True


class DiagramSpec(BaseModel):
    """검증을 통과한 Mermaid 소스와 메타. LLM/폴백 양쪽이 같은 형태를 만든다."""

    diagram_type: DiagramType = 'flowchart'
    title: str = Field(default='업무 다이어그램', max_length=MAX_TITLE_CHARS)
    mermaid: str = Field(min_length=3, max_length=50_000)
    warnings: list[str] = Field(default_factory=list, max_length=20)


class DiagramGenerateResponse(BaseModel):
    """생성 결과. job 레코드 요약 + 브라우저가 렌더할 Mermaid 소스."""

    job_id: str
    status: str
    title: str
    diagram_type: DiagramType
    mermaid: str
    warnings: list[str] = Field(default_factory=list)
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    preview_url: str
    bundle_url: str


class ReportGenerateResponse(BaseModel):
    """보고서 생성 결과. job 요약 + 즉시 미리보기용 sanitize HTML 을 함께 돌려준다.

    ``html`` 은 응답 편의(iframe srcdoc)용이며 job.json 에는 저장하지 않는다(중복 회피).
    영구 산출물은 ``aeroone_report.html`` artifact 로 별도 다운로드한다.
    """

    job_id: str
    status: str
    title: str
    ai_mode: ReportAiMode
    llm_used: bool
    html: str
    warnings: list[str] = Field(default_factory=list)
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    preview_url: str
    bundle_url: str


class ChartColumnProfile(BaseModel):
    """inspect 가 돌려주는 열 단위 프로필(스펙 작성 힌트)."""

    name: str
    dtype: str
    non_null: int
    null: int
    unique: int
    numeric: bool
    datetime: bool


class ChartInspectResponse(BaseModel):
    """데이터 프로필 — 행/열 수 + 열별 요약 + 앞부분 샘플."""

    row_count: int
    column_count: int
    columns: list[ChartColumnProfile] = Field(default_factory=list)
    sample: list[dict[str, Any]] = Field(default_factory=list)


class ChartGenerateResponse(BaseModel):
    """차트 생성 결과. job 요약 + 브라우저가 렌더할 ChartSpec/ECharts option."""

    job_id: str
    status: str
    title: str
    llm_used: bool
    chart_spec: dict[str, Any]
    echarts_option: dict[str, Any]
    warnings: list[str] = Field(default_factory=list)
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    preview_url: str
    bundle_url: str
