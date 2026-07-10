from __future__ import annotations

import os
from pathlib import Path
import subprocess

import pytest

from tests.rotation_harness import SyntheticWorkspace, create_synthetic_workspace, invoke_rotation


def test_public_failpoint_validate_set_contains_only_original_four() -> None:
    # Given: the checked-in PowerShell entrypoint is inspected without execution.
    script = Path(__file__).resolve().parents[3] / "scripts" / "rotate_aeroone_credentials.ps1"
    process_environment = os.environ.copy()
    process_environment["AEROONE_ROTATION_SCRIPT"] = str(script)
    command = (
        "$parameter=(Get-Command -Name $env:AEROONE_ROTATION_SCRIPT).Parameters['Failpoint'];"
        "$attribute=@($parameter.Attributes | Where-Object {$_ -is [Management.Automation.ValidateSetAttribute]})[0];"
        "$attribute.ValidValues | Sort-Object"
    )

    # When: PowerShell reports the accepted public values.
    completed = subprocess.run(
        ["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", command],
        check=True,
        capture_output=True,
        text=True,
        env=process_environment,
        timeout=30,
    )

    # Then: only the four documented deterministic failpoints are public.
    assert completed.stdout.split() == [
        "after_db_commit",
        "after_root_env_promote",
        "before_credentials_promote",
        "before_db_commit",
    ]


@pytest.mark.parametrize(
    "arguments",
    (
        ("-Failpoint", "unsupported"),
        ("-Provider", "unsupported"),
        ("-WorkspaceRoot", "unsupported"),
    ),
)
def test_unknown_failpoint_provider_and_root_options_are_rejected(
    tmp_path: Path,
    arguments: tuple[str, str],
) -> None:
    # Given: a valid synthetic workspace and one unsupported control surface.
    workspace = create_synthetic_workspace(tmp_path)
    before_root_env = (workspace.root / ".env").read_bytes()

    # When: PowerShell parameter binding receives the unsupported option or value.
    completed = invoke_rotation(workspace, arguments)

    # Then: invocation fails before secure output or environment mutation.
    assert completed.returncode != 0
    assert (workspace.root / ".env").read_bytes() == before_root_env
    assert not (workspace.root / ".rotation-secure").exists()


def test_marker_alone_does_not_authorize_test_mode(tmp_path: Path) -> None:
    # Given: an ordinary temporary directory containing only the old public marker.
    ordinary_root = tmp_path / "ordinary-workspace"
    ordinary_root.mkdir()
    (ordinary_root / ".aeroone-rotation-test-root").write_text("test-only", encoding="utf-8")
    workspace = SyntheticWorkspace(
        root=ordinary_root,
        database_url="",
        jwt_secret="",
        admin_password="",
    )

    # When: the caller attempts to enable TestMode with the marker alone.
    completed = invoke_rotation(workspace, ("-DryRun",))

    # Then: authorization fails at the test-root boundary without discovery.
    assert completed.returncode != 0
    assert "unknown-test-root" in completed.stderr
    assert tuple(ordinary_root.iterdir()) == (ordinary_root / ".aeroone-rotation-test-root",)
