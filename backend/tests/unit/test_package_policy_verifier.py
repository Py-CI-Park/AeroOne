from __future__ import annotations

import zipfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from app.operations.package_policy_contracts import (
    AuthenticodeSignatureInfo,
    ForbiddenCategory,
    ManifestEntry,
    ManifestProvenance,
    PackageManifest,
    PackagePolicyError,
    PackagePolicyErrorCode,
    PolicyDocument,
    RequiredInstaller,
)
from app.operations.package_policy_verifier import (
    RawEntry,
    compute_sha256,
    validate_raw_entries,
    verify_post_zip,
    verify_pre_stage,
)

_PROVENANCE = ManifestProvenance(
    origin="AeroOne",
    tag="v1.13.0-test",
    commit="deadbeefcafefeed0000000000000000000000",
    policy="release-qa@1",
)

_PY_INSTALLER = "python-3.12.7-amd64.exe"
_NODE_INSTALLER = "node-v20.18.0-x64.msi"
_PY_INSTALLER_CONTENT = b"fixture-python-installer-bytes"
_NODE_INSTALLER_CONTENT = b"fixture-node-installer-bytes"
_PY_THUMBPRINT = "11111111111111111111111111111111111111AA"
_NODE_THUMBPRINT = "22222222222222222222222222222222222222BB"
_PY_SUBJECT = "Fixture Python Foundation"
_NODE_SUBJECT = "Fixture OpenJS Foundation"


@dataclass
class Fixture:
    root: Path
    manifest: PackageManifest
    policy: PolicyDocument
    provenance: ManifestProvenance
    signatures: dict[str, AuthenticodeSignatureInfo]
    files: dict[str, Path] = field(default_factory=dict)


def _write(root: Path, rel_posix: str, content: bytes) -> Path:
    target = root / rel_posix
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return target


def _build_fixture(tmp_path: Path) -> Fixture:
    root = tmp_path / "stage"
    root.mkdir()

    files = {
        "backend/app/__init__.py": b"",
        "backend/requirements.txt": b"fastapi\n",
        "frontend/package.json": b'{"name": "aeroone-frontend"}\n',
        "docs/README.md": b"# docs\n",
        "scripts/tool.py": b"print('tool')\n",
        f"offline_assets/installers/{_PY_INSTALLER}": _PY_INSTALLER_CONTENT,
        f"offline_assets/installers/{_NODE_INSTALLER}": _NODE_INSTALLER_CONTENT,
    }
    paths = {rel: _write(root, rel, content) for rel, content in files.items()}

    manifest_entries = tuple(
        ManifestEntry(
            path=rel,
            sha256=compute_sha256(path),
            origin=_PROVENANCE.origin,
            tag=_PROVENANCE.tag,
            commit=_PROVENANCE.commit,
            policy=_PROVENANCE.policy,
        )
        for rel, path in paths.items()
    )

    policy = PolicyDocument(
        policy_version=1,
        profile="test-profile",
        allow_top_level_entries=("backend", "frontend", "docs", "packaging", "scripts", "offline_assets"),
        forbidden_categories=(
            ForbiddenCategory(
                category="env-secret",
                patterns=("**/.env", ".env"),
                allow_patterns=("**/.env.example", ".env.example"),
            ),
            ForbiddenCategory(category="database", patterns=("**/*.db", "backend/data/**")),
            ForbiddenCategory(category="storage-runtime", patterns=("storage/**",)),
            ForbiddenCategory(category="agent-state", patterns=(".gjc/**", ".omo/**", ".ug-*")),
            ForbiddenCategory(category="dev-artifact", patterns=("**/__pycache__/**", "dist/**")),
        ),
        required_installers=(
            RequiredInstaller(
                filename=_PY_INSTALLER,
                sha256=compute_sha256(paths[f"offline_assets/installers/{_PY_INSTALLER}"]),
                authenticode_thumbprint=_PY_THUMBPRINT,
                authenticode_subject=_PY_SUBJECT,
            ),
            RequiredInstaller(
                filename=_NODE_INSTALLER,
                sha256=compute_sha256(paths[f"offline_assets/installers/{_NODE_INSTALLER}"]),
                authenticode_thumbprint=_NODE_THUMBPRINT,
                authenticode_subject=_NODE_SUBJECT,
            ),
        ),
    )

    signatures = {
        _PY_INSTALLER: AuthenticodeSignatureInfo(status="Valid", thumbprint=_PY_THUMBPRINT, subject=_PY_SUBJECT),
        _NODE_INSTALLER: AuthenticodeSignatureInfo(
            status="Valid", thumbprint=_NODE_THUMBPRINT, subject=_NODE_SUBJECT
        ),
    }

    return Fixture(
        root=root,
        manifest=PackageManifest(entries=manifest_entries),
        policy=policy,
        provenance=_PROVENANCE,
        signatures=signatures,
        files=paths,
    )


