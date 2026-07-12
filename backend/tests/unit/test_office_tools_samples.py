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


def test_multiseries_chart_samples_are_registered(csrf_client: TestClient) -> None:
    body = csrf_client.get('/api/v1/office-tools/samples').json()
    by_key = {item['key']: item for item in body}
    # 누적·그룹·다계열선 예제는 완성된 ChartSpec(manual_spec)을 힌트로 갖는다.
    for key in ('chart-region-channel-stacked', 'chart-quarter-product-grouped', 'chart-product-multiline'):
        assert key in by_key, key
        assert isinstance(by_key[key]['hints'].get('manual_spec'), dict)
    assert by_key['chart-region-channel-stacked']['hints']['manual_spec']['stacked'] is True
    # 복합 예제(시퀀스·경영 대시보드)도 등록돼 있다.
    assert 'diagram-checkout' in by_key
    assert 'report-dashboard' in by_key


def test_manual_spec_chart_samples_match_their_data(csrf_client: TestClient) -> None:
    """manual_spec 샘플은 실제 데이터 열과 일치해 집계까지 성공해야 한다(스펙/데이터 드리프트 차단)."""

    from app.modules.office_tools import samples_service
    from app.modules.office_tools.services.chart import load_dataframe, prepare_chart
    from app.modules.office_tools.services.chart.schemas import ChartSpec

    checked = 0
    for sample in samples_service.all_samples():
        hints = sample['hints']
        spec_dict = hints.get('manual_spec') if isinstance(hints, dict) else None
        if not isinstance(spec_dict, dict):
            continue
        frame = load_dataframe(str(sample['filename']), str(sample['content']).encode('utf-8'), 1000)
        prepared = prepare_chart(frame, ChartSpec.model_validate(spec_dict))
        assert len(prepared.series) >= 1
        checked += 1
    assert checked >= 3  # 누적·그룹·다계열선 최소 3종
