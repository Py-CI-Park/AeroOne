"""Contracts for the public offline-package builder (Task 6, AeroOne v1.13.0).

This module owns only the *build-time* decision contracts: whether the
requested build options are safe (fail-closed), and which release/QA
context a build lands in. It intentionally reuses the Task 5 policy
contracts (``package_policy_contracts``) for the underlying allow-list /
manifest / installer shapes rather than redefining them, so the builder and
the verifier never drift.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum, unique
from typing import ClassVar, Literal, override

from pydantic import BaseModel, ConfigDict


@unique
class OfflinePackageBuildErrorCode(StrEnum):
    DIRTY_WORKTREE = "dirty-worktree"
    REUSE_NODE_MODULES_FORBIDDEN = "reuse-node-modules-forbidden"
    REUSE_NEXT_BUILD_FORBIDDEN = "reuse-next-build-forbidden"
    REUSE_WHEELHOUSE_FORBIDDEN = "reuse-wheelhouse-forbidden"
    DEV_DEPENDENCIES_FORBIDDEN = "dev-dependencies-forbidden"
    TAG_REQUIRED = "tag-required"
    PUBLIC_DATA_FORBIDDEN = "public-data-forbidden"
    TOPLEVEL_NOT_ALLOWED = "toplevel-not-allowed"
    NETWORK_SANDBOX_FORBIDDEN = "network-sandbox-forbidden"
    INTERACTIVE_PAUSE_FORBIDDEN = "interactive-pause-forbidden"
    SANDBOX_TIMEOUT_INVALID = "sandbox-timeout-invalid"
    EMPTY_SELECTION = "empty-selection"


class OfflinePackageBuildError(Exception):
    code: OfflinePackageBuildErrorCode

    def __init__(self, code: OfflinePackageBuildErrorCode, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(code.value)

    @override
    def __str__(self) -> str:
        return self.code.value


class BuildOptions(BaseModel):
    """Requested build-time toggles. Every toggle below defaults to the
    single safe value; setting any of them to the unsafe value is rejected
    by ``validate_build_options`` (fail-closed, no override).
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    reuse_node_modules: bool = False
    reuse_next_build: bool = False
    reuse_wheelhouse: bool = False
    include_dev_dependencies: bool = False
    allow_public_data: bool = False
    allow_timestamp_fallback: bool = False


class GitState(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    is_clean: bool
    head_commit: str
    head_tag: str | None = None


class SandboxLaunchOptions(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    networking_enabled: bool = False
    interactive_pause: bool = False
    timeout_minutes: int = 20


@dataclass(frozen=True, slots=True)
class ReleaseContext:
    mode: Literal["release", "qa"]
    publishable: bool
    output_dir: str
    zip_name: str
    version: str
    tag: str | None
    commit: str


@dataclass(frozen=True, slots=True)
class BuildPlan:
    context: ReleaseContext
    selected_paths: tuple[str, ...]
