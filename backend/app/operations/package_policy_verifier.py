from __future__ import annotations

import hashlib
import json
import os
import re
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from app.operations.package_policy_contracts import (
    AuthenticodeSignatureInfo,
    ManifestEntry,
    ManifestProvenance,
    PackageManifest,
    PackagePolicyError,
    PackagePolicyErrorCode,
    PolicyDocument,
    PostZipResult,
    PreStageResult,
)

_HASH_CHUNK_SIZE = 1024 * 1024


def load_policy(policy_path: Path) -> PolicyDocument:
    raw = json.loads(policy_path.read_text(encoding="utf-8"))
    return PolicyDocument.model_validate(raw)


def load_manifest(manifest_path: Path) -> PackageManifest:
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    return PackageManifest.model_validate(raw)


def _pattern_to_regex(pattern: str) -> re.Pattern[str]:
    out: list[str] = []
    i = 0
    n = len(pattern)
    while i < n:
        if pattern[i : i + 2] == "**":
            out.append(".*")
            i += 2
            if i < n and pattern[i] == "/":
                out.append("/?")
                i += 1
            continue
        c = pattern[i]
        if c == "*":
            out.append("[^/]*")
        elif c == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(c))
        i += 1
    return re.compile("^" + "".join(out) + "$")


def _match_any(rel_posix: str, patterns: Sequence[str]) -> bool:
    return any(_pattern_to_regex(pattern).match(rel_posix) for pattern in patterns)


def classify_forbidden(rel_posix: str, policy: PolicyDocument) -> PackagePolicyErrorCode | None:
    category_codes = {
        "env-secret": PackagePolicyErrorCode.FORBIDDEN_ENV_SECRET,
        "database": PackagePolicyErrorCode.FORBIDDEN_DATABASE,
        "storage-runtime": PackagePolicyErrorCode.FORBIDDEN_STORAGE_RUNTIME,
        "agent-state": PackagePolicyErrorCode.FORBIDDEN_AGENT_STATE,
        "dev-artifact": PackagePolicyErrorCode.FORBIDDEN_DEV_ARTIFACT,
    }
    for forbidden in policy.forbidden_categories:
        if _match_any(rel_posix, forbidden.allow_patterns):
            continue
        if _match_any(rel_posix, forbidden.patterns):
            code = category_codes.get(forbidden.category)
            if code is None:
                raise PackagePolicyError(PackagePolicyErrorCode.TOPLEVEL_NOT_ALLOWED, "unknown-category")
            return code
    return None


def check_top_level_allowed(rel_posix: str, policy: PolicyDocument) -> bool:
    top_level = rel_posix.split("/", 1)[0]
    return top_level in policy.allow_top_level_entries


def _to_posix(root: Path, absolute: Path) -> str:
    return absolute.relative_to(root).as_posix()


def compute_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_HASH_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class RawEntry:
    rel_posix: str
    is_symlink: bool
    resolved: Path


def _iter_raw_entries(root: Path) -> list[RawEntry]:
    """Walk a staging tree without following symlinked directories, so that a
    symlink is always reported as its own entry rather than transparently
    expanded.
    """
    entries: list[RawEntry] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirpath_p = Path(dirpath)
        for dirname in dirnames:
            dir_path = dirpath_p / dirname
            if dir_path.is_symlink():
                rel_posix = _to_posix(root, dir_path)
                try:
                    resolved = dir_path.resolve()
                except OSError:
                    resolved = dir_path
                entries.append(RawEntry(rel_posix, True, resolved))
        for filename in filenames:
            file_path = dirpath_p / filename
            rel_posix = _to_posix(root, file_path)
            is_symlink = file_path.is_symlink()
            try:
                resolved = file_path.resolve()
            except OSError:
                resolved = file_path
            entries.append(RawEntry(rel_posix, is_symlink, resolved))
    return sorted(entries, key=lambda entry: entry.rel_posix)


