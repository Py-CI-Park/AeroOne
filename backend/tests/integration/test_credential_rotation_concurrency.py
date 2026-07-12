from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

from tests.rotation_harness import create_synthetic_workspace


def test_workspace_mutex_name_and_acl_are_machine_global_and_exact(tmp_path: Path) -> None:
    # Given: the production lock module receives a synthetic physical workspace identity.
    workspace = create_synthetic_workspace(tmp_path)
    repository_root = Path(__file__).resolve().parents[3]
    process_environment = os.environ.copy()
    process_environment.update(
        {
            "AEROONE_PATH_MODULE": str(
                repository_root / "scripts" / "credential_rotation" / "Rotation.PathSecurity.psm1"
            ),
            "AEROONE_LOCK_MODULE": str(
                repository_root / "scripts" / "credential_rotation" / "Rotation.ProcessLock.psm1"
            ),
            "AEROONE_WORKSPACE": str(workspace.root),
        }
    )
    probe = (
        "Import-Module $env:AEROONE_PATH_MODULE -Force;"
        "Import-Module $env:AEROONE_LOCK_MODULE -Force;"
        "$name=Get-RotationMutexName -WorkspaceRoot $env:AEROONE_WORKSPACE;"
        "$mutex=Enter-RotationMutex -WorkspaceRoot $env:AEROONE_WORKSPACE;"
        "if($null -eq $mutex){exit 91};"
        "try{"
        "$acl=$mutex.GetAccessControl();"
        "$current=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value;"
        "$owner=$acl.GetOwner([Security.Principal.SecurityIdentifier]).Value;"
        "$rules=@($acl.GetAccessRules($true,$false,[Security.Principal.SecurityIdentifier]));"
        "$sids=@($rules|ForEach-Object{$_.IdentityReference.Value}|Sort-Object);"
        "$expected=@($current,'S-1-5-18')|Sort-Object;"
        "$valid=$name.StartsWith('Global\\',[StringComparison]::Ordinal)-and"
        "$acl.AreAccessRulesProtected-and$owner-eq$current-and$rules.Count-eq2-and"
        "@(Compare-Object $sids $expected).Count-eq0-and"
        "@($rules|Where-Object{$_.AccessControlType-ne'Allow'-or"
        "($_.MutexRights-band[Security.AccessControl.MutexRights]::FullControl)-ne"
        "[Security.AccessControl.MutexRights]::FullControl}).Count-eq0;"
        "if(-not$valid){[Console]::Error.WriteLine('mutex-contract-invalid');exit 92};"
        "[Console]::Out.WriteLine($name)"
        "}finally{$mutex.ReleaseMutex();$mutex.Dispose()}"
    )

    # When: a real PowerShell process creates and inspects the named mutex.
    completed = subprocess.run(
        ["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", probe],
        check=False,
        capture_output=True,
        text=True,
        env=process_environment,
        timeout=30,
    )

    # Then: the namespace is machine-global and only current SID plus SYSTEM have full control.
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip().startswith("Global\\AeroOne.CredentialRotation.")


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
            "AEROONE_LOCK_MODULE": str(
                repository_root / "scripts" / "credential_rotation" / "Rotation.ProcessLock.psm1"
            ),
            "AEROONE_WORKSPACE": str(workspace.root),
            "AEROONE_ROTATION_PYTHON": sys.executable,
            "TEMP": str(workspace.root.parent),
            "TMP": str(workspace.root.parent),
        }
    )
    holder = (
        "Import-Module $env:AEROONE_PATH_MODULE -Force;"
        "Import-Module $env:AEROONE_LOCK_MODULE -Force;"
        "$mutex=Enter-RotationMutex -WorkspaceRoot $env:AEROONE_WORKSPACE;"
        "if($null-eq$mutex){exit 99};"
        "try{"
        "& powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass "
        "-File $env:AEROONE_ROTATION_SCRIPT -TestMode "
        "-TestWorkspaceRoot $env:AEROONE_WORKSPACE -DryRun;"
        "exit $LASTEXITCODE"
        "}finally{$mutex.ReleaseMutex();$mutex.Dispose()}"
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
