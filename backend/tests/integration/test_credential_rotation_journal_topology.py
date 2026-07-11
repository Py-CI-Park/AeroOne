from __future__ import annotations

import os
from pathlib import Path

from tests.rotation_harness import create_synthetic_workspace, invoke_rotation


def test_missing_live_root_after_quarantine_is_reconciled_from_journal(tmp_path: Path) -> None:
    # Given: the process stopped after the DB commit and then died after moving the root env.
    workspace = create_synthetic_workspace(tmp_path)
    failed = invoke_rotation(workspace, ("-Failpoint", "after_db_commit"))
    root_env = workspace.root / ".env"
    quarantined = (
        workspace.root
        / ".rotation-secure"
        / "quarantine"
        / "environment"
        / "root.env.before-rotation"
    )
    assert failed.returncode != 0
    os.replace(root_env, quarantined)

    # When: a new process resumes with no live root environment file.
    resumed = invoke_rotation(workspace)

    # Then: validated journal artifacts repair the seam and complete the same rotation.
    assert resumed.returncode == 0, resumed.stderr