def validate_raw_entries(entries: Sequence[RawEntry], root_resolved: Path) -> list[str]:
    """Pure fail-closed validation of already-collected entries: rejects
    symlinks, path traversal (resolved path escaping the root, or a literal
    ``..`` segment), and case-insensitive duplicate paths.
    """
    validated: list[str] = []
    seen_case_insensitive: set[str] = set()

    for entry in entries:
        if entry.is_symlink:
            raise PackagePolicyError(PackagePolicyErrorCode.SYMLINK_ENTRY)

        if ".." in entry.rel_posix.split("/"):
            raise PackagePolicyError(PackagePolicyErrorCode.PATH_TRAVERSAL)

        try:
            entry.resolved.relative_to(root_resolved)
        except ValueError as exc:
            raise PackagePolicyError(PackagePolicyErrorCode.PATH_TRAVERSAL) from exc

        lowered = entry.rel_posix.lower()
        if lowered in seen_case_insensitive:
            raise PackagePolicyError(PackagePolicyErrorCode.DUPLICATE_ENTRY)
        seen_case_insensitive.add(lowered)
        validated.append(entry.rel_posix)

    return validated


def walk_stage_entries(root: Path) -> list[str]:
    root_resolved = root.resolve()
    return validate_raw_entries(_iter_raw_entries(root), root_resolved)


def verify_stage_policy(entries: Sequence[str], policy: PolicyDocument) -> None:
    for rel_posix in entries:
        forbidden_code = classify_forbidden(rel_posix, policy)
        if forbidden_code is not None:
            raise PackagePolicyError(forbidden_code)
        if not check_top_level_allowed(rel_posix, policy):
            raise PackagePolicyError(PackagePolicyErrorCode.TOPLEVEL_NOT_ALLOWED)


def verify_manifest_one_to_one(manifest_entries: Sequence[ManifestEntry], actual_paths: Sequence[str]) -> None:
    manifest_paths = {entry.path for entry in manifest_entries}
    if len(manifest_paths) != len(manifest_entries):
        raise PackagePolicyError(PackagePolicyErrorCode.DUPLICATE_ENTRY)

    actual_set = set(actual_paths)
    if len(actual_set) != len(actual_paths):
        raise PackagePolicyError(PackagePolicyErrorCode.DUPLICATE_ENTRY)

    if manifest_paths - actual_set:
        raise PackagePolicyError(PackagePolicyErrorCode.MANIFEST_MISSING_ENTRY)
    if actual_set - manifest_paths:
        raise PackagePolicyError(PackagePolicyErrorCode.MANIFEST_EXTRA_ENTRY)


def verify_manifest_hashes(manifest_entries: Sequence[ManifestEntry], root: Path) -> dict[str, str]:
    digests: dict[str, str] = {}
    for entry in manifest_entries:
        actual_hash = compute_sha256(root / entry.path)
        if actual_hash != entry.sha256:
            raise PackagePolicyError(PackagePolicyErrorCode.MANIFEST_HASH_MISMATCH)
        digests[entry.path] = actual_hash
    return digests


def verify_manifest_provenance(manifest_entries: Sequence[ManifestEntry], expected: ManifestProvenance) -> None:
    for entry in manifest_entries:
        if (
            entry.origin != expected.origin
            or entry.tag != expected.tag
            or entry.commit != expected.commit
            or entry.policy != expected.policy
        ):
            raise PackagePolicyError(PackagePolicyErrorCode.MANIFEST_PROVENANCE_MISMATCH)