def _zip_stage(fixture: Fixture, zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w") as archive:
        for entry in fixture.manifest.entries:
            archive.write(fixture.root / entry.path, entry.path)


# ---------------------------------------------------------------------------
# Happy path: pre-stage + post-ZIP both pass, entry counts and digests 1:1.
# ---------------------------------------------------------------------------


def test_pre_stage_and_post_zip_pass_for_a_compliant_package(tmp_path: Path) -> None:
    fixture = _build_fixture(tmp_path)

    pre_result = verify_pre_stage(
        fixture.root, fixture.manifest, fixture.policy, fixture.provenance, fixture.signatures
    )

    assert pre_result.entry_count == len(fixture.manifest.entries)
    assert pre_result.installer_count == 2
    assert set(pre_result.entry_digests) == {entry.path for entry in fixture.manifest.entries}

    zip_path = tmp_path / "AeroOne-offline-test.zip"
    _zip_stage(fixture, zip_path)

    post_result = verify_post_zip(zip_path, fixture.manifest, pre_result.entry_digests)

    assert post_result.entry_count == pre_result.entry_count == len(fixture.manifest.entries)


def test_env_example_is_allowed_while_real_env_is_forbidden(tmp_path: Path) -> None:
    fixture = _build_fixture(tmp_path)
    example_path = _write(fixture.root, "backend/.env.example", b"KEY=placeholder\n")
    example_entry = ManifestEntry(
        path="backend/.env.example",
        sha256=compute_sha256(example_path),
        origin=fixture.provenance.origin,
        tag=fixture.provenance.tag,
        commit=fixture.provenance.commit,
        policy=fixture.provenance.policy,
    )
    fixture.manifest = PackageManifest(entries=(*fixture.manifest.entries, example_entry))

    pre_result = verify_pre_stage(
        fixture.root, fixture.manifest, fixture.policy, fixture.provenance, fixture.signatures
    )
    assert pre_result.entry_count == len(fixture.manifest.entries)

    _write(fixture.root, "backend/.env", b"KEY=real-secret-value\n")
    with pytest.raises(PackagePolicyError) as excinfo:
        verify_pre_stage(fixture.root, fixture.manifest, fixture.policy, fixture.provenance, fixture.signatures)
    assert excinfo.value.code == PackagePolicyErrorCode.FORBIDDEN_ENV_SECRET


# ---------------------------------------------------------------------------
# Failure paths: path safety at the raw-entry validation layer.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "case_name,build_entries,expected_code",
    [
        (
            "path-traversal-resolves-outside-root",
            lambda root_resolved: [RawEntry("outside.txt", False, root_resolved.parent / "outside.txt")],
            PackagePolicyErrorCode.PATH_TRAVERSAL,
        ),
        (
            "path-traversal-literal-dotdot-segment",
            lambda root_resolved: [
                RawEntry("backend/../../escape.txt", False, root_resolved / "backend/../../escape.txt")
            ],
            PackagePolicyErrorCode.PATH_TRAVERSAL,
        ),
        (
            "symlink-entry-rejected",
            lambda root_resolved: [RawEntry("backend/app/link.py", True, root_resolved / "backend/app/link.py")],
            PackagePolicyErrorCode.SYMLINK_ENTRY,
        ),
        (
            "case-insensitive-duplicate-entry",
            lambda root_resolved: [
                RawEntry("backend/App/x.py", False, root_resolved / "backend/App/x.py"),
                RawEntry("backend/app/x.py", False, root_resolved / "backend/app/x.py"),
            ],
            PackagePolicyErrorCode.DUPLICATE_ENTRY,
        ),
    ],
)
def test_validate_raw_entries_rejects_unsafe_paths(
    tmp_path: Path,
    case_name: str,
    build_entries: Callable[[Path], list[RawEntry]],
    expected_code: PackagePolicyErrorCode,
) -> None:
    root_resolved = (tmp_path / "root").resolve()
    entries = build_entries(root_resolved)
    with pytest.raises(PackagePolicyError) as excinfo:
        validate_raw_entries(entries, root_resolved)
    assert excinfo.value.code == expected_code, case_name


