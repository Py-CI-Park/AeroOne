from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum, unique
from typing import ClassVar, override

from pydantic import BaseModel, ConfigDict, Field


@unique
class PackagePolicyErrorCode(StrEnum):
    PATH_TRAVERSAL = "path-traversal"
    SYMLINK_ENTRY = "symlink-entry"
    DUPLICATE_ENTRY = "duplicate-entry"
    TOPLEVEL_NOT_ALLOWED = "toplevel-not-allowed"
    FORBIDDEN_ENV_SECRET = "forbidden-env-secret"
    FORBIDDEN_DATABASE = "forbidden-database"
    FORBIDDEN_STORAGE_RUNTIME = "forbidden-storage-runtime"
    FORBIDDEN_AGENT_STATE = "forbidden-agent-state"
    FORBIDDEN_DEV_ARTIFACT = "forbidden-dev-artifact"
    MANIFEST_MISSING_ENTRY = "manifest-missing-entry"
    MANIFEST_EXTRA_ENTRY = "manifest-extra-entry"
    MANIFEST_HASH_MISMATCH = "manifest-hash-mismatch"
    MANIFEST_PROVENANCE_MISMATCH = "manifest-provenance-mismatch"
    INSTALLER_MISSING = "installer-missing"
    INSTALLER_HASH_MISMATCH = "installer-hash-mismatch"
    INSTALLER_SIGNATURE_INVALID = "installer-signature-invalid"
    INSTALLER_THUMBPRINT_MISMATCH = "installer-thumbprint-mismatch"
    INSTALLER_SUBJECT_MISMATCH = "installer-subject-mismatch"
    POST_ZIP_DIGEST_MISMATCH = "post-zip-digest-mismatch"
    POST_ZIP_ENTRY_COUNT_MISMATCH = "post-zip-entry-count-mismatch"
    POST_ZIP_UNKNOWN_ENTRY = "post-zip-unknown-entry"


class PackagePolicyError(Exception):
    code: PackagePolicyErrorCode

    def __init__(self, code: PackagePolicyErrorCode, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(code.value)

    @override
    def __str__(self) -> str:
        return self.code.value


class ForbiddenCategory(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    category: str
    patterns: tuple[str, ...]
    allow_patterns: tuple[str, ...] = ()


class RequiredInstaller(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, strict=True, extra="forbid")

    filename: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    authenticode_thumbprint: str = Field(pattern=r"^[0-9A-F]{40}$")
    authenticode_subject: str


class PolicyDocument(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    policy_version: int
    profile: str
    allow_top_level_entries: tuple[str, ...]
    forbidden_categories: tuple[ForbiddenCategory, ...]
    required_installers: tuple[RequiredInstaller, ...]


class ManifestEntry(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, strict=True, extra="forbid")

    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    origin: str
    tag: str
    commit: str
    policy: str


class PackageManifest(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    entries: tuple[ManifestEntry, ...]


@dataclass(frozen=True, slots=True)
class ManifestProvenance:
    origin: str
    tag: str
    commit: str
    policy: str


@dataclass(frozen=True, slots=True)
class AuthenticodeSignatureInfo:
    status: str
    thumbprint: str
    subject: str


@dataclass(frozen=True, slots=True)
class PreStageResult:
    entry_count: int
    installer_count: int
    entry_digests: dict[str, str]


@dataclass(frozen=True, slots=True)
class PostZipResult:
    entry_count: int
