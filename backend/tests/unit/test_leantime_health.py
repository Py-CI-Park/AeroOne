"""Leantime 동거 상태(health) 엔드포인트·프로브 검증.

Leantime 은 별도 스택이라 기동 여부를 TCP 도달성 + 시간 제한 HTTP 프로브 + 앱 신원
식별로 감지한다. 엔드포인트는 로그인 필수이며, 프로브 결과와 무관하게 항상 HTTP 200 을
반환한다. 실제 소켓/HTTP 호출은 ``_tcp_reachable``/``_http_probe`` monkeypatch 로 대체해
환경(설치 여부)과 무관하게 결정적으로 검증한다.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.modules.leantime import service
from app.modules.leantime.service import HttpProbeResult


def test_health_requires_login(client: TestClient) -> None:
    assert client.get('/api/v1/leantime/health').status_code == 401


def _leantime_probe(status_code: int = 200, latency_ms: int = 12) -> HttpProbeResult:
    return HttpProbeResult(
        status_code=status_code,
        header_values=('nginx',),
        body_snippet='<html><head><title>Leantime</title></head></html>',
        latency_ms=latency_ms,
    )


def _foreign_probe(status_code: int = 200, latency_ms: int = 5) -> HttpProbeResult:
    return HttpProbeResult(
        status_code=status_code,
        header_values=('nginx',),
        body_snippet='<html><head><title>Grafana</title></head></html>',
        latency_ms=latency_ms,
    )


def test_health_reports_ready_when_http_identifies_leantime(
    csrf_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(service, '_tcp_reachable', lambda *a, **k: True)
    monkeypatch.setattr(service, '_http_probe', lambda *a, **k: _leantime_probe())
    resp = csrf_client.get('/api/v1/leantime/health')
    assert resp.status_code == 200
    body = resp.json()
    assert body['status'] == 'ready'
    assert body['port'] == 8081
    assert body['probe_target'] == '127.0.0.1:8081'
    assert body['launch_url'] == 'http://127.0.0.1:8081'
    assert body['app_identified'] is True
    assert body['latency_ms'] == 12
    assert body['checked_at']
    assert body['detail']


def test_health_reports_ready_when_auth_gated_but_identified(
    csrf_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(service, '_tcp_reachable', lambda *a, **k: True)
    monkeypatch.setattr(service, '_http_probe', lambda *a, **k: _leantime_probe(status_code=401))
    resp = csrf_client.get('/api/v1/leantime/health')
    assert resp.json()['status'] == 'ready'


def test_health_reports_unhealthy_when_http_ok_but_not_identified(
    csrf_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(service, '_tcp_reachable', lambda *a, **k: True)
    monkeypatch.setattr(service, '_http_probe', lambda *a, **k: _foreign_probe())
    resp = csrf_client.get('/api/v1/leantime/health')
    body = resp.json()
    assert body['status'] == 'unhealthy'
    assert body['app_identified'] is False
    assert body['latency_ms'] == 5


def test_health_reports_unhealthy_on_non_auth_4xx(
    csrf_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(service, '_tcp_reachable', lambda *a, **k: True)
    monkeypatch.setattr(service, '_http_probe', lambda *a, **k: _leantime_probe(status_code=404))
    resp = csrf_client.get('/api/v1/leantime/health')
    assert resp.json()['status'] == 'unhealthy'


def test_health_reports_starting_when_tcp_up_but_http_times_out(
    csrf_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(service, '_tcp_reachable', lambda *a, **k: True)
    monkeypatch.setattr(service, '_http_probe', lambda *a, **k: None)
    resp = csrf_client.get('/api/v1/leantime/health')
    body = resp.json()
    assert body['status'] == 'starting'
    assert body['latency_ms'] is None
    assert body['app_identified'] is False


def test_health_reports_absent_when_tcp_refused(
    csrf_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(service, '_tcp_reachable', lambda *a, **k: False)

    def _unexpected_http_probe(*args: object, **kwargs: object) -> None:
        raise AssertionError('http probe must not run when TCP is unreachable')

    monkeypatch.setattr(service, '_http_probe', _unexpected_http_probe)
    resp = csrf_client.get('/api/v1/leantime/health')
    body = resp.json()
    assert body['status'] == 'absent'
    assert body['latency_ms'] is None
    assert body['app_identified'] is False


def test_health_reports_error_when_probe_raises_unexpectedly(
    csrf_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom(*args: object, **kwargs: object) -> bool:
        raise RuntimeError('boom')

    monkeypatch.setattr(service, '_tcp_reachable', _boom)
    resp = csrf_client.get('/api/v1/leantime/health')
    assert resp.status_code == 200
    body = resp.json()
    assert body['status'] == 'error'
    assert body['latency_ms'] is None
    assert body['app_identified'] is False
    assert body['detail']


def test_resolve_target_defaults_to_kit_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv('AEROONE_LEANTIME_HEALTH_URL', raising=False)
    assert service.resolve_target() == ('127.0.0.1', 8081)


def test_resolve_target_honors_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('AEROONE_LEANTIME_HEALTH_URL', 'http://10.10.20.50:9090')
    assert service.resolve_target() == ('10.10.20.50', 9090)


def test_resolve_target_accepts_host_port_without_scheme(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('AEROONE_LEANTIME_HEALTH_URL', '192.168.0.9:8081')
    assert service.resolve_target() == ('192.168.0.9', 8081)


def test_launch_url_is_canonical_by_default(
    csrf_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv('AEROONE_LEANTIME_LAUNCH_URL', raising=False)
    monkeypatch.setenv('AEROONE_LEANTIME_HEALTH_URL', 'http://10.10.20.50:9090')
    monkeypatch.setattr(service, '_tcp_reachable', lambda *a, **k: False)
    resp = csrf_client.get('/api/v1/leantime/health')
    assert resp.json()['launch_url'] == 'http://10.10.20.50:9090'


def test_launch_url_env_override(csrf_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('AEROONE_LEANTIME_HEALTH_URL', 'http://127.0.0.1:8081')
    monkeypatch.setenv('AEROONE_LEANTIME_LAUNCH_URL', 'http://lan-host:8081')
    monkeypatch.setattr(service, '_tcp_reachable', lambda *a, **k: False)
    resp = csrf_client.get('/api/v1/leantime/health')
    assert resp.json()['launch_url'] == 'http://lan-host:8081'

def test_https_health_url_honors_scheme_for_launch_and_probe(
    csrf_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # https 로 설정된 대상은 launch_url 과 프로브 URL 모두 https 스킴을 따라야 한다.
    monkeypatch.delenv('AEROONE_LEANTIME_LAUNCH_URL', raising=False)
    monkeypatch.setenv('AEROONE_LEANTIME_HEALTH_URL', 'https://leantime.internal:8443')
    monkeypatch.setattr(service, '_tcp_reachable', lambda *a, **k: True)
    probed_urls: list[str] = []

    def _capture(url: str, *a, **k):  # noqa: ANN002, ANN003
        probed_urls.append(url)
        return _leantime_probe()

    monkeypatch.setattr(service, '_http_probe', _capture)
    resp = csrf_client.get('/api/v1/leantime/health')
    body = resp.json()
    assert body['status'] == 'ready'
    assert body['launch_url'] == 'https://leantime.internal:8443'
    assert probed_urls == ['https://leantime.internal:8443']


def test_tcp_reachable_returns_false_on_closed_port() -> None:
    # 실제로 열려 있지 않을 사설 포트로 프로브 → 예외 없이 False.
    assert service._tcp_reachable('127.0.0.1', 1, timeout=0.2) is False  # noqa: SLF001


def test_http_probe_returns_none_on_connection_error() -> None:
    # 아무도 듣지 않는 사설 포트 → 연결 실패는 None(부팅 중 취급)으로 낮춰진다.
    assert service._http_probe('http://127.0.0.1:1', timeout=0.2) is None  # noqa: SLF001
