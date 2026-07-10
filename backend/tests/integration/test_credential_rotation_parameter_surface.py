from __future__ import annotations

from pathlib import Path

import pytest

from tests.rotation_harness import create_synthetic_workspace, invoke_rotation


@pytest.mark.parametrize(
    'arguments',
    (
        ('-Failpoint', 'unsupported'),
        ('-Provider', 'unsupported'),
        ('-WorkspaceRoot', 'unsupported'),
    ),
)
def test_unknown_failpoint_provider_and_root_options_are_rejected(
    tmp_path: Path,
    arguments: tuple[str, str],
) -> None:
    # Given: a valid synthetic workspace and one unsupported control surface.
    workspace = create_synthetic_workspace(tmp_path)
    before_root_env = (workspace.root / '.env').read_bytes()

    # When: PowerShell parameter binding receives the unsupported option or value.
    completed = invoke_rotation(workspace, arguments)

    # Then: invocation fails before secure output or environment mutation.
    assert completed.returncode != 0
    assert (workspace.root / '.env').read_bytes() == before_root_env
    assert not (workspace.root / '.rotation-secure').exists()
