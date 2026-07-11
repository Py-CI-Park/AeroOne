"""office-tools 공통 뼈대 인증/능력 검증.

상위 라우터가 세션 로그인을 강제하므로 대표 엔드포인트(health/capabilities/jobs)는
미로그인 시 401, 로그인 시 통과한다. capabilities 는 base_url 을 노출하지 않는다.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

_VALID_JOB_ID = 'a' * 32  # 정규식 [0-9a-f]{32} 을 만족하지만 존재하지 않는 job.


def test_health_requires_login(client: TestClient) -> None:
    assert client.get('/api/v1/office-tools/health').status_code == 401


def test_capabilities_requires_login(client: TestClient) -> None:
    assert client.get('/api/v1/office-tools/capabilities').status_code == 401


def test_jobs_requires_login(client: TestClient) -> None:
    assert client.get(f'/api/v1/office-tools/jobs/{_VALID_JOB_ID}').status_code == 401


def test_health_ok_when_logged_in(csrf_client: TestClient) -> None:
    resp = csrf_client.get('/api/v1/office-tools/health')
    assert resp.status_code == 200
    body = resp.json()
    assert body['status'] == 'ok'
    assert isinstance(body['service'], str) and body['service']


def test_capabilities_reports_services_and_hides_base_url(csrf_client: TestClient) -> None:
    resp = csrf_client.get('/api/v1/office-tools/capabilities')
    assert resp.status_code == 200
    body = resp.json()
    assert body['services'] == {'report': True, 'chart': True, 'diagram': True}
    # 활성 LLM 연결이 없는 상태 → active False, 규칙기반 폴백 신호.
    assert body['llm']['active'] is False
    assert body['llm']['fallback'] == 'rule-based'
    # base_url/api_key 는 어떤 형태로도 노출되지 않는다.
    assert 'base_url' not in resp.text
    assert 'api_key' not in resp.text


def test_jobs_unknown_id_returns_404_when_logged_in(csrf_client: TestClient) -> None:
    # 로그인 상태에서 존재하지 않는(하지만 형식은 유효한) job → 404(401 아님).
    assert csrf_client.get(f'/api/v1/office-tools/jobs/{_VALID_JOB_ID}').status_code == 404
