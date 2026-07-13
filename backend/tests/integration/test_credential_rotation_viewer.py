from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess

from app.operations.credential_bundle import load_credential_bundle
from app.operations.windows_dpapi import DpapiPurpose, protect_for_current_user
from tests.rotation_harness import create_synthetic_workspace, invoke_rotation


VIEWER_PROCESS_TIMEOUT_SECONDS = 30
ACL_PROCESS_TIMEOUT_SECONDS = 30


def _invoke_viewer(workspace_root: Path) -> subprocess.CompletedProcess[str]:
    script = Path(__file__).resolve().parents[3] / "scripts" / "view_aeroone_credentials.ps1"
    process_environment = os.environ.copy()
    for key in tuple(process_environment):
        if key.startswith("AEROONE_ROTATION_"):
            del process_environment[key]
    process_environment["TEMP"] = str(workspace_root.parent)
    process_environment["TMP"] = str(workspace_root.parent)
    return subprocess.run(
        [
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            "-TestMode",
            "-TestWorkspaceRoot",
            str(workspace_root),
            "-ValidateOnly",
        ],
        check=False,
        capture_output=True,
        text=True,
        env=process_environment,
        timeout=VIEWER_PROCESS_TIMEOUT_SECONDS,
    )


def _workspace_files(root: Path) -> dict[Path, bytes]:
    return {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}


def test_validate_only_enforces_purpose_schema_acl_and_leaves_no_output(
    tmp_path: Path,
) -> None:
    # Given: a completed synthetic bundle at the only authorized secure path.
    workspace = create_synthetic_workspace(tmp_path)
    rotated = invoke_rotation(workspace)
    assert rotated.returncode == 0, rotated.stderr
    bundle_path = workspace.root / ".rotation-secure" / "credentials.dpapi"
    original_protected = bundle_path.read_bytes()
    bundle = load_credential_bundle(bundle_path)
    secret_values = [bundle.jwt_secret_key, *(item.password for item in bundle.users)]
    before = _workspace_files(workspace.root)

    # When: headless validation runs, then wrong-purpose, extra-schema, and ACL cases run.
    validated = _invoke_viewer(workspace.root)
    wrong_purpose = protect_for_current_user(
        bundle.model_dump_json().encode("utf-8"),
        DpapiPurpose.TEST_PAYLOAD,
    )
    bundle_path.write_bytes(wrong_purpose)
    purpose_rejected = _invoke_viewer(workspace.root)
    extra_schema = bundle.model_dump(mode="json")
    extra_schema["unexpected"] = True
    bundle_path.write_bytes(
        protect_for_current_user(
            json.dumps(extra_schema).encode("utf-8"),
            DpapiPurpose.CREDENTIAL_BUNDLE,
        )
    )
    schema_rejected = _invoke_viewer(workspace.root)
    bundle_path.write_bytes(original_protected)
    acl_changed = subprocess.run(
        ["icacls.exe", str(bundle_path), "/grant", "*S-1-5-32-545:R"],
        check=False,
        capture_output=True,
        text=True,
        timeout=ACL_PROCESS_TIMEOUT_SECONDS,
    )
    assert acl_changed.returncode == 0
    acl_rejected = _invoke_viewer(workspace.root)

    # Then: only the exact current-user artifact validates without plaintext side effects.
    assert validated.returncode == 0
    assert validated.stdout == ""
    assert validated.stderr == ""
    assert _workspace_files(workspace.root) == before
    for rejected in (purpose_rejected, schema_rejected, acl_rejected):
        assert rejected.returncode != 0
        combined_output = rejected.stdout + rejected.stderr
        assert all(secret not in combined_output for secret in secret_values)


def test_wpf_viewer_contract_is_masked_and_clipboard_owned() -> None:
    # Given: the checked-in headless entrypoint and WPF implementation are inspected.
    root = Path(__file__).resolve().parents[3]
    entrypoint = (root / "scripts" / "view_aeroone_credentials.ps1").read_text(encoding="utf-8")
    viewer = (
        root / "scripts" / "credential_rotation" / "Rotation.CredentialViewer.psm1"
    ).read_text(encoding="utf-8")
    clipboard = (
        root / "scripts" / "credential_rotation" / "Rotation.Clipboard.psm1"
    ).read_text(encoding="utf-8")

    # When: the security-sensitive UI and output surface are enumerated statically.
    combined = entrypoint + viewer + clipboard

    # Then: masking, account selection, owned clipboard clearing, and no plaintext sinks remain.
    for required in (
        "ValidateOnly",
        "PresentationFramework",
        "PasswordBox",
        "ComboBox",
        "DispatcherTimer",
        "FromSeconds(30)",
        "Clipboard",
        "GetData",
        "Clear",
        "ExcludeClipboardContentFromMonitorProcessing",
        "CanIncludeInClipboardHistory",
        "CanUploadToCloudClipboard",
        "Add_Closing",
        "RetryClipboardClear",
        "Set-RotationSecureClipboard",
        "Rotation.Clipboard.psm1",
        'Height="580"',
        'Visibility="Collapsed"',
    ):
        assert required in combined
    for forbidden in (
        "Write-Output",
        "Write-Host",
        "Start-Transcript",
        "Out-File",
        "Set-Content",
        "Add-Content",
    ):
        assert forbidden not in combined


def test_copied_viewer_validate_only_proves_its_own_canonical_entrypoint(
    tmp_path: Path,
) -> None:
    # Given: a production-like copied script tree and an empty synthetic user profile.
    repository_root = Path(__file__).resolve().parents[3]
    copied_root = tmp_path / "copied-tree"
    shutil.copytree(repository_root / "scripts", copied_root / "scripts")
    copied_viewer = copied_root / "scripts" / "view_aeroone_credentials.ps1"
    user_profile = tmp_path / "profile"
    user_profile.mkdir()
    process_environment = os.environ.copy()
    process_environment["USERPROFILE"] = str(user_profile)

    # When: ValidateOnly enters through the copied canonical viewer path.
    completed = subprocess.run(
        [
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(copied_viewer),
            "-ValidateOnly",
        ],
        check=False,
        capture_output=True,
        text=True,
        env=process_environment,
        timeout=VIEWER_PROCESS_TIMEOUT_SECONDS,
    )

    # Then: viewer provenance passes before the expected absent credential root is reported.
    assert completed.returncode != 0
    assert "credential-viewer-root-missing" in completed.stderr
    assert "provenance-" not in completed.stderr
