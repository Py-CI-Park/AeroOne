"""office-tools 샘플 예제 엔드포인트 검증.

각 스튜디오의 '예제 불러오기'가 쓰는 ``/samples`` 는 로그인 필수이며, 도구별 샘플
내용(번들 파일)과 폼 프리필 힌트를 돌려준다. 미지원 도구는 404.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_samples_require_login(client: TestClient) -> None:
    assert client.get('/api/v1/office-tools/samples').status_code == 401
    assert client.get('/api/v1/office-tools/samples/diagram').status_code == 401


def test_list_samples_returns_three_tools(csrf_client: TestClient) -> None:
    resp = csrf_client.get('/api/v1/office-tools/samples')
    assert resp.status_code == 200
    body = resp.json()
    tools = {item['tool'] for item in body}
    assert tools == {'report', 'chart', 'diagram'}
    for item in body:
        assert item['content'].strip()
        assert item['filename']
        assert isinstance(item['hints'], dict)


def test_get_chart_sample_has_csv_content(csrf_client: TestClient) -> None:
    resp = csrf_client.get('/api/v1/office-tools/samples/chart')
    assert resp.status_code == 200
    body = resp.json()
    assert body['tool'] == 'chart'
    assert body['filename'].endswith('.csv')
    # CSV 헤더가 실제로 들어 있어야 프런트가 File 로 만들어 업로드할 수 있다.
    assert 'region' in body['content']
    assert body['hints'].get('chart_type') == 'bar'


def test_get_diagram_sample_has_arrow_flow(csrf_client: TestClient) -> None:
    resp = csrf_client.get('/api/v1/office-tools/samples/diagram')
    assert resp.status_code == 200
    body = resp.json()
    assert body['tool'] == 'diagram'
    assert '->' in body['content']
    assert body['hints'].get('diagram_type') == 'flowchart'


def test_get_report_sample_is_markdown(csrf_client: TestClient) -> None:
    resp = csrf_client.get('/api/v1/office-tools/samples/report')
    assert resp.status_code == 200
    body = resp.json()
    assert body['tool'] == 'report'
    assert body['filename'].endswith('.md')
    assert body['content'].lstrip().startswith('#')


def test_unknown_sample_returns_404(csrf_client: TestClient) -> None:
    assert csrf_client.get('/api/v1/office-tools/samples/unknown').status_code == 404
