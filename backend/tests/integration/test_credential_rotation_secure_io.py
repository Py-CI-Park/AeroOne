from __future__ import annotations

import ctypes
import locale
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import time

from tests.rotation_harness import create_synthetic_workspace, has_exact_secure_acl, invoke_rotation

def _is_elevated() -> bool:
    return bool(ctypes.windll.shell32.IsUserAnAdmin())


def _invoke_limited_probe(
    command: str,
    *,
    module_root: Path,
    test_root: Path,
) -> subprocess.CompletedProcess[str]:
    nonce = secrets.token_hex(8)
    launcher_root = Path(os.environ["LOCALAPPDATA"]) / "Temp"
    launcher_root.mkdir(parents=True, exist_ok=True)
    script_path = launcher_root / f"aeroone-limited-probe-{nonce}.ps1"
    stdout_path = launcher_root / f"aeroone-limited-probe-{nonce}.stdout"
    stderr_path = launcher_root / f"aeroone-limited-probe-{nonce}.stderr"
    status_path = launcher_root / f"aeroone-limited-probe-{nonce}.status"

    def quote_powershell(value: str) -> str:
        return value.replace("'", "''")

    script_path.write_text(
        "\n".join(
            (
                f"$env:AEROONE_ROTATION_MODULE_ROOT = '{quote_powershell(str(module_root))}'",
                f"$env:AEROONE_ROTATION_TEST_ROOT = '{quote_powershell(str(test_root))}'",
                f"$stdoutPath = '{quote_powershell(str(stdout_path))}'",
                f"$stderrPath = '{quote_powershell(str(stderr_path))}'",
                f"$statusPath = '{quote_powershell(str(status_path))}'",
                "$utf8 = New-Object Text.UTF8Encoding($false)",
                "$stdoutWriter = New-Object IO.StreamWriter($stdoutPath, $false, $utf8)",
                "$stderrWriter = New-Object IO.StreamWriter($stderrPath, $false, $utf8)",
                "$originalOut = [Console]::Out",
                "$originalError = [Console]::Error",
                "$exitCode = 0",
                "try {",
                "  [Console]::SetOut($stdoutWriter)",
                "  [Console]::SetError($stderrWriter)",
                command,
                "} catch {",
                "  $exitCode = 1",
                "  [Console]::Error.WriteLine(($_ | Out-String))",
                "} finally {",
                "  $stdoutWriter.Flush()",
                "  $stderrWriter.Flush()",
                "  [Console]::SetOut($originalOut)",
                "  [Console]::SetError($originalError)",
                "  $stdoutWriter.Dispose()",
                "  $stderrWriter.Dispose()",
                "  [IO.File]::WriteAllText($statusPath, [string]$exitCode, [Text.Encoding]::ASCII)",
                "}",
                "exit $exitCode",
            )
        )
        + "\n",
        encoding="utf-8-sig",
    )
    target = (
        "powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass "
        f'-File "{script_path}"'
    )
    launch_encoding = locale.getpreferredencoding(False)
    launch = subprocess.run(
        ["runas.exe", "/trustlevel:0x20000", target],
        check=False,
        capture_output=True,
        text=True,
        encoding=launch_encoding,
        errors="replace",
        timeout=10,
    )
    try:
        if launch.returncode != 0:
            return launch
        deadline = time.monotonic() + 30
        while not status_path.is_file() and time.monotonic() < deadline:
            time.sleep(0.05)
        if not status_path.is_file():
            return subprocess.CompletedProcess(
                launch.args,
                1,
                launch.stdout,
                f"{launch.stderr}\nlimited-probe-timeout",
            )
        return subprocess.CompletedProcess(
            launch.args,
            int(status_path.read_text(encoding="ascii").strip()),
            stdout_path.read_text(encoding="utf-8"),
            stderr_path.read_text(encoding="utf-8"),
        )
    finally:
        for artifact in (script_path, stdout_path, stderr_path, status_path):
            artifact.unlink(missing_ok=True)



