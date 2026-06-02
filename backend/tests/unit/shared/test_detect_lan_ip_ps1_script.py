from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]


def test_detect_lan_ip_script_prefers_gateway_then_falls_back_to_private_ranges() -> None:
    script = REPO_ROOT / "scripts" / "windows" / "detect_lan_ip.ps1"
    contents = script.read_text(encoding="utf-8")

    # 기본 게이트웨이가 있는 Up 어댑터의 IPv4 를 우선한다.
    assert "Get-NetIPConfiguration" in contents
    assert "IPv4DefaultGateway" in contents
    # 폴백: loopback(127.*) / APIPA(169.254.*) 제외 + 사설 IPv4 범위.
    assert "127.*" in contents
    assert "169.254.*" in contents
    assert "192.168.*" in contents
