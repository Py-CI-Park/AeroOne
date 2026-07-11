"""office-tools 샘플 예제 제공 — 각 스튜디오의 즉시 체험용 샘플 데이터.

``samples/`` 디렉터리에 실제 샘플 파일(sample_flow.txt / sample_metrics.csv /
sample_report.md)을 번들로 두고, 이 모듈이 그 내용과 폼 프리필 힌트를 함께 돌려준다.
프런트의 '예제 불러오기' 버튼이 이 값을 받아 폼을 채우고 바로 실행할 수 있게 한다.

번들 파일만 읽으므로 사용자 입력 경로가 개입하지 않는다(경로 탈출 표면 없음).
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

SampleTool = Literal['report', 'chart', 'diagram']

_SAMPLES_DIR = Path(__file__).resolve().parent / 'samples'

# tool -> (파일명, media_type, 제목, 설명, 폼 프리필 힌트)
_SAMPLES: dict[SampleTool, dict[str, object]] = {
    'diagram': {
        'filename': 'sample_flow.txt',
        'media_type': 'text/plain',
        'title': '방문자 처리 흐름',
        'description': '접속부터 산출물 다운로드까지의 단계 흐름 예시입니다.',
        'hints': {'diagram_type': 'flowchart', 'title': '방문자 처리 흐름', 'ai_assist': True},
    },
    'chart': {
        'filename': 'sample_metrics.csv',
        'media_type': 'text/csv',
        'title': '지역별 월 매출',
        'description': '지역·월별 매출/주문 수 표본 데이터입니다.',
        'hints': {'prompt': '지역별 2월 매출을 크기순으로 비교', 'chart_type': 'bar', 'ai_assist': True},
    },
    'report': {
        'filename': 'sample_report.md',
        'media_type': 'text/markdown',
        'title': '2026년 2월 지역별 매출 보고',
        'description': '표와 요약이 포함된 Markdown 보고서 예시입니다.',
        'hints': {'title': '2026년 2월 지역별 매출 보고', 'subtitle': '요약과 지역별 실적', 'ai_mode': 'none'},
    },
}


def available_tools() -> list[SampleTool]:
    return list(_SAMPLES.keys())


def get_sample(tool: str) -> dict[str, object]:
    """도구의 샘플 메타 + 내용을 돌려준다. 미지원 도구는 KeyError."""

    if tool not in _SAMPLES:
        raise KeyError(tool)
    meta = _SAMPLES[tool]  # type: ignore[index]
    content = (_SAMPLES_DIR / str(meta['filename'])).read_text(encoding='utf-8')
    return {
        'tool': tool,
        'filename': meta['filename'],
        'media_type': meta['media_type'],
        'title': meta['title'],
        'description': meta['description'],
        'content': content,
        'hints': meta['hints'],
    }
