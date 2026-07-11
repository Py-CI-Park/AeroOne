from __future__ import annotations

import os
from pathlib import Path
import secrets
import subprocess

from tests.rotation_harness import create_synthetic_workspace, has_exact_secure_acl, invoke_rotation


def _invoke_secure_io_probe(tmp_path: Path, body: str) -> subprocess.CompletedProcess[str]:
    module_root = Path(__file__).resolve().parents[3] / "scripts" / "credential_rotation"
    process_environment = os.environ.copy()
    process_environment["AEROONE_ROTATION_MODULE_ROOT"] = str(module_root)
    process_environment["AEROONE_ROTATION_TEST_ROOT"] = str(tmp_path / "secure-root")
    command = "\n".join(
        (
            "$ErrorActionPreference = 'Stop'",
            "Import-Module (Join-Path $env:AEROONE_ROTATION_MODULE_ROOT 'Rotation.PathSecurity.psm1') -Force -DisableNameChecking",
            "Import-Module (Join-Path $env:AEROONE_ROTATION_MODULE_ROOT 'Rotation.SecureIO.psm1') -Force -DisableNameChecking",
            body,
        )
    )
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
