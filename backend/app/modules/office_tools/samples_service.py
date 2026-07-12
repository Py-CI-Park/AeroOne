"""office-tools 샘플 예제 제공 — 각 스튜디오의 즉시 체험용 샘플 데이터(도구별 여러 종).

``samples/`` 디렉터리에 실제 샘플 파일을 번들로 두고, 이 모듈이 도구별 여러 예제의
내용과 폼 프리필 힌트를 함께 돌려준다. 프런트는 '예제' 칩 목록으로 보여 주고, 사용자가
고르면 폼을 채워 바로 실행할 수 있게 한다.

- 다이어그램: 플로우 / 시퀀스 / 상태 / 간트 / 로드맵 / 주문 결제 시퀀스(복합)
- 차트: 막대 / 선 / 파이 / 산점 / 히스토그램 + 누적막대·그룹막대·다계열선(manual_spec 결정적 렌더)
- 보고서: 매출 보고 / 장애 사후분석 / 주간 업무보고 / 경영 대시보드(복합)

번들 파일만 읽으므로 사용자 입력 경로가 개입하지 않는다(경로 탈출 표면 없음).
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

SampleTool = Literal['report', 'chart', 'diagram']

_SAMPLES_DIR = Path(__file__).resolve().parent / 'samples'

# key -> (tool, 파일명, media_type, 칩 라벨, 설명, 폼 프리필 힌트)
_SAMPLES: dict[str, dict[str, object]] = {
    # ---- 다이어그램 ----
    'diagram-flow': {
        'tool': 'diagram',
        'filename': 'sample_flow.txt',
        'media_type': 'text/plain',
        'title': '처리 흐름(플로우)',
        'description': '접속부터 산출물 다운로드까지의 단계 흐름.',
        'hints': {'diagram_type': 'flowchart', 'title': '방문자 처리 흐름', 'ai_assist': True},
    },
    'diagram-sequence': {
        'tool': 'diagram',
        'filename': 'sample_diagram_sequence.txt',
        'media_type': 'text/plain',
        'title': '로그인 시퀀스',
        'description': '사용자·웹서버·인증서버·DB 간 메시지 흐름.',
        'hints': {'diagram_type': 'sequence', 'title': '로그인 시퀀스', 'ai_assist': True},
    },
    'diagram-state': {
        'tool': 'diagram',
        'filename': 'sample_diagram_state.txt',
        'media_type': 'text/plain',
        'title': '상태 전이',
        'description': '접수부터 완료까지의 승인 상태 전이.',
        'hints': {'diagram_type': 'state', 'title': '승인 상태 전이', 'ai_assist': True},
    },
    'diagram-gantt': {
        'tool': 'diagram',
        'filename': 'sample_diagram_gantt.txt',
        'media_type': 'text/plain',
        'title': '프로젝트 간트',
        'description': '요구 분석~배포까지의 일정(업무 | 시작일 | 기간).',
        'hints': {'diagram_type': 'gantt', 'title': '프로젝트 일정', 'ai_assist': True},
    },
    'diagram-roadmap': {
        'tool': 'diagram',
        'filename': 'sample_diagram_roadmap.txt',
        'media_type': 'text/plain',
        'title': '제품 로드맵(간트)',
        'description': '기획~정식 출시까지 반년 로드맵 타임라인.',
        'hints': {'diagram_type': 'gantt', 'title': '제품 로드맵', 'ai_assist': True},
    },
    'diagram-checkout': {
        'tool': 'diagram',
        'filename': 'sample_diagram_checkout.txt',
        'media_type': 'text/plain',
        'title': '주문 결제 시퀀스(복합)',
        'description': '고객·웹앱·재고·결제·카드사·DB·알림 7주체의 주문 결제 흐름.',
        'hints': {'diagram_type': 'sequence', 'title': '주문 결제 시퀀스', 'ai_assist': True},
    },
    # ---- 차트 ----
    'chart-region-bar': {
        'tool': 'chart',
        'filename': 'sample_metrics.csv',
        'media_type': 'text/csv',
        'title': '지역 매출(막대)',
        'description': '지역·월별 매출/주문 표본 → 지역별 막대.',
        'hints': {'prompt': '지역별 매출을 크기순으로 비교', 'chart_type': 'bar', 'ai_assist': True},
    },
    'chart-visitors-line': {
        'tool': 'chart',
        'filename': 'sample_chart_visitors.csv',
        'media_type': 'text/csv',
        'title': '월별 추세(선)',
        'description': '12개월 방문자 시계열 → 선형 추세.',
        'hints': {'prompt': '월별 방문자 추세', 'chart_type': 'line', 'ai_assist': True},
    },
    'chart-channel-pie': {
        'tool': 'chart',
        'filename': 'sample_chart_channel.csv',
        'media_type': 'text/csv',
        'title': '채널 비중(파이)',
        'description': '판매 채널별 매출 구성비 → 파이.',
        'hints': {'prompt': '채널별 매출 비중', 'chart_type': 'pie', 'ai_assist': True},
    },
    'chart-adspend-scatter': {
        'tool': 'chart',
        'filename': 'sample_chart_adspend.csv',
        'media_type': 'text/csv',
        'title': '광고비-매출(산점)',
        'description': '광고비와 매출 두 지표의 상관 → 산점도.',
        'hints': {'prompt': '광고비와 매출의 상관', 'chart_type': 'scatter', 'ai_assist': True},
    },
    'chart-latency-hist': {
        'tool': 'chart',
        'filename': 'sample_chart_latency.csv',
        'media_type': 'text/csv',
        'title': '응답시간 분포(히스토그램)',
        'description': '응답시간(ms) 표본 → 분포 히스토그램.',
        'hints': {'prompt': '응답시간 분포', 'chart_type': 'histogram', 'ai_assist': True},
    },
    # ---- 차트(다계열·화려한 예제, manual_spec 로 결정적 렌더) ----
    'chart-region-channel-stacked': {
        'tool': 'chart',
        'filename': 'sample_chart_region_channel.csv',
        'media_type': 'text/csv',
        'title': '지역×채널 누적막대(스택)',
        'description': '지역별 채널 매출을 누적 막대로 쌓아 구성비까지 한눈에.',
        'hints': {
            'manual_spec': {
                'type': 'bar', 'title': '지역별 채널 매출 구성(누적)',
                'x': 'region', 'y': ['revenue'], 'group': 'channel',
                'aggregation': 'sum', 'stacked': True, 'sort': 'none', 'limit': 30,
            },
        },
    },
    'chart-quarter-product-grouped': {
        'tool': 'chart',
        'filename': 'sample_chart_quarter_product.csv',
        'media_type': 'text/csv',
        'title': '분기×제품군 그룹막대',
        'description': '분기별 제품군 매출을 나란한 그룹 막대로 비교.',
        'hints': {
            'manual_spec': {
                'type': 'bar', 'title': '분기별 제품군 매출(그룹)',
                'x': 'quarter', 'y': ['sales'], 'group': 'product',
                'aggregation': 'sum', 'stacked': False, 'sort': 'none', 'limit': 30,
            },
        },
    },
    'chart-product-multiline': {
        'tool': 'chart',
        'filename': 'sample_chart_product_trend.csv',
        'media_type': 'text/csv',
        'title': '제품군 월 추세(다계열 선)',
        'description': '제품군 3종의 월별 추세를 다계열 선으로 겹쳐 비교.',
        'hints': {
            'manual_spec': {
                'type': 'line', 'title': '제품군별 월 추세(다계열)',
                'x': 'month', 'y': ['여객기', '화물기', '부품'],
                'aggregation': 'none', 'sort': 'x_asc', 'limit': 30,
            },
        },
    },
    # ---- 보고서 ----
    'report-sales': {
        'tool': 'report',
        'filename': 'sample_report.md',
        'media_type': 'text/markdown',
        'title': '매출 보고',
        'description': '표와 요약이 있는 지역별 매출 보고.',
        'hints': {'title': '2026년 2월 지역별 매출 보고', 'subtitle': '요약과 지역별 실적', 'ai_mode': 'none'},
    },
    'report-postmortem': {
        'tool': 'report',
        'filename': 'sample_report_postmortem.md',
        'media_type': 'text/markdown',
        'title': '장애 사후분석',
        'description': '표·코드블록·체크리스트가 있는 포스트모템.',
        'hints': {'title': '장애 사후 분석 — 결제 승인 지연', 'subtitle': '원인·영향·재발 방지', 'ai_mode': 'none'},
    },
    'report-weekly': {
        'tool': 'report',
        'filename': 'sample_report_weekly.md',
        'media_type': 'text/markdown',
        'title': '주간 업무보고',
        'description': '완료·진행·계획·지표로 구성한 주간 보고.',
        'hints': {'title': '주간 업무 보고', 'subtitle': '완료·진행·계획', 'ai_mode': 'none'},
    },
    'report-dashboard': {
        'tool': 'report',
        'filename': 'sample_report_dashboard.md',
        'media_type': 'text/markdown',
        'title': '경영 대시보드(복합)',
        'description': 'KPI·채널 표 여러 개·인용·코드·체크리스트가 있는 상반기 대시보드.',
        'hints': {'title': '2026년 상반기 경영 대시보드', 'subtitle': 'KPI·채널·리스크', 'ai_mode': 'none'},
    },
}


def _read(meta: dict[str, object]) -> str:
    return (_SAMPLES_DIR / str(meta['filename'])).read_text(encoding='utf-8')


def _to_payload(key: str, meta: dict[str, object]) -> dict[str, object]:
    return {
        'key': key,
        'tool': meta['tool'],
        'filename': meta['filename'],
        'media_type': meta['media_type'],
        'title': meta['title'],
        'description': meta['description'],
        'content': _read(meta),
        'hints': meta['hints'],
    }


def all_samples() -> list[dict[str, object]]:
    """모든 도구의 모든 샘플(내용·힌트 포함)을 등록 순서대로 돌려준다."""

    return [_to_payload(key, meta) for key, meta in _SAMPLES.items()]


def get_sample(key: str) -> dict[str, object]:
    """key 로 샘플 하나(내용·힌트 포함)를 돌려준다. 미지원 key 는 KeyError."""

    if key not in _SAMPLES:
        raise KeyError(key)
    return _to_payload(key, _SAMPLES[key])
