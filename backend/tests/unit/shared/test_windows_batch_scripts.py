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
_SETUP_SCRIPT = (REPO_ROOT / "setup.bat").read_text(encoding="utf-8")
_SETUP_OFFLINE_SCRIPT = (REPO_ROOT / "setup_offline.bat").read_text(encoding="utf-8")


def test_setup_secret_generation_is_compatible_with_windows_powershell_51() -> None:
    for script in (_SETUP_SCRIPT, _SETUP_OFFLINE_SCRIPT):
        assert "RandomNumberGenerator]::Fill" not in script
        assert script.count("RandomNumberGenerator]::Create()") == 2
        assert script.count("$rng.GetBytes($bytes)") == 2
        assert script.count("$rng.Dispose()") == 2


def test_setup_offline_installs_only_production_requirements_from_wheelhouse() -> None:
    assert 'pip install --no-index --find-links "%WHEEL_DIR%" -r requirements.txt' in _SETUP_OFFLINE_SCRIPT
    assert "requirements-dev.txt" not in _SETUP_OFFLINE_SCRIPT

    app_env = 'set "APP_ENV=closed_network"'
    database_url = 'set "DATABASE_URL=sqlite:///%BACKEND_DIR_FWD%/data/aeroone.db"'
    admin_username = 'set "ADMIN_USERNAME=admin"'
    migration = 'call python scripts\\ensure_db_state.py data\\aeroone.db'

    assert _SETUP_OFFLINE_SCRIPT.index(app_env) < _SETUP_OFFLINE_SCRIPT.index(migration)
    assert _SETUP_OFFLINE_SCRIPT.index(database_url) < _SETUP_OFFLINE_SCRIPT.index(migration)
    assert _SETUP_OFFLINE_SCRIPT.index(admin_username) < _SETUP_OFFLINE_SCRIPT.index(migration)


_START_OFFLINE_SCRIPT = (REPO_ROOT / "start_offline.bat").read_text(encoding="utf-8")


def test_start_offline_preserves_entry_path_before_argument_shifts() -> None:
    capture = 'set "ENTRY_BATCH=%~f0"'
    invocation = '-BatchPath "%ENTRY_BATCH%" -RawBatchArguments "--maintenance-preflight"'

    assert _START_OFFLINE_SCRIPT.index(capture) < _START_OFFLINE_SCRIPT.index(":parse_args")
    assert invocation in _START_OFFLINE_SCRIPT
    assert '-BatchPath "%~f0"' not in _START_OFFLINE_SCRIPT


