"""외부 앱 런처(Open Notebook/OpenWebUI) 헬스 엔드포인트·프로브 검증.

Leantime 과 동일한 로그인 강제 수준을 재사용한다. 신원 마커 검사는 요구하지 않는다 —
HTTP 응답만 오면(2xx~4xx) ready 로 판정한다. 실제 소켓/HTTP 호출은
``_tcp_reachable``/``_http_probe`` monkeypatch 로 대체해 환경과 무관하게 결정적으로 검증한다.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.modules.launchers import service
from app.core.http_probe import HttpProbeResult


def _probe(status_code: int = 200, latency_ms: int = 9) -> HttpProbeResult:
    return HttpProbeResult(
        status_code=status_code,
        header_values=(),
        body_snippet='<html></html>',
        latency_ms=latency_ms,
    )


@pytest.mark.parametrize('kind', ['open_notebook', 'open_webui'])
def test_health_requires_login(client: TestClient, kind: str) -> None:
    assert client.get(f'/api/v1/launchers/{kind}/health').status_code == 401


def test_health_404_for_unregistered_kind(csrf_client: TestClient) -> None:
    resp = csrf_client.get('/api/v1/launchers/grafana/health')
    assert resp.status_code == 404


@pytest.mark.parametrize(('kind', 'port'), [('open_notebook', 8502), ('open_webui', 8080)])
def test_health_reports_absent_when_tcp_refused(
    csrf_client: TestClient, monkeypatch: pytest.MonkeyPatch, kind: str, port: int
) -> None:
    monkeypatch.setattr(service, '_tcp_reachable', lambda *a, **k: False)

    def _unexpected_http_probe(*args: object, **kwargs: object) -> None:
        raise AssertionError('http probe must not run when TCP is unreachable')

    monkeypatch.setattr(service, '_http_probe', _unexpected_http_probe)
    resp = csrf_client.get(f'/api/v1/launchers/{kind}/health')
    assert resp.status_code == 200
    body = resp.json()
    assert body['status'] == 'absent'
    assert body['port'] == port
    assert body['probe_target'] == f'127.0.0.1:{port}'
    assert body['latency_ms'] is None
    assert body['detail']


@pytest.mark.parametrize('kind', ['open_notebook', 'open_webui'])
def test_health_reports_starting_when_tcp_up_but_http_times_out(
    csrf_client: TestClient, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    monkeypatch.setattr(service, '_tcp_reachable', lambda *a, **k: True)
    monkeypatch.setattr(service, '_http_probe', lambda *a, **k: None)
    resp = csrf_client.get(f'/api/v1/launchers/{kind}/health')
    body = resp.json()
    assert body['status'] == 'starting'
    assert body['latency_ms'] is None


@pytest.mark.parametrize('kind', ['open_notebook', 'open_webui'])
def test_health_reports_ready_on_any_http_response_without_identity_marker(
    csrf_client: TestClient, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    monkeypatch.setattr(service, '_tcp_reachable', lambda *a, **k: True)
    monkeypatch.setattr(service, '_http_probe', lambda *a, **k: _probe(status_code=404, latency_ms=7))
    resp = csrf_client.get(f'/api/v1/launchers/{kind}/health')
    body = resp.json()
    assert body['status'] == 'ready'
    assert body['latency_ms'] == 7


def test_health_reports_error_when_probe_raises_unexpectedly(
    csrf_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom(*args: object, **kwargs: object) -> bool:
        raise RuntimeError('boom')

    monkeypatch.setattr(service, '_tcp_reachable', _boom)
    resp = csrf_client.get('/api/v1/launchers/open_webui/health')
    assert resp.status_code == 200
    body = resp.json()
    assert body['status'] == 'error'
    assert body['latency_ms'] is None
    assert body['detail']


def test_resolve_port_honors_settings_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import get_settings, reset_settings_cache

    monkeypatch.setenv('OPEN_WEBUI_PORT', '9999')
    reset_settings_cache()
    try:
        assert service.resolve_port('open_webui') == 9999
    finally:
        monkeypatch.delenv('OPEN_WEBUI_PORT', raising=False)
        reset_settings_cache()


def test_resolve_port_raises_for_unknown_kind() -> None:
    with pytest.raises(service.UnknownLauncherKindError):
        service.resolve_port('grafana')


def test_launcher_status_raises_for_unknown_kind() -> None:
    with pytest.raises(service.UnknownLauncherKindError):
        service.launcher_status('grafana')
