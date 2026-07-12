"""Leantime 동거 상태(health) 엔드포인트·프로브 검증.

Leantime 은 별도 스택이라 기동 여부를 TCP 프로브로 감지한다. 엔드포인트는 로그인 필수이며,
프로브 결과(up/down)를 그대로 상태로 노출한다. 실제 소켓 연결은 monkeypatch 로 대체해
환경(설치 여부)과 무관하게 결정적으로 검증한다.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.modules.leantime import service


def test_health_requires_login(client: TestClient) -> None:
    assert client.get('/api/v1/leantime/health').status_code == 401


def test_health_reports_up_when_probe_succeeds(csrf_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(service, 'probe_leantime', lambda *a, **k: True)
    resp = csrf_client.get('/api/v1/leantime/health')
    assert resp.status_code == 200
    body = resp.json()
    assert body['status'] == 'up'
    assert body['port'] == 8081
    assert body['probe_target'] == '127.0.0.1:8081'


def test_health_reports_down_when_probe_fails(csrf_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(service, 'probe_leantime', lambda *a, **k: False)
    resp = csrf_client.get('/api/v1/leantime/health')
    assert resp.status_code == 200
    assert resp.json()['status'] == 'down'


def test_resolve_target_defaults_to_kit_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv('AEROONE_LEANTIME_HEALTH_URL', raising=False)
    assert service.resolve_target() == ('127.0.0.1', 8081)


def test_resolve_target_honors_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('AEROONE_LEANTIME_HEALTH_URL', 'http://10.10.20.50:9090')
    assert service.resolve_target() == ('10.10.20.50', 9090)


def test_resolve_target_accepts_host_port_without_scheme(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('AEROONE_LEANTIME_HEALTH_URL', '192.168.0.9:8081')
    assert service.resolve_target() == ('192.168.0.9', 8081)


def test_probe_returns_false_on_closed_port(monkeypatch: pytest.MonkeyPatch) -> None:
    # 실제로 열려 있지 않을 사설 포트로 프로브 → 예외 없이 False.
    monkeypatch.setenv('AEROONE_LEANTIME_HEALTH_URL', 'http://127.0.0.1:1')
    assert service.probe_leantime(timeout=0.2) is False
