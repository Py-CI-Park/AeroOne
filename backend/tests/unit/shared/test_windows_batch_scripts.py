from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows batch scripts only")

REPO_ROOT = Path(__file__).resolve().parents[4]


def _run_cmd(cwd: Path, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["cmd", "/d", "/c", *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def _non_empty_lines(output: str) -> list[str]:
    return [line.strip() for line in output.splitlines() if line.strip()]


def _write_stub_command(path: Path) -> None:
    path.write_text(
        "@echo off\r\n"
        "echo %~nx0 %*>>\"%STUB_LOG%\"\r\n"
        "exit /b 0\r\n",
        encoding="utf-8",
    )


def _make_stub_repo(tmp_path: Path) -> Path:
    repo_root = tmp_path / "repo"
    backend_dir = repo_root / "backend"
    frontend_dir = repo_root / "frontend"
    scripts_dir = backend_dir / "scripts"
    venv_scripts_dir = backend_dir / ".venv" / "Scripts"

    backend_dir.mkdir(parents=True)
    frontend_dir.mkdir(parents=True)
    scripts_dir.mkdir(parents=True)
    venv_scripts_dir.mkdir(parents=True)

    shutil.copy2(REPO_ROOT / "setup.bat", repo_root / "setup.bat")
    shutil.copy2(REPO_ROOT / "start.bat", repo_root / "start.bat")

    (backend_dir / "requirements-dev.txt").write_text("", encoding="utf-8")
    (scripts_dir / "ensure_db_state.py").write_text("print('stub')\n", encoding="utf-8")
    (scripts_dir / "seed.py").write_text("print('stub')\n", encoding="utf-8")
    (frontend_dir / "package.json").write_text('{"name":"stub-frontend"}\n', encoding="utf-8")

    (venv_scripts_dir / "activate.bat").write_text("@echo off\r\nexit /b 0\r\n", encoding="utf-8")
    (venv_scripts_dir / "python.exe").write_bytes(b"")
    return repo_root


def _make_stub_commands(tmp_path: Path) -> tuple[Path, Path]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log_file = tmp_path / "stub.log"

    for name in ("pip.bat", "python.bat", "alembic.bat", "npm.cmd"):
        _write_stub_command(bin_dir / name)

    return bin_dir, log_file


def _make_powershell_stub(tmp_path: Path) -> tuple[Path, Path]:
    bin_dir = tmp_path / "powershell-bin"
    bin_dir.mkdir()
    log_file = tmp_path / "powershell.log"
    (bin_dir / "powershell.bat").write_text(
        "@echo off\r\n"
        "echo powershell %*>>\"%STUB_LOG%\"\r\n"
        "exit /b 0\r\n",
        encoding="utf-8",
    )
    return bin_dir, log_file


def test_setup_dry_run_lists_steps_on_separate_lines() -> None:
    result = _run_cmd(REPO_ROOT, "setup.bat", "--dry-run", "--no-pause")

    assert result.returncode == 0, result.stdout + result.stderr
    lines = _non_empty_lines(result.stdout)
    assert any(line.startswith("[DRY-RUN] backend env") for line in lines)
    assert any(line.startswith("2.") and "venv" in line for line in lines)
    assert any(line.startswith("3.") and "pip install" in line for line in lines)
    assert not any("venv" in line and "pip install" in line for line in lines)


def test_setup_help_lists_venv_and_pip_on_separate_lines() -> None:
    result = _run_cmd(REPO_ROOT, "setup.bat", "--help")

    assert result.returncode == 0, result.stdout + result.stderr
    lines = _non_empty_lines(result.stdout)
    assert any(line.startswith("- backend .venv") for line in lines)
    assert any(line.startswith("- pip install") for line in lines)
    assert not any("backend .venv" in line and "pip install" in line for line in lines)


def test_setup_executes_full_flow_in_stub_repo(tmp_path: Path) -> None:
    repo_root = _make_stub_repo(tmp_path)
    bin_dir, log_file = _make_stub_commands(tmp_path)
    env = os.environ.copy()
    env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
    env["STUB_LOG"] = str(log_file)

    result = _run_cmd(repo_root, "setup.bat", "--no-pause", env=env)

    assert result.returncode == 0, result.stdout + result.stderr
    assert (repo_root / "backend" / ".env").exists()
    assert (repo_root / "frontend" / ".env.local").exists()

    log_lines = log_file.read_text(encoding="utf-8").splitlines()
    assert any(line.startswith("pip.bat install -r requirements-dev.txt") for line in log_lines)
    assert any(line.startswith("python.bat scripts\\ensure_db_state.py data\\aeroone.db") for line in log_lines)
    assert any(line.startswith("alembic.bat upgrade head") for line in log_lines)
    assert any(line.startswith("python.bat scripts\\seed.py") for line in log_lines)
    assert any(line.startswith("npm.cmd install") for line in log_lines)


def test_start_dry_run_requires_backend_and_frontend_directories(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    shutil.copy2(REPO_ROOT / "start.bat", repo_root / "start.bat")

    result = _run_cmd(repo_root, "start.bat", "--dry-run")

    assert result.returncode == 1, result.stdout + result.stderr
    assert "backend directory not found" in result.stdout.lower()


def test_start_dry_run_prints_launch_commands() -> None:
    result = _run_cmd(REPO_ROOT, "start.bat", "--dry-run")

    assert result.returncode == 0, result.stdout + result.stderr
    lines = _non_empty_lines(result.stdout)
    assert any("uvicorn app.main:app" in line for line in lines)
    assert any("start_frontend_dev.cmd" in line for line in lines)
    assert any("http://localhost:29501" in line for line in lines)


def test_start_dry_run_prints_readiness_wrapper_command() -> None:
    result = _run_cmd(REPO_ROOT, "start.bat", "--dry-run")

    assert result.returncode == 0, result.stdout + result.stderr
    lines = _non_empty_lines(result.stdout)
    assert any("uvicorn app.main:app" in line for line in lines)
    assert any("start_frontend_dev.cmd" in line for line in lines)
    assert any(
        "open_browser.cmd" in line and "18437" in line and "29501" in line and "20" in line and "60" in line
        for line in lines
    )


def test_start_offline_dry_run_prints_readiness_wrapper_command() -> None:
    result = _run_cmd(REPO_ROOT, "start_offline.bat", "--dry-run")

    assert result.returncode == 0, result.stdout + result.stderr
    lines = _non_empty_lines(result.stdout)
    assert any("uvicorn app.main:app" in line for line in lines)
    assert any("start_frontend_offline.cmd" in line for line in lines)
    assert any(
        "open_browser.cmd" in line and "18437" in line and "29501" in line and "20" in line and "60" in line
        for line in lines
    )


def test_open_browser_cmd_delegates_to_wait_helper(tmp_path: Path) -> None:
    bin_dir, log_file = _make_powershell_stub(tmp_path)
    env = os.environ.copy()
    env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
    env["STUB_LOG"] = str(log_file)

    result = _run_cmd(
        REPO_ROOT,
        "scripts\\open_browser.cmd",
        "http://localhost:29501/",
        "18437",
        "29501",
        "20",
        "60",
        env=env,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    invocation = log_file.read_text(encoding="utf-8")
    assert "wait_for_services.ps1" in invocation
    assert "-BackendPort 18437" in invocation
    assert "-FrontendPort 29501" in invocation
    assert "-BackendTimeoutSeconds 20" in invocation
    assert "-FrontendTimeoutSeconds 60" in invocation
