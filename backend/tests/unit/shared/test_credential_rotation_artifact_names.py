from __future__ import annotations

from pathlib import Path


def test_final_credential_bundle_name_is_release_neutral() -> None:
    # Given: every active rotation runtime, operator document, and focused test.
    root = Path(__file__).resolve().parents[4]
    paths = (
        root / "scripts" / "rotate_aeroone_credentials.ps1",
        root / "scripts" / "credential_rotation" / "Rotation.Reconciliation.psm1",
        root / "scripts" / "credential_rotation" / "Rotation.CredentialViewer.psm1",
        root / "README.md",
        root / "docs" / "INDEX.md",
        root / "docs" / "CLOSED_NETWORK_GUIDE.md",
        root / "docs" / "runbook" / "credential-rotation.md",
        *(root / "backend" / "tests").rglob("test_credential_rotation*.py"),
    )
    release_pinned = "1.12.3-" + "credentials.dpapi"

    # When: release-pinned final bundle references are collected.
    violations = tuple(
        str(path.relative_to(root))
        for path in paths
        if release_pinned in path.read_text(encoding="utf-8")
    )

    # Then: the durable artifact contract is independent of a withdrawn release.
    assert violations == ()


def test_recovery_artifact_name_is_rotation_bound() -> None:
    # Given: active rotation runtime, focused tests, and operator documentation.
    root = Path(__file__).resolve().parents[4]
    paths = (
        *(root / "scripts").rglob("*.ps1"),
        *(root / "scripts").rglob("*.psm1"),
        *(root / "backend" / "tests").rglob("test_credential_rotation*.py"),
        root / "docs" / "runbook" / "credential-rotation.md",
    )
    fixed_recovery = "aeroone-db-before-" + "rotation.dpapi"

    # When: fixed recovery artifact references are collected.
    violations = tuple(
        str(path.relative_to(root))
        for path in paths
        if fixed_recovery in path.read_text(encoding="utf-8")
    )

    # Then: every final recovery name remains bound to its rotation UUID.
    assert violations == ()
