from __future__ import annotations

from pathlib import Path

from tests.rotation_harness import create_synthetic_workspace, env_value, invoke_rotation


def test_backend_only_install_rotates_without_creating_root_environment(tmp_path: Path) -> None:
    # Given: an installer topology with only backend/.env and an initialized database.
    workspace = create_synthetic_workspace(tmp_path)
    root_environment = workspace.root / ".env"
    backend_environment = workspace.root / "backend" / ".env"
    root_environment.unlink()
    previous_jwt = env_value(backend_environment, "JWT_SECRET_KEY")
    previous_password = env_value(backend_environment, "ADMIN_PASSWORD")

    # When: credential rotation completes against the backend-only installation.
    completed = invoke_rotation(workspace)

    # Then: only backend/.env rotates and no duplicate root secret file is created.
    assert completed.returncode == 0, completed.stderr
    assert not root_environment.exists()
    assert env_value(backend_environment, "JWT_SECRET_KEY") != previous_jwt
    assert env_value(backend_environment, "ADMIN_PASSWORD") != previous_password
    assert (workspace.root / ".rotation-secure" / "credentials.dpapi").is_file()


def test_backend_only_precommit_resume_preserves_absent_root_environment(tmp_path: Path) -> None:
    # Given: a backend-only rotation interrupted after publishing its prepared journal.
    workspace = create_synthetic_workspace(tmp_path)
    root_environment = workspace.root / ".env"
    root_environment.unlink()
    interrupted = invoke_rotation(workspace, ("-Failpoint", "before_db_commit"))
    assert interrupted.returncode != 0
    assert not root_environment.exists()

    # When: the same immutable prepared state is resumed.
    resumed = invoke_rotation(workspace)

    # Then: forward recovery completes without materializing a root environment.
    assert resumed.returncode == 0, resumed.stderr
    assert not root_environment.exists()


def test_backend_only_resume_rejects_new_root_environment_topology(tmp_path: Path) -> None:
    # Given: a backend-only prepared journal followed by an unexpected root .env appearance.
    workspace = create_synthetic_workspace(tmp_path)
    root_environment = workspace.root / ".env"
    backend_environment = workspace.root / "backend" / ".env"
    root_environment.unlink()
    interrupted = invoke_rotation(workspace, ("-Failpoint", "before_db_commit"))
    assert interrupted.returncode != 0
    backend_before_resume = backend_environment.read_bytes()
    root_environment.write_bytes(backend_before_resume)

    # When: resume validates the journal-bound environment topology.
    resumed = invoke_rotation(workspace)

    # Then: drift fails closed before changing the database or backend environment.
    assert resumed.returncode != 0
    assert "env-topology-changed" in resumed.stderr
    assert backend_environment.read_bytes() == backend_before_resume