def verify_installers(
    manifest_entries: Sequence[ManifestEntry],
    root: Path,
    policy: PolicyDocument,
    signature_lookup: Mapping[str, AuthenticodeSignatureInfo],
) -> int:
    entries_by_basename: dict[str, ManifestEntry] = {}
    for entry in manifest_entries:
        entries_by_basename.setdefault(Path(entry.path).name, entry)

    for required in policy.required_installers:
        entry = entries_by_basename.get(required.filename)
        if entry is None:
            raise PackagePolicyError(PackagePolicyErrorCode.INSTALLER_MISSING)

        actual_hash = compute_sha256(root / entry.path)
        if actual_hash != required.sha256 or entry.sha256 != required.sha256:
            raise PackagePolicyError(PackagePolicyErrorCode.INSTALLER_HASH_MISMATCH)

        signature = signature_lookup.get(required.filename)
        if signature is None or signature.status != "Valid":
            raise PackagePolicyError(PackagePolicyErrorCode.INSTALLER_SIGNATURE_INVALID)
        if signature.thumbprint.upper() != required.authenticode_thumbprint.upper():
            raise PackagePolicyError(PackagePolicyErrorCode.INSTALLER_THUMBPRINT_MISMATCH)
        if signature.subject != required.authenticode_subject:
            raise PackagePolicyError(PackagePolicyErrorCode.INSTALLER_SUBJECT_MISMATCH)

    return len(policy.required_installers)


def verify_pre_stage(
    root: Path,
    manifest: PackageManifest,
    policy: PolicyDocument,
    expected_provenance: ManifestProvenance,
    signature_lookup: Mapping[str, AuthenticodeSignatureInfo],
) -> PreStageResult:
    """Fail-closed pre-ZIP verification: path safety, allow-list, manifest
    one-to-one, hash/provenance integrity, and required installer signatures.
    """
    actual_paths = walk_stage_entries(root)
    verify_stage_policy(actual_paths, policy)
    verify_manifest_one_to_one(manifest.entries, actual_paths)
    digests = verify_manifest_hashes(manifest.entries, root)
    verify_manifest_provenance(manifest.entries, expected_provenance)
    installer_count = verify_installers(manifest.entries, root, policy, signature_lookup)

    return PreStageResult(
        entry_count=len(actual_paths),
        installer_count=installer_count,
        entry_digests=digests,
    )


def _zip_entry_sha256(archive: zipfile.ZipFile, name: str) -> str:
    digest = hashlib.sha256()
    with archive.open(name, "r") as stream:
        while chunk := stream.read(_HASH_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def verify_post_zip(
    zip_path: Path,
    manifest: PackageManifest,
    pre_stage_digests: Mapping[str, str],
) -> PostZipResult:
    """Post-ZIP verification without extraction: entry names are checked for
    traversal/duplicates and matched 1:1 against the manifest, then each
    entry's SHA-256 is streamed (not written to disk) and compared against
    the digest that was already Authenticode-verified at the pre-stage.
    """
    with zipfile.ZipFile(zip_path, "r") as archive:
        infos = [info for info in archive.infolist() if not info.is_dir()]

        names = [info.filename.replace("\\", "/") for info in infos]
        for name in names:
            if name.startswith("/") or ".." in name.split("/"):
                raise PackagePolicyError(PackagePolicyErrorCode.PATH_TRAVERSAL)

        if len(set(names)) != len(names):
            raise PackagePolicyError(PackagePolicyErrorCode.DUPLICATE_ENTRY)

        manifest_paths = {entry.path for entry in manifest.entries}
        actual_set = set(names)
        if manifest_paths - actual_set:
            raise PackagePolicyError(PackagePolicyErrorCode.MANIFEST_MISSING_ENTRY)
        if actual_set - manifest_paths:
            raise PackagePolicyError(PackagePolicyErrorCode.MANIFEST_EXTRA_ENTRY)
        if len(names) != len(manifest.entries):
            raise PackagePolicyError(PackagePolicyErrorCode.POST_ZIP_ENTRY_COUNT_MISMATCH)

        for name in names:
            expected_digest = pre_stage_digests.get(name)
            if expected_digest is None:
                raise PackagePolicyError(PackagePolicyErrorCode.POST_ZIP_UNKNOWN_ENTRY)
            actual_digest = _zip_entry_sha256(archive, name)
            if actual_digest != expected_digest:
                raise PackagePolicyError(PackagePolicyErrorCode.POST_ZIP_DIGEST_MISMATCH)

    return PostZipResult(entry_count=len(names))
