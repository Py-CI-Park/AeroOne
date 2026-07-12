"""office-tools 샘플 예제 엔드포인트 검증(도구별 여러 종).

각 스튜디오의 '예제'가 쓰는 ``/samples`` 는 로그인 필수이며, 도구별 여러 샘플의
내용(번들 파일) + 폼 프리필 힌트를 돌려준다. key 로 개별 조회하며, 미지원 key 는 404.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_samples_require_login(client: TestClient) -> None:
    assert client.get('/api/v1/office-tools/samples').status_code == 401
    assert client.get('/api/v1/office-tools/samples/diagram-flow').status_code == 401


def test_list_covers_all_tools_with_multiple_samples(csrf_client: TestClient) -> None:
    resp = csrf_client.get('/api/v1/office-tools/samples')
    assert resp.status_code == 200
    body = resp.json()
    # 도구별로 여러 종을 제공한다(다이어그램 4·차트 5·보고서 3 = 12).
    by_tool: dict[str, int] = {}
    for item in body:
        assert item['key'] and item['content'].strip() and isinstance(item['hints'], dict)
        by_tool[item['tool']] = by_tool.get(item['tool'], 0) + 1
    assert by_tool['diagram'] >= 4
    assert by_tool['chart'] >= 5
    assert by_tool['report'] >= 3


def test_chart_samples_cover_every_chart_type(csrf_client: TestClient) -> None:
    body = csrf_client.get('/api/v1/office-tools/samples').json()
    chart_types = {item['hints'].get('chart_type') for item in body if item['tool'] == 'chart'}
    assert {'bar', 'line', 'pie', 'scatter', 'histogram'}.issubset(chart_types)


def test_diagram_samples_cover_every_diagram_type(csrf_client: TestClient) -> None:
    body = csrf_client.get('/api/v1/office-tools/samples').json()
    diagram_types = {item['hints'].get('diagram_type') for item in body if item['tool'] == 'diagram'}
    assert {'flowchart', 'sequence', 'state', 'gantt'}.issubset(diagram_types)


def test_get_pie_sample_by_key(csrf_client: TestClient) -> None:
    resp = csrf_client.get('/api/v1/office-tools/samples/chart-channel-pie')
    assert resp.status_code == 200
    body = resp.json()
    assert body['tool'] == 'chart'
    assert body['filename'].endswith('.csv')
    assert 'channel' in body['content']
    assert body['hints'].get('chart_type') == 'pie'


def test_get_sequence_sample_by_key(csrf_client: TestClient) -> None:
    resp = csrf_client.get('/api/v1/office-tools/samples/diagram-sequence')
    assert resp.status_code == 200
    body = resp.json()
    assert body['hints'].get('diagram_type') == 'sequence'
    assert '->' in body['content']


def test_get_postmortem_report_sample_by_key(csrf_client: TestClient) -> None:
    resp = csrf_client.get('/api/v1/office-tools/samples/report-postmortem')
    assert resp.status_code == 200
    body = resp.json()
    assert body['tool'] == 'report'
    assert body['content'].lstrip().startswith('#')
    # 복합 마크다운: 표 헤더 구분선이 포함된다.
    assert '|' in body['content']


def test_unknown_sample_returns_404(csrf_client: TestClient) -> None:
    assert csrf_client.get('/api/v1/office-tools/samples/nope').status_code == 404