# ---------------------------------------------------------------------------
# Failure paths: fail-closed allow-list, manifest integrity, installer trust.
# ---------------------------------------------------------------------------


def _inject_real_env(fixture: Fixture) -> None:
    _write(fixture.root, "backend/.env", b"KEY=real-secret-value\n")


def _inject_database_file(fixture: Fixture) -> None:
    _write(fixture.root, "backend/data/aeroone.db", b"sqlite-fixture-bytes")


def _inject_storage_runtime_file(fixture: Fixture) -> None:
    _write(fixture.root, "storage/markdown/newsletters/sample.md", b"# sample\n")


def _drop_manifest_entry(fixture: Fixture) -> None:
    fixture.manifest = PackageManifest(entries=fixture.manifest.entries[:-1])


def _duplicate_manifest_entry(fixture: Fixture) -> None:
    duplicate = fixture.manifest.entries[0]
    fixture.manifest = PackageManifest(entries=(*fixture.manifest.entries, duplicate))


def _corrupt_installer_with_self_consistent_manifest(fixture: Fixture) -> None:
    installer_path = fixture.root / "offline_assets/installers" / _PY_INSTALLER
    installer_path.write_bytes(_PY_INSTALLER_CONTENT + b"-tampered")
    new_hash = compute_sha256(installer_path)
    updated_entries = tuple(
        ManifestEntry(
            path=entry.path,
            sha256=new_hash,
            origin=entry.origin,
            tag=entry.tag,
            commit=entry.commit,
            policy=entry.policy,
        )
        if entry.path.endswith(_PY_INSTALLER)
        else entry
        for entry in fixture.manifest.entries
    )
    fixture.manifest = PackageManifest(entries=updated_entries)


def _wrong_installer_thumbprint(fixture: Fixture) -> None:
    fixture.signatures[_PY_INSTALLER] = AuthenticodeSignatureInfo(
        status="Valid", thumbprint="0" * 40, subject=_PY_SUBJECT
    )


def _wrong_installer_subject(fixture: Fixture) -> None:
    fixture.signatures[_NODE_INSTALLER] = AuthenticodeSignatureInfo(
        status="Valid", thumbprint=_NODE_THUMBPRINT, subject="Untrusted Publisher"
    )


def _unsigned_installer(fixture: Fixture) -> None:
    fixture.signatures[_PY_INSTALLER] = AuthenticodeSignatureInfo(status="NotSigned", thumbprint="", subject="")


def _new_top_level_outside_allow_list(fixture: Fixture) -> None:
    _write(fixture.root, "vendor/unexpected.txt", b"not on the allow-list\n")


