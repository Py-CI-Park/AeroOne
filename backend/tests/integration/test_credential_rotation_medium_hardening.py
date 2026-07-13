from __future__ import annotations

import hashlib
import json
from pathlib import Path
from uuid import uuid4

from tests.rotation_harness import create_synthetic_workspace, invoke_rotation


def _manifest_checksum(manifest: dict[str, object]) -> str:
    payload = {
        key: manifest[key]
        for key in (
            "schema_version",
            "rotation_id",
            "database_id",
            "retention",
            "entries",
        )
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("ascii")
    return hashlib.sha256(canonical).hexdigest()


def test_abandoned_bootstrap_rejects_insecure_owned_temp_before_delete(
    tmp_path: Path,
) -> None:
    workspace = create_synthetic_workspace(tmp_path)
    crashed = invoke_rotation(
        workspace,
        internal_crashpoint="crash_after_secure_root_init",
    )
    assert crashed.returncode != 0
    orphan = (
        workspace.root
        / ".rotation-secure"
        / "pending"
        / ".aeroone-rotation-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.tmp"
    )
    orphan.write_bytes(b"synthetic-orphan")

    resumed = invoke_rotation(workspace)

    assert resumed.returncode != 0
    assert "insecure-acl" in resumed.stderr
    assert orphan.read_bytes() == b"synthetic-orphan"


def test_manifest_rejects_extra_checksum_and_foreign_journal_binding(
    tmp_path: Path,
) -> None:
    workspace = create_synthetic_workspace(tmp_path)
    completed = invoke_rotation(workspace)
    assert completed.returncode == 0, completed.stderr
    manifest_path = workspace.root / ".rotation-secure" / "quarantine" / "quarantine-manifest.json"
    original = manifest_path.read_bytes()
    manifest = json.loads(original)
    assert set(manifest) == {
        "schema_version",
        "rotation_id",
        "database_id",
        "retention",
        "entries",
        "checksum_sha256",
    }
    root_before = (workspace.root / ".env").read_bytes()
    backend_before = (workspace.root / "backend" / ".env").read_bytes()

    extra = manifest | {"unexpected": True}
    manifest_path.write_text(json.dumps(extra), encoding="utf-8")
    extra_rejected = invoke_rotation(workspace)
    manifest_path.write_bytes(original)

    checksum = json.loads(original)
    checksum["entries"][0]["sha256"] = "f" * 64
    manifest_path.write_text(json.dumps(checksum), encoding="utf-8")
    checksum_rejected = invoke_rotation(workspace)
    manifest_path.write_bytes(original)

    foreign = json.loads(original)
    foreign["rotation_id"] = str(uuid4())
    foreign["checksum_sha256"] = _manifest_checksum(foreign)
    manifest_path.write_text(json.dumps(foreign), encoding="utf-8")
    binding_rejected = invoke_rotation(workspace)

    assert extra_rejected.returncode != 0
    assert "quarantine-manifest-mismatch" in extra_rejected.stderr
    assert checksum_rejected.returncode != 0
    assert "quarantine-manifest-mismatch" in checksum_rejected.stderr
    assert binding_rejected.returncode != 0
    assert "quarantine-manifest-binding-mismatch" in binding_rejected.stderr
    assert (workspace.root / ".env").read_bytes() == root_before
    assert (workspace.root / "backend" / ".env").read_bytes() == backend_before
