from __future__ import annotations

import os
from pathlib import Path
import secrets

from tests.rotation_harness import create_synthetic_workspace, has_exact_secure_acl, invoke_rotation


def test_precreated_plaintext_temp_hardlink_is_never_opened_or_modified(tmp_path: Path) -> None:
    # Given: the old predictable plaintext temp name is a hardlink to an external victim.
    workspace = create_synthetic_workspace(tmp_path)
    victim = tmp_path / "victim.bin"
    original = secrets.token_bytes(96)
    victim.write_bytes(original)
    predictable_temp = workspace.root / ".env.rotation-pending"
    os.link(victim, predictable_temp)

    # When: credential rotation promotes the new root environment.
    completed = invoke_rotation(workspace)

    # Then: rotation succeeds through a random CreateNew temp and the victim is unchanged.
    assert completed.returncode == 0, completed.stderr
    assert victim.read_bytes() == original
    assert predictable_temp.read_bytes() == original
    assert has_exact_secure_acl(workspace.root / ".env")
    assert has_exact_secure_acl(workspace.root / "backend" / ".env")