@pytest.mark.parametrize(
    "case_name,mutate,expected_code",
    [
        ("real-dot-env-file", _inject_real_env, PackagePolicyErrorCode.FORBIDDEN_ENV_SECRET),
        ("database-file", _inject_database_file, PackagePolicyErrorCode.FORBIDDEN_DATABASE),
        ("storage-runtime-file", _inject_storage_runtime_file, PackagePolicyErrorCode.FORBIDDEN_STORAGE_RUNTIME),
        ("manifest-missing-entry-on-disk", _drop_manifest_entry, PackagePolicyErrorCode.MANIFEST_EXTRA_ENTRY),
        ("manifest-duplicate-entry", _duplicate_manifest_entry, PackagePolicyErrorCode.DUPLICATE_ENTRY),
        (
            "installer-hash-mismatch-vs-policy",
            _corrupt_installer_with_self_consistent_manifest,
            PackagePolicyErrorCode.INSTALLER_HASH_MISMATCH,
        ),
        (
            "installer-thumbprint-mismatch",
            _wrong_installer_thumbprint,
            PackagePolicyErrorCode.INSTALLER_THUMBPRINT_MISMATCH,
        ),
        ("installer-subject-mismatch", _wrong_installer_subject, PackagePolicyErrorCode.INSTALLER_SUBJECT_MISMATCH),
        ("installer-not-signed", _unsigned_installer, PackagePolicyErrorCode.INSTALLER_SIGNATURE_INVALID),
        (
            "top-level-outside-allow-list",
            _new_top_level_outside_allow_list,
            PackagePolicyErrorCode.TOPLEVEL_NOT_ALLOWED,
        ),
    ],
)
def test_verify_pre_stage_is_fail_closed(
    tmp_path: Path,
    case_name: str,
    mutate: Callable[[Fixture], None],
    expected_code: PackagePolicyErrorCode,
) -> None:
    fixture = _build_fixture(tmp_path)
    mutate(fixture)

    with pytest.raises(PackagePolicyError) as excinfo:
        verify_pre_stage(fixture.root, fixture.manifest, fixture.policy, fixture.provenance, fixture.signatures)

    assert excinfo.value.code == expected_code, case_name


# ---------------------------------------------------------------------------
# Failure paths: post-ZIP verification without extraction.
# ---------------------------------------------------------------------------


def test_verify_post_zip_rejects_traversal_entry_name(tmp_path: Path) -> None:
    fixture = _build_fixture(tmp_path)
    pre_result = verify_pre_stage(
        fixture.root, fixture.manifest, fixture.policy, fixture.provenance, fixture.signatures
    )

    zip_path = tmp_path / "malicious.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        for entry in fixture.manifest.entries:
            archive.write(fixture.root / entry.path, entry.path)
        archive.writestr("../evil.txt", b"escape")

    with pytest.raises(PackagePolicyError) as excinfo:
        verify_post_zip(zip_path, fixture.manifest, pre_result.entry_digests)
    assert excinfo.value.code == PackagePolicyErrorCode.PATH_TRAVERSAL


def test_verify_post_zip_rejects_digest_drift_from_pre_stage(tmp_path: Path) -> None:
    fixture = _build_fixture(tmp_path)
    pre_result = verify_pre_stage(
        fixture.root, fixture.manifest, fixture.policy, fixture.provenance, fixture.signatures
    )

    zip_path = tmp_path / "drifted.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        for entry in fixture.manifest.entries:
            if entry.path == "backend/requirements.txt":
                archive.writestr(entry.path, b"tampered-after-signing\n")
            else:
                archive.write(fixture.root / entry.path, entry.path)

    with pytest.raises(PackagePolicyError) as excinfo:
        verify_post_zip(zip_path, fixture.manifest, pre_result.entry_digests)
    assert excinfo.value.code == PackagePolicyErrorCode.POST_ZIP_DIGEST_MISMATCH


def test_verify_post_zip_rejects_entry_missing_from_manifest(tmp_path: Path) -> None:
    fixture = _build_fixture(tmp_path)
    pre_result = verify_pre_stage(
        fixture.root, fixture.manifest, fixture.policy, fixture.provenance, fixture.signatures
    )

    zip_path = tmp_path / "incomplete.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        for entry in fixture.manifest.entries[:-1]:
            archive.write(fixture.root / entry.path, entry.path)

    with pytest.raises(PackagePolicyError) as excinfo:
        verify_post_zip(zip_path, fixture.manifest, pre_result.entry_digests)
    assert excinfo.value.code == PackagePolicyErrorCode.MANIFEST_MISSING_ENTRY
