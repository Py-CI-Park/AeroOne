from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import socket
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


def _write_frontend_dev_delegate_stub(path: Path) -> str:
    marker = "[STUB][FRONTEND-DEV] start_frontend_dev.cmd invoked"
    path.write_text(
        "@echo off\r\n"
        f"echo {marker}\r\n"
        "echo start_frontend_dev.cmd delegated>>\"%STUB_LOG%\"\r\n"
        "exit /b 0\r\n",
        encoding="utf-8",
    )
    return marker


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
    stub_source = (
        "using System;\n"
        "using System.IO;\n"
        "class Program {\n"
        "    static int Main(string[] args) {\n"
        "        var logPath = Environment.GetEnvironmentVariable(\"STUB_LOG\");\n"
        "        if (!string.IsNullOrEmpty(logPath)) {\n"
        "            File.AppendAllText(logPath, \"powershell \" + string.Join(\" \", args) + Environment.NewLine);\n"
        "        }\n"
        "        return 0;\n"
        "    }\n"
        "}\n"
    )
    compile_result = subprocess.run(
        [
            "powershell",
            "-NoLogo",
            "-NoProfile",
            "-Command",
            "Add-Type -TypeDefinition @'\n"
            + stub_source
            + "'@ -OutputAssembly '"
            + str(bin_dir / "powershell.exe")
            + "' -OutputType ConsoleApplication",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if compile_result.returncode != 0:
        raise AssertionError(compile_result.stdout + compile_result.stderr)
    return bin_dir, log_file


def _make_open_browser_test_copy(tmp_path: Path) -> Path:
    scripts_dir = tmp_path / "scripts"
    windows_dir = scripts_dir / "windows"
    windows_dir.mkdir(parents=True)
    script_path = scripts_dir / "open_browser.cmd"
    script_text = (REPO_ROOT / "scripts" / "open_browser.cmd").read_text(encoding="utf-8")
    timeout_line = "timeout /t 6 /nobreak >nul"
    start_line = 'start "" "%URL%"'
    if timeout_line in script_text:
        script_text = script_text.replace(timeout_line, "rem timeout disabled in test", 1)
    if start_line in script_text:
        script_text = script_text.replace(start_line, "rem browser start disabled in test", 1)
    script_path.write_text(script_text, encoding="utf-8")
    (windows_dir / "wait_for_services.ps1").write_text("", encoding="utf-8")
    return script_path


def _make_frontend_launcher_repo(tmp_path: Path) -> tuple[Path, Path, Path]:
    repo_root = tmp_path / "repo"
    frontend_dir = repo_root / "frontend"
    scripts_dir = repo_root / "scripts"

    frontend_dir.mkdir(parents=True)
    scripts_dir.mkdir(parents=True)

    shutil.copy2(REPO_ROOT / "scripts" / "start_frontend_dev.cmd", scripts_dir / "start_frontend_dev.cmd")
    return repo_root, frontend_dir, scripts_dir


def _make_wait_for_services_test_copy(tmp_path: Path) -> Path:
    helper_dir = tmp_path / "scripts" / "windows"
    helper_dir.mkdir(parents=True)
    helper_path = helper_dir / "wait_for_services.ps1"

    script_text = (REPO_ROOT / "scripts" / "windows" / "wait_for_services.ps1").read_text(encoding="utf-8")
    script_text, replacement_count = re.subn(
        r"(?m)^\s*Start-Process\s+\$Url(?:\s*\|\s*Out-Null)?\s*$",
        'Write-Host "[READY] Browser launch skipped in test"',
        script_text,
        count=1,
    )
    if replacement_count != 1:
        raise AssertionError("Failed to neutralize browser launch in wait_for_services.ps1 test copy")
    helper_path.write_text(script_text, encoding="utf-8")
    return helper_path


def test_wait_for_services_times_out_when_backend_never_opens() -> None:
    helper_path = REPO_ROOT / "scripts" / "windows" / "wait_for_services.ps1"

    result = subprocess.run(
        [
            "powershell",
            "-NoLogo",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(helper_path),
            "-Url",
            "http://localhost:29501/",
            "-BackendPort",
            "65534",
            "-FrontendPort",
            "65535",
            "-BackendTimeoutSeconds",
            "1",
            "-FrontendTimeoutSeconds",
            "1",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    assert result.returncode == 1, result.stdout + result.stderr
    combined_output = result.stdout + result.stderr
    assert "backend port 65534 did not become ready within 1 seconds." in combined_output.lower()


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
    browser_line = next((line for line in lines if "open_browser.cmd" in line), None)
    pattern = re.compile(r'open_browser\.cmd.*http://localhost:29501/.*\b18437\b.*\b29501\b.*\b20\b.*\b60\b')
    assert any("uvicorn app.main:app" in line for line in lines)
    assert any("start_frontend_dev.cmd" in line for line in lines)
    assert browser_line is not None
    assert pattern.search(browser_line), browser_line


def test_start_dry_run_uses_frontend_wrapper_and_extended_timeout() -> None:
    result = _run_cmd(REPO_ROOT, "start.bat", "--dry-run")

    assert result.returncode == 0, result.stdout + result.stderr
    lines = _non_empty_lines(result.stdout)
    frontend_index = lines.index("[DRY-RUN] frontend window command:")
    frontend_line = lines[frontend_index + 1]
    browser_index = lines.index("[DRY-RUN] browser readiness command:")
    browser_line = lines[browser_index + 1]
    browser_pattern = re.compile(
        r'^call ".*[\\/]scripts[\\/]open_browser\.cmd" "http://localhost:29501/" 18437 29501 20 180$'
    )
    old_nested_launch_pattern = re.compile(
        r'^cmd /k .*call \\".*start_frontend_dev\.cmd\\"$'
    )

    assert frontend_line == "cmd /k start_frontend_window.cmd"
    assert browser_pattern.fullmatch(browser_line), browser_line
    assert not any(old_nested_launch_pattern.search(line) for line in lines), result.stdout


def test_start_frontend_window_delegates_to_dev_script(tmp_path: Path) -> None:
    repo_root, _, scripts_dir = _make_frontend_launcher_repo(tmp_path)
    dev_stub_marker = _write_frontend_dev_delegate_stub(scripts_dir / "start_frontend_dev.cmd")
    shutil.copy2(REPO_ROOT / "scripts" / "start_frontend_window.cmd", scripts_dir / "start_frontend_window.cmd")
    bin_dir, log_file = _make_stub_commands(tmp_path)
    env = os.environ.copy()
    env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
    env["STUB_LOG"] = str(log_file)

    result = _run_cmd(repo_root, r"scripts\start_frontend_window.cmd", env=env)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "[FRONTEND][BOOT] AeroOne Web UI" in result.stdout
    assert dev_stub_marker in result.stdout
    log_lines = log_file.read_text(encoding="utf-8").splitlines()
    assert "start_frontend_dev.cmd delegated" in log_lines
    assert not any(line.startswith("npm.cmd run dev") for line in log_lines)


def test_start_frontend_dev_preserves_caches_without_clean(tmp_path: Path) -> None:
    repo_root, frontend_dir, _ = _make_frontend_launcher_repo(tmp_path)
    bin_dir, log_file = _make_stub_commands(tmp_path)
    env = os.environ.copy()
    env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
    env["STUB_LOG"] = str(log_file)

    (frontend_dir / ".next").mkdir()
    (frontend_dir / ".turbo").mkdir()

    result = _run_cmd(repo_root, r"scripts\start_frontend_dev.cmd", env=env)

    assert result.returncode == 0, result.stdout + result.stderr
    assert (frontend_dir / ".next").exists()
    assert (frontend_dir / ".turbo").exists()
    assert any(
        line.startswith("npm.cmd run dev")
        for line in log_file.read_text(encoding="utf-8").splitlines()
    )


def test_start_frontend_dev_clears_caches_with_clean(tmp_path: Path) -> None:
    repo_root, frontend_dir, _ = _make_frontend_launcher_repo(tmp_path)
    bin_dir, log_file = _make_stub_commands(tmp_path)
    env = os.environ.copy()
    env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
    env["STUB_LOG"] = str(log_file)

    (frontend_dir / ".next").mkdir()
    (frontend_dir / ".turbo").mkdir()

    result = _run_cmd(repo_root, r"scripts\start_frontend_dev.cmd", "--clean", env=env)

    assert result.returncode == 0, result.stdout + result.stderr
    assert not (frontend_dir / ".next").exists()
    assert not (frontend_dir / ".turbo").exists()
    assert any(
        line.startswith("npm.cmd run dev")
        for line in log_file.read_text(encoding="utf-8").splitlines()
    )


def test_wait_for_services_accepts_ipv6_loopback_listeners(tmp_path: Path) -> None:
    helper_path = _make_wait_for_services_test_copy(tmp_path)

    backend_socket = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    frontend_socket = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    for sock in (backend_socket, frontend_socket):
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    backend_socket.bind(("::1", 0))
    frontend_socket.bind(("::1", 0))
    backend_socket.listen(1)
    frontend_socket.listen(1)

    backend_port = backend_socket.getsockname()[1]
    frontend_port = frontend_socket.getsockname()[1]

    try:
        result = subprocess.run(
            [
                "powershell",
                "-NoLogo",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(helper_path),
                "-Url",
                "http://localhost:29501/",
                "-BackendPort",
                str(backend_port),
                "-FrontendPort",
                str(frontend_port),
                "-BackendTimeoutSeconds",
                "2",
                "-FrontendTimeoutSeconds",
                "2",
            ],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    finally:
        backend_socket.close()
        frontend_socket.close()

    assert result.returncode == 0, result.stdout + result.stderr
    combined = (result.stdout + result.stderr).lower()
    assert f"backend port {backend_port}" in combined
    assert f"frontend port {frontend_port}" in combined


def test_start_offline_dry_run_prints_readiness_wrapper_command() -> None:
    result = _run_cmd(REPO_ROOT, "start_offline.bat", "--dry-run")

    assert result.returncode == 0, result.stdout + result.stderr
    lines = _non_empty_lines(result.stdout)
    browser_line = next((line for line in lines if "open_browser.cmd" in line), None)
    pattern = re.compile(r'open_browser\.cmd.*http://localhost:29501/.*\b18437\b.*\b29501\b.*\b20\b.*\b60\b')
    assert any("uvicorn app.main:app" in line for line in lines)
    assert any("start_frontend_offline.cmd" in line for line in lines)
    assert browser_line is not None
    assert pattern.search(browser_line), browser_line


def test_open_browser_cmd_delegates_to_wait_helper(tmp_path: Path) -> None:
    bin_dir, log_file = _make_powershell_stub(tmp_path)
    script_path = _make_open_browser_test_copy(tmp_path)
    env = os.environ.copy()
    env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
    env["STUB_LOG"] = str(log_file)

    result = _run_cmd(
        tmp_path,
        str(script_path.relative_to(tmp_path)).replace("/", "\\"),
        "http://localhost:29501/",
        "18437",
        "29501",
        "20",
        "60",
        env=env,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert log_file.exists(), result.stdout + result.stderr
    invocation = log_file.read_text(encoding="utf-8")
    assert "wait_for_services.ps1" in invocation
    assert "-Url" in invocation
    assert "http://localhost:29501/" in invocation
    assert "-BackendPort 18437" in invocation
    assert "-FrontendPort 29501" in invocation
    assert "-BackendTimeoutSeconds 20" in invocation
    assert "-FrontendTimeoutSeconds 60" in invocation