def _run_cmd(cwd: Path, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    resolved = list(args)
    if resolved:
        first = resolved[0]
        lowered = first.lower()
        if (lowered.endswith(".bat") or lowered.endswith(".cmd")) and not Path(first).is_absolute() and not first.startswith((".\\", "./")):
            resolved[0] = ".\\" + first
    return subprocess.run(
        ["cmd", "/d", "/c", *resolved],
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


def _make_stub_open_notebook_bundle(tmp_path: Path) -> Path:
    bundle = tmp_path / "AeroOne-bundle"
    bundle.mkdir()
    (bundle / "3-run.bat").write_text("@echo off\r\nexit /b 0\r\n", encoding="utf-8")
    return bundle


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
    frontend_env = (repo_root / "frontend" / ".env.local").read_text(encoding="utf-8")
    backend_env = (repo_root / "backend" / ".env").read_text(encoding="utf-8")
    assert "JWT_SECRET_KEY=change-me" not in backend_env
    assert "ADMIN_PASSWORD=change-me" not in backend_env
    assert re.search(r"^JWT_SECRET_KEY=.{32,}$", backend_env, re.MULTILINE)
    assert re.search(r"^ADMIN_PASSWORD=.{24,}$", backend_env, re.MULTILINE)
    assert (repo_root / "_database" / "newsletter").is_dir()
    assert (repo_root / "_database" / "civil_aircraft").is_dir()
    assert (repo_root / "_database" / "document").is_dir()
    assert (repo_root / "_database" / "nsa").is_dir()
    assert "/_database/newsletter" in backend_env
    assert "CIVIL_AIRCRAFT_ROOT=" in backend_env and "/_database/civil_aircraft" in backend_env
    assert "DOCUMENT_ROOT=" in backend_env and "/_database/document" in backend_env
    assert "NSA_ROOT=" in backend_env and "/_database/nsa" in backend_env
    assert "AI_FEATURES_ENABLED=true" in backend_env
    assert "OLLAMA_BASE_URL=http://127.0.0.1:11434" in backend_env
    assert "OLLAMA_DEFAULT_MODEL=gemma4:12b" in backend_env
    assert "SERVER_API_BASE_URL=http://127.0.0.1:18437" in backend_env
    assert "SERVER_API_BASE_URL=http://127.0.0.1:18437" in frontend_env

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
    assert any("uvicorn app.main:app --host 127.0.0.1" in line for line in lines)
    assert not any("uvicorn app.main:app --host 0.0.0.0" in line for line in lines)
    assert any("start_frontend_window.cmd" in line for line in lines)
    assert any("http://localhost:29501" in line for line in lines)


def test_start_dry_run_prints_readiness_wrapper_command() -> None:
    result = _run_cmd(REPO_ROOT, "start.bat", "--dry-run")

    assert result.returncode == 0, result.stdout + result.stderr
    lines = _non_empty_lines(result.stdout)
    browser_line = next((line for line in lines if "open_browser.cmd" in line), None)
    pattern = re.compile(r'open_browser\.cmd.*http://localhost:29501/.*\b18437\b.*\b29501\b.*\b20\b.*\b180\b')
    assert any("uvicorn app.main:app" in line for line in lines)
    assert any("start_frontend_window.cmd" in line for line in lines)
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
    contents = (repo_root / "scripts" / "start_frontend_dev.cmd").read_text(encoding="utf-8")
    assert 'set "NEXT_PUBLIC_API_BASE_URL=http://localhost:18437"' in contents
    assert 'set "SERVER_API_BASE_URL=http://127.0.0.1:18437"' in contents


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
    assert "::1" in combined


def test_start_offline_dry_run_prints_readiness_wrapper_command() -> None:
    # 기본이 LAN 으로 바뀌어 URL 이 감지된 IP 가 되므로, 이 구조 검증은 --local 로 고정해
    # localhost URL 을 결정적으로 만든다(여기서 검증하려는 건 open_browser 래퍼 인자 구조다).
    result = _run_cmd(REPO_ROOT, "start_offline.bat", "--dry-run", "--local")

    assert result.returncode == 0, result.stdout + result.stderr
    lines = _non_empty_lines(result.stdout)
    browser_line = next((line for line in lines if "open_browser.cmd" in line), None)
    pattern = re.compile(r'open_browser\.cmd.*http://localhost:29501/.*\b18437\b.*\b29501\b.*\b20\b.*\b60\b')
    assert any("uvicorn app.main:app" in line for line in lines)
    assert any("start_frontend_offline.cmd" in line for line in lines)
    assert browser_line is not None
    assert pattern.search(browser_line), browser_line


def test_start_offline_dry_run_frontend_window_avoids_broken_nested_quotes() -> None:
    result = _run_cmd(REPO_ROOT, "start_offline.bat", "--dry-run")

    assert result.returncode == 0, result.stdout + result.stderr
    lines = _non_empty_lines(result.stdout)
    frontend_index = lines.index("[DRY-RUN] offline frontend window command:")
    frontend_line = lines[frontend_index + 1]

    # 회귀 가드: backslash 로 escape 한 따옴표(\")는 cmd 에서 escape 가 아니라 리터럴 \" 로
    # 남아, 새 창에서 'call \"...start_frontend_offline.cmd\" 은(는) 내부/외부 명령... 배치
    # 파일이 아닙니다' 오류를 냈다(1.0.14 폐쇄망 프론트 창 기동 실패). 백엔드 창과 동일하게
    # cd /d ""path"" 로 scripts 로 이동한 뒤 무인용 상대경로로 call 해야 한다.
    old_nested_launch_pattern = re.compile(r'call \\".*start_frontend_offline\.cmd\\"')
    assert not old_nested_launch_pattern.search(frontend_line), frontend_line
    assert not any(old_nested_launch_pattern.search(line) for line in lines), result.stdout
    assert 'cd /d ""' in frontend_line, frontend_line
    assert frontend_line.rstrip('"').endswith("call start_frontend_offline.cmd"), frontend_line


def test_setup_offline_dry_run_bypasses_only_the_mutating_maintenance_gate() -> None:
    assert 'for %%A in (%*) do if /I "%%~A"=="--dry-run"' in _SETUP_OFFLINE_SCRIPT
    assert (
        'if /I not "%AEROONE_MAINTENANCE_GATE_HELD%"=="1" '
        'if not defined AEROONE_DRY_RUN_REQUESTED ('
    ) in _SETUP_OFFLINE_SCRIPT
    assert "invoke_with_maintenance_gate.ps1" in _SETUP_OFFLINE_SCRIPT

def test_setup_offline_dry_run_allow_host_prints_lan_info() -> None:
    result = _run_cmd(REPO_ROOT, "setup_offline.bat", "--dry-run", "--no-pause", "--allow-host=192.168.1.10")

    assert result.returncode == 0, result.stdout + result.stderr
    lines = _non_empty_lines(result.stdout)
    assert any("LAN host = 192.168.1.10" in line for line in lines)
    assert any("http://localhost:29501,http://192.168.1.10:29501" in line for line in lines)
    assert any("NEXT_PUBLIC_API_BASE_URL = http://192.168.1.10:18437" in line for line in lines)


def test_setup_offline_dry_run_default_writes_lan_env() -> None:
    # 1.0.22+: 기본이 LAN. 옵션 없으면 LAN IPv4 를 감지해 .env(CORS/NEXT_PUBLIC)에 IP 를 넣고,
    # LAN IPv4 가 없는 환경에서는 localhost 로 폴백한다(두 경로 모두 결정적).
    result = _run_cmd(REPO_ROOT, "setup_offline.bat", "--dry-run", "--no-pause")

    assert result.returncode == 0, result.stdout + result.stderr
    lines = _non_empty_lines(result.stdout)
    lan = next((line for line in lines if line.startswith("[DRY-RUN] LAN host = ")), "")
    assert lan, result.stdout
    if re.search(r"LAN host = \d+\.\d+\.\d+\.\d+", lan):
        assert any("NEXT_PUBLIC_API_BASE_URL = http://" in line and ":18437" in line for line in lines)
    else:
        assert "localhost only" in lan


def test_setup_offline_dry_run_local_is_loopback_only() -> None:
    result = _run_cmd(REPO_ROOT, "setup_offline.bat", "--dry-run", "--no-pause", "--local")

    assert result.returncode == 0, result.stdout + result.stderr
    lines = _non_empty_lines(result.stdout)
    assert any("localhost only" in line for line in lines)
    assert not any("0.0.0.0" in line for line in lines)


def test_start_offline_dry_run_allow_host_uses_external_binding() -> None:
    result = _run_cmd(REPO_ROOT, "start_offline.bat", "--dry-run", "--allow-host=10.0.0.5")

    assert result.returncode == 0, result.stdout + result.stderr
    lines = _non_empty_lines(result.stdout)
    assert any("uvicorn app.main:app --host 0.0.0.0 --port 18437" in line for line in lines)
    assert any("URL  : http://10.0.0.5:18437" in line for line in lines)
    assert any("URL  : http://10.0.0.5:29501/" in line for line in lines)
    browser_line = next((line for line in lines if "open_browser.cmd" in line), None)
    assert browser_line is not None
    assert "http://10.0.0.5:29501/" in browser_line
    assert any("LAN host = 10.0.0.5" in line for line in lines)


def test_start_offline_dry_run_default_serves_lan() -> None:
    # 1.0.22+: 기본이 LAN. 옵션 없으면 LAN IPv4 를 감지해 0.0.0.0 으로 바인딩하고,
    # LAN IPv4 가 없는 환경에서는 localhost 로 폴백한다(두 경로 모두 결정적).
    result = _run_cmd(REPO_ROOT, "start_offline.bat", "--dry-run")

    assert result.returncode == 0, result.stdout + result.stderr
    lines = _non_empty_lines(result.stdout)
    lan = next((line for line in lines if line.startswith("[DRY-RUN] LAN host = ")), "")
    assert lan, result.stdout
    if re.search(r"LAN host = \d+\.\d+\.\d+\.\d+", lan):
        assert any("uvicorn app.main:app --host 0.0.0.0 --port 18437" in line for line in lines)
    else:
        assert "localhost only" in lan
        assert any("uvicorn app.main:app --host 127.0.0.1 --port 18437" in line for line in lines)


def test_start_offline_dry_run_local_keeps_loopback() -> None:
    result = _run_cmd(REPO_ROOT, "start_offline.bat", "--dry-run", "--local")

    assert result.returncode == 0, result.stdout + result.stderr
    lines = _non_empty_lines(result.stdout)
    assert any("uvicorn app.main:app --host 127.0.0.1 --port 18437" in line for line in lines)
    assert not any("uvicorn app.main:app --host 0.0.0.0" in line for line in lines)
    assert any("URL  : http://localhost:18437" in line for line in lines)
    assert any("localhost only" in line for line in lines)


def test_start_offline_defaults_to_lan_with_local_optout() -> None:
    # 1.0.22+: 기본 LAN. 인자/--local 없으면 ALLOW_HOST=auto 로 두고, 감지 실패 시 loopback 폴백.
    # 더 이상 인터랙티브 프롬프트(choice)는 쓰지 않는다.
    contents = (REPO_ROOT / "start_offline.bat").read_text(encoding="utf-8")
    assert 'if not defined LOCAL_ONLY if not defined ALLOW_HOST set "ALLOW_HOST=auto"' in contents
    assert '"--local"' in contents
    assert ":prompt_lan_choice" not in contents
    assert "choice /C YN" not in contents


def test_start_offline_dry_run_allow_host_auto_resolves_lan_ip() -> None:
    # --allow-host=auto 는 LAN IPv4 를 감지해 0.0.0.0 으로 띄운다(없으면 localhost 폴백, 에러 없음).
    result = _run_cmd(REPO_ROOT, "start_offline.bat", "--dry-run", "--allow-host=auto")

    assert result.returncode == 0, result.stdout + result.stderr
    lines = _non_empty_lines(result.stdout)
    lan = next((line for line in lines if line.startswith("[DRY-RUN] LAN host = ")), "")
    if re.search(r"LAN host = \d+\.\d+\.\d+\.\d+", lan):
        assert any("uvicorn app.main:app --host 0.0.0.0" in line for line in lines)
    else:
        assert "localhost only" in lan


def test_setup_offline_dry_run_allow_host_auto_resolves_lan_ip() -> None:
    result = _run_cmd(REPO_ROOT, "setup_offline.bat", "--dry-run", "--no-pause", "--allow-host=auto")

    assert result.returncode == 0, result.stdout + result.stderr
    lines = _non_empty_lines(result.stdout)
    lan = next((line for line in lines if line.startswith("[DRY-RUN] LAN host = ")), "")
    if re.search(r"LAN host = \d+\.\d+\.\d+\.\d+", lan):
        assert any("NEXT_PUBLIC_API_BASE_URL = http://" in line and ":18437" in line for line in lines)
    else:
        assert "localhost only" in lan


def test_start_offline_no_interactive_prompt_remains() -> None:
    # 1.0.22+: 기본이 LAN 이라 인터랙티브 프롬프트는 제거됨. dry-run 은 입력 대기 없이 끝난다.
    result = _run_cmd(REPO_ROOT, "start_offline.bat", "--dry-run")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "[SELECT]" not in result.stdout


def test_start_offline_allow_host_missing_value_fails() -> None:
    result = _run_cmd(REPO_ROOT, "start_offline.bat", "--allow-host")

    assert result.returncode == 1, result.stdout + result.stderr
    assert "--allow-host requires a host argument" in result.stdout


def test_start_frontend_offline_script_supports_allow_host_branch() -> None:
    script = REPO_ROOT / "scripts" / "start_frontend_offline.cmd"
    contents = script.read_text(encoding="utf-8")

    assert "if defined AEROONE_ALLOW_HOST" in contents
    assert "next.cmd start -H 0.0.0.0 -p 29501" in contents
    assert "next.cmd start -H 127.0.0.1 -p 29501" in contents
    assert 'set "SERVER_API_BASE_URL=http://127.0.0.1:18437"' in contents


def test_start_frontend_offline_recovers_node_when_not_on_path() -> None:
    script = REPO_ROOT / "scripts" / "start_frontend_offline.cmd"
    contents = script.read_text(encoding="utf-8")

    # node 가 PATH 에 없는 창(탐색기 더블클릭 등)에서도 표준 설치 위치가 있으면
    # PATH 앞에 추가해 프론트가 뜨도록 하는 복구 라인.
    assert r"%ProgramFiles%\nodejs\node.exe" in contents
    assert r'set "PATH=%ProgramFiles%\nodejs;%PATH%"' in contents


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

def test_run_all_dry_run_waits_for_open_notebook_readiness(tmp_path: Path) -> None:
    bundle = _make_stub_open_notebook_bundle(tmp_path)
    result = _run_cmd(
        REPO_ROOT,
        r"scripts\run_all.bat",
        "--dry-run",
        "--on-bundle",
        str(bundle),
    )

    assert result.returncode == 0, result.stdout + result.stderr
    lines = _non_empty_lines(result.stdout)
    assert any("would wait backend health" in line for line in lines)
    assert any("would wait Open Notebook API health" in line for line in lines)
    assert any("would wait Open Notebook frontend" in line for line in lines)
    assert any("would inspect Open Notebook runtime config" in line for line in lines)
    assert any('would call "' in line and "3-run.bat" in line for line in lines)


def test_run_all_passes_network_mode_to_open_notebook_bundle(tmp_path: Path) -> None:
    bundle = _make_stub_open_notebook_bundle(tmp_path)
    result = _run_cmd(
        REPO_ROOT,
        r"scripts\run_all.bat",
        "--dry-run",
        "--on-bundle",
        str(bundle),
        "--local",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert 'would call "' in result.stdout
    assert '3-run.bat" --local' in result.stdout


def test_offline_package_delegates_to_allow_list_builder() -> None:
    result = _run_cmd(REPO_ROOT, "offline_package.bat", "--help")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "git-archive allow-list" in result.stdout
    assert "requirements-dev.txt" not in result.stdout

    script = (REPO_ROOT / "offline_package.bat").read_text(encoding="utf-8")
    assert "scripts\\build_offline_package.ps1" in script
    assert "-Version 1.13.0 -DryRun" in script
    assert "robocopy" not in script.lower()
    assert "requirements-dev.txt" not in script