def _invoke_secure_io_probe(tmp_path: Path, body: str) -> subprocess.CompletedProcess[str]:
    module_root = Path(__file__).resolve().parents[3] / "scripts" / "credential_rotation"
    elevated = _is_elevated()
    if elevated:
        local_temp = Path(os.environ["LOCALAPPDATA"]) / "Temp"
        local_temp.mkdir(parents=True, exist_ok=True)
        test_root = local_temp / f"aeroone-secure-io-probe-{secrets.token_hex(8)}"
    else:
        test_root = tmp_path / "secure-root"
    process_environment = os.environ.copy()
    process_environment["AEROONE_ROTATION_MODULE_ROOT"] = str(module_root)
    process_environment["AEROONE_ROTATION_TEST_ROOT"] = str(test_root)
    command = "\n".join(
        (
            "$ErrorActionPreference = 'Stop'",
            "Import-Module (Join-Path $env:AEROONE_ROTATION_MODULE_ROOT 'Rotation.PathSecurity.psm1') -Force -DisableNameChecking",
            "Import-Module (Join-Path $env:AEROONE_ROTATION_MODULE_ROOT 'Rotation.SecureIO.psm1') -Force -DisableNameChecking",
            body,
        )
    )
    if elevated:
        try:
            return _invoke_limited_probe(
                command,
                module_root=module_root,
                test_root=test_root,
            )
        finally:
            if test_root.exists():
                shutil.rmtree(test_root)
    return subprocess.run(
        ["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", command],
        check=False,
        capture_output=True,
        text=True,
        env=process_environment,
        timeout=30,
    )


def test_exact_acl_reapplication_does_not_require_security_privilege(tmp_path: Path) -> None:
    # Given: a protected current-SID and SYSTEM-only file created by an ordinary token.
    completed = _invoke_secure_io_probe(
        tmp_path,
        "\n".join(
            (
                "Import-Module (Join-Path $env:AEROONE_ROTATION_MODULE_ROOT 'Rotation.Security.psm1') -Force -DisableNameChecking",
                "$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())",
                "$elevated = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)",
                "if ($elevated) { throw 'probe-token-is-elevated' }",
                "New-RotationSecureDirectory -Path $env:AEROONE_ROTATION_TEST_ROOT",
                "$path = Join-Path $env:AEROONE_ROTATION_TEST_ROOT 'payload.bin'",
                "Publish-RotationSecureBytes -Bytes ([byte[]](1, 2, 3)) -DestinationPath $path",
                # When: the exact owner and DACL are re-applied without a SACL operation.
                "Set-SecureFileAcl -Path $path",
                # Then: the ordinary process can validate the final protected ACL.
                "Assert-SecureAcl -Path $path",
                "[Console]::Out.WriteLine('status=acl-ok elevated=false')",
            )
        ),
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "status=acl-ok elevated=false"


def test_no_backup_publish_atomically_swaps_identity_acl_and_digest(tmp_path: Path) -> None:
    # Given: an existing protected destination on the same volume as its secure temporary file.
    completed = _invoke_secure_io_probe(
        tmp_path,
        "\n".join(
            (
                "New-RotationSecureDirectory -Path $env:AEROONE_ROTATION_TEST_ROOT",
                "$path = Join-Path $env:AEROONE_ROTATION_TEST_ROOT 'payload.bin'",
                "Publish-RotationSecureBytes -Bytes ([byte[]](1, 2, 3)) -DestinationPath $path",
                "$before = Assert-SinglePhysicalFile -Path $path",
                # When: publish replaces the destination without a backup path.
                "Publish-RotationSecureBytes -Bytes ([byte[]](4, 5, 6)) -DestinationPath $path",
                # Then: the final object is a new contained identity with the exact ACL and digest.
                "$after = Assert-SinglePhysicalFile -Path $path",
                "$root = Get-PhysicalPathIdentity -Path $env:AEROONE_ROTATION_TEST_ROOT",
                "Assert-PhysicalContainment -RootIdentity $root -ChildIdentity $after",
                "Assert-RotationSecureFileAcl -Path $path",
                "if (Test-SamePhysicalObject -Left $before -Right $after) { throw 'replace-identity-not-swapped' }",
                "$sha = [Security.Cryptography.SHA256]::Create()",
                "try { $digest = [BitConverter]::ToString($sha.ComputeHash([IO.File]::ReadAllBytes($path))).Replace('-', '').ToLowerInvariant() } finally { $sha.Dispose() }",
                "$expected = [Security.Cryptography.SHA256]::Create()",
                "try { $expectedDigest = [BitConverter]::ToString($expected.ComputeHash([byte[]](4, 5, 6))).Replace('-', '').ToLowerInvariant() } finally { $expected.Dispose() }",
                "if ($digest -cne $expectedDigest) { throw 'replace-digest-mismatch' }",
                "[Console]::Out.WriteLine('status=replace-ok')",
            )
        ),
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "status=replace-ok"


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
