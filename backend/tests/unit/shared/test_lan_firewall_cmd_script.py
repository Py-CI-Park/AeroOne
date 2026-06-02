from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]


def _firewall_script_contents() -> str:
    return (REPO_ROOT / "scripts" / "allow_lan_firewall.cmd").read_text(encoding="utf-8")


def test_allow_lan_firewall_cmd_opens_both_ports_scoped_to_local_subnet() -> None:
    contents = _firewall_script_contents()

    assert "netsh advfirewall firewall add rule" in contents
    # 두 포트(백엔드 18437 / 프론트 29501)를 정의하고 규칙의 localport 로 사용한다.
    assert "18437" in contents
    assert "29501" in contents
    assert "localport=%BACKEND_PORT%" in contents
    assert "localport=%FRONTEND_PORT%" in contents
    # LAN 외부로 노출되지 않도록 private 프로필 + 로컬 서브넷으로 제한한다.
    assert "profile=private" in contents
    assert "remoteip=LocalSubnet" in contents


def test_allow_lan_firewall_cmd_supports_remove_and_help() -> None:
    contents = _firewall_script_contents()

    assert "--remove" in contents
    assert "netsh advfirewall firewall delete rule" in contents
    assert ":help" in contents
    # netsh advfirewall 은 관리자 권한이 필요하므로 권한 확인 가드가 있어야 한다.
    assert "net session" in contents
