from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from tests.rotation_harness import SyntheticWorkspace, create_synthetic_workspace, invoke_rotation


def _write_profile(source: Path, destination: Path, replacements: dict[str, str]) -> None:
    lines: list[str] = []
    for line in source.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator:
            lines.append(f"{key}={replacements.get(key, value)}")
        else:
            lines.append(line)
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _materialize_example_profiles(
    tmp_path: Path,
) -> tuple[Path, Path, SyntheticWorkspace]:
    workspace = create_synthetic_workspace(tmp_path)
    repository_root = Path(__file__).resolve().parents[3]
    root_example = repository_root / ".env.example"
    backend_example = repository_root / "backend" / ".env.example"
    assert backend_example.is_file()
    replacements = {
        "APP_ENV": "test",
        "DATABASE_URL": workspace.database_url,
        "JWT_SECRET_KEY": workspace.jwt_secret,
        "ADMIN_USERNAME": "admin",
        "ADMIN_PASSWORD": workspace.admin_password,
    }
    root_environment = workspace.root / ".env"
    backend_environment = workspace.root / "backend" / ".env"
    _write_profile(root_example, root_environment, replacements)
    _write_profile(backend_example, backend_environment, replacements)
    return root_environment, backend_environment, workspace


def _tree_snapshot(root: Path) -> tuple[tuple[str, bool, bytes], ...]:
    return tuple(
        (
            path.relative_to(root).as_posix(),
            path.is_dir(),
            b"" if path.is_dir() else path.read_bytes(),
        )
        for path in sorted(root.rglob("*"))
    )


def test_example_derived_root_and_backend_profiles_pass_dry_run(tmp_path: Path) -> None:
    # Given: live profiles materialized from both committed example files.
    _, _, workspace = _materialize_example_profiles(tmp_path)

    # When: dry-run parses each profile with its own schema.
    completed = invoke_rotation(workspace, ("-DryRun",))

    # Then: official host import keys and backend runtime keys are accepted.
    assert completed.returncode == 0, completed.stderr


@pytest.mark.parametrize("profile", ("root", "backend"))
def test_security_mode_key_is_required_in_each_environment_profile(
    tmp_path: Path,
    profile: str,
) -> None:
    # Given: an example-derived profile with APP_ENV removed from one live file.
    root_environment, backend_environment, workspace = _materialize_example_profiles(tmp_path)
    target = root_environment if profile == "root" else backend_environment
    target.write_text(
        "\n".join(
            line
            for line in target.read_text(encoding="utf-8").splitlines()
            if not line.startswith("APP_ENV=")
        )
        + "\n",
        encoding="utf-8",
    )

    # When: dry-run validates the distinct live profiles.
    completed = invoke_rotation(workspace, ("-DryRun",))

    # Then: both root and backend profiles require the security mode key.
    assert completed.returncode != 0
    assert "env-required-key-missing" in completed.stderr
    assert not (workspace.root / ".rotation-secure").exists()


def test_root_only_host_import_key_is_rejected_in_backend_profile(tmp_path: Path) -> None:
    # Given: an example-derived backend profile containing a root-only host mapping.
    _, backend_environment, workspace = _materialize_example_profiles(tmp_path)
    backend_environment.write_text(
        backend_environment.read_text(encoding="utf-8")
        + "NEWSLETTER_IMPORT_ROOT_HOST=./foreign-host-path\n",
        encoding="utf-8",
    )

    # When: dry-run validates the backend profile.
    completed = invoke_rotation(workspace, ("-DryRun",))

    # Then: profile separation rejects the misplaced key without output creation.
    assert completed.returncode != 0
    assert "unknown-env-key" in completed.stderr
    assert not (workspace.root / ".rotation-secure").exists()


def test_production_like_dry_run_leaves_user_profile_tree_byte_identical(
    tmp_path: Path,
) -> None:
    # Given: a copied production-provenance tree and an empty synthetic USERPROFILE.
    workspace = create_synthetic_workspace(tmp_path)
    repository_root = Path(__file__).resolve().parents[3]
    shutil.copytree(repository_root / "scripts", workspace.root / "scripts")
    shutil.copytree(repository_root / "backend" / "app", workspace.root / "backend" / "app")
    script = workspace.root / "scripts" / "rotate_aeroone_credentials.ps1"
    runtime_module = (
        workspace.root / "scripts" / "credential_rotation" / "Rotation.PythonCommand.psm1"
    )
    runtime_module.write_text(
        runtime_module.read_text(encoding="utf-8").replace(
            "$python = Join-Path $WorkspaceRoot 'backend\\.venv\\Scripts\\python.exe'",
            "$python = [IO.Path]::GetFullPath([string]$env:AEROONE_ROTATION_PYTHON)",
        ),
        encoding="utf-8",
    )
    user_profile = tmp_path / "profile"
    user_profile.mkdir()
    process_environment = os.environ.copy()
    process_environment["USERPROFILE"] = str(user_profile)
    process_environment["AEROONE_ROTATION_PYTHON"] = sys.executable
    runtime_cache = tmp_path / "runtime-cache"
    runtime_cache.mkdir()
    process_environment["APPDATA"] = str(runtime_cache / "roaming")
    process_environment["LOCALAPPDATA"] = str(runtime_cache / "local")
    process_environment["PSModuleAnalysisCachePath"] = str(runtime_cache / "module-analysis-cache")
    subprocess.run(
        ["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", "exit 0"],
        check=True,
        capture_output=True,
        text=True,
        env=process_environment,
        timeout=30,
    )
    before = _tree_snapshot(user_profile)

    # When: the production branch executes validation-only dry-run.
    completed = subprocess.run(
        [
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            "-DryRun",
        ],
        check=False,
        capture_output=True,
        text=True,
        env=process_environment,
        timeout=60,
    )

    # Then: validation succeeds without creating a secure parent, root, ACL, journal, or temp.
    assert completed.returncode == 0, completed.stderr
    assert _tree_snapshot(user_profile) == before
