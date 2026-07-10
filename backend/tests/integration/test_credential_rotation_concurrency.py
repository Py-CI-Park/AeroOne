from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

from tests.rotation_harness import create_synthetic_workspace


def test_workspace_mutex_rejects_a_concurrent_rotation_process(tmp_path: Path) -> None:
    # Given: the workspace-scoped physical-identity mutex is already owned.
    workspace = create_synthetic_workspace(tmp_path)
    repository_root = Path(__file__).resolve().parents[3]
    process_environment = os.environ.copy()
    process_environment.update(
        {
            "AEROONE_PATH_MODULE": str(
                repository_root / "scripts" / "credential_rotation" / "Rotation.PathSecurity.psm1"
            ),
            "AEROONE_ROTATION_SCRIPT": str(
                repository_root / "scripts" / "rotate_aeroone_credentials.ps1"
            ),
            "AEROONE_WORKSPACE": str(workspace.root),
            "AEROONE_ROTATION_PYTHON": sys.executable,
            "TEMP": str(workspace.root.parent),
            "TMP": str(workspace.root.parent),
        }
    )
    holder = (
        "Import-Module $env:AEROONE_PATH_MODULE -Force;"
        "$identity=Get-PhysicalPathIdentity -Path $env:AEROONE_WORKSPACE;"
        "$raw=[Text.Encoding]::UTF8.GetBytes(("
        "'{0}:{1}' -f $identity.VolumeSerialNumber,$identity.FileId));"
        "$sha=[Security.Cryptography.SHA256]::Create();"
        "$digest=$sha.ComputeHash($raw);"
        r"$name='Local\AeroOne.CredentialRotation.'+"
        "([BitConverter]::ToString($digest).Replace('-','').ToLowerInvariant());"
        "$mutex=New-Object Threading.Mutex($false,$name);"
        "if(-not $mutex.WaitOne(0)){exit 99};"
        "try{"
        "& powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass "
        "-File $env:AEROONE_ROTATION_SCRIPT -TestMode "
        "-TestWorkspaceRoot $env:AEROONE_WORKSPACE -DryRun;"
        "exit $LASTEXITCODE"
        "}finally{$mutex.ReleaseMutex();$mutex.Dispose();$sha.Dispose();"
        "[Array]::Clear($raw,0,$raw.Length);[Array]::Clear($digest,0,$digest.Length)}"
    )

    # When: a second real PowerShell process starts for the same workspace.
    completed = subprocess.run(
        ["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", holder],
        check=False,
        capture_output=True,
        text=True,
        env=process_environment,
        timeout=30,
    )

    # Then: it fails before environment inspection instead of running concurrently.
    assert completed.returncode != 0
    assert "rotation-already-running" in completed.stderr
