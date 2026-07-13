"""Boundary logic for the public offline-package builder (Task 6, AeroOne
v1.13.0): fail-closed build-option validation, release/QA context
determination, and git-archive allow-list path selection.

This module performs no I/O beyond hashing already-materialized files; it
never shells out to ``git``, ``npm``, or ``pip``. The PowerShell builder
(``scripts/build_offline_package.ps1``) gathers git/tool state and calls the
paired CLI (``packaging/build_offline_package_plan.py``) which wraps these
pure functions, mirroring the Task 5 verifier/CLI split.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
import re

from app.operations.offline_package_build_contracts import (
    BuildOptions,
    BuildPlan,
    GitState,
    OfflinePackageBuildError,
    OfflinePackageBuildErrorCode,
    ReleaseContext,
    SandboxLaunchOptions,
)
from app.operations.package_policy_contracts import ManifestEntry, ManifestProvenance, PolicyDocument
from app.operations.package_policy_verifier import check_top_level_allowed, classify_forbidden, compute_sha256

_MAX_SANDBOX_TIMEOUT_MINUTES = 20


def validate_build_options(options: BuildOptions) -> None:
    """Fail-closed: every unsafe toggle is rejected outright. There is no
    override path — reuse of generated trees, dev dependencies, public
    data, and timestamp-only versioning are always forbidden for the public
    offline package, matching the constraints that made the legacy
    ``offline_package.bat`` robocopy/deny-list approach unsafe.
    """
    if options.reuse_node_modules:
        raise OfflinePackageBuildError(OfflinePackageBuildErrorCode.REUSE_NODE_MODULES_FORBIDDEN)
    if options.reuse_next_build:
        raise OfflinePackageBuildError(OfflinePackageBuildErrorCode.REUSE_NEXT_BUILD_FORBIDDEN)
    if options.reuse_wheelhouse:
        raise OfflinePackageBuildError(OfflinePackageBuildErrorCode.REUSE_WHEELHOUSE_FORBIDDEN)
    if options.include_dev_dependencies:
        raise OfflinePackageBuildError(OfflinePackageBuildErrorCode.DEV_DEPENDENCIES_FORBIDDEN)
    if options.allow_public_data:
        raise OfflinePackageBuildError(OfflinePackageBuildErrorCode.PUBLIC_DATA_FORBIDDEN)
    if options.allow_timestamp_fallback:
        raise OfflinePackageBuildError(OfflinePackageBuildErrorCode.TAG_REQUIRED)


def validate_requirements_source(requirements_filename: str) -> None:
    """Require the one canonical repository-relative production requirements path."""
    if requirements_filename.replace("\\", "/") != "backend/requirements.txt":
        raise OfflinePackageBuildError(OfflinePackageBuildErrorCode.DEV_DEPENDENCIES_FORBIDDEN)

def determine_release_context(
    git_state: GitState,
    version: str,
    *,
    dist_root: str = "dist",
    qa_root: str = "artifacts/qa",
) -> ReleaseContext:
    """Determine immutable release or QA context from a captured commit."""
    if not git_state.is_clean:
        raise OfflinePackageBuildError(OfflinePackageBuildErrorCode.DIRTY_WORKTREE)
    if re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version, flags=re.ASCII) is None:
        raise OfflinePackageBuildError(OfflinePackageBuildErrorCode.TAG_REQUIRED)

    accepted_tag = version
    commit_short = git_state.head_commit[:8]
    if git_state.head_tag == accepted_tag:
        return ReleaseContext(
            mode="release", publishable=True, output_dir=dist_root,
            zip_name=f"AeroOne-offline-{version}.zip", version=version,
            tag=git_state.head_tag, commit=git_state.head_commit,
        )

    pr_id = f"{version}-pr-{commit_short}"
    return ReleaseContext(
        mode="qa", publishable=False, output_dir=f"{qa_root}/{version}/{pr_id}",
        zip_name=f"AeroOne-offline-{pr_id}.zip", version=version,
        tag=git_state.head_tag, commit=git_state.head_commit,
    )


def _is_builder_denied_path(rel_posix: str) -> bool:
    """Case-insensitive builder-owned exclusions for Windows worktrees."""
    normalized = rel_posix.replace("\\", "/").casefold()
    denied_exact = {
        "backend/requirements-dev.txt",
        "frontend/playwright.qa.config.ts",
    }
    if normalized in denied_exact:
        return True
    denied_prefixes = (
        "backend/tests/",
        "frontend/tests/",
        "scripts/qa/",
        "frontend/node_modules/",
        "frontend/.next/",
        "offline_assets/python-wheels/",
    )
    return normalized.startswith(denied_prefixes)


def select_allowlisted_paths(tracked_paths: Sequence[str], policy: PolicyDocument) -> list[str]:
    """``git archive`` allow-list selection: keep only tracked paths whose
    top-level entry is in ``policy.allow_top_level_entries`` and that do not
    match any forbidden-category pattern. Anything else (forbidden
    top-level dirs, categorized secrets/db/storage/agent-state/dev-artifact
    paths, or the builder-owned denylist below) is silently excluded from
    the archive pathspec — the same exclusion semantics
    ``git archive <tree> -- <pathspecs>`` gives when a path is simply never
    listed.
    """
    selected: list[str] = []
    seen: set[str] = set()
    for rel_posix in tracked_paths:
        if rel_posix in seen:
            continue
        seen.add(rel_posix)
        if _is_builder_denied_path(rel_posix):
            continue
        if classify_forbidden(rel_posix, policy) is not None:
            continue
        if not check_top_level_allowed(rel_posix, policy):
            continue
        selected.append(rel_posix)

    if not selected:
        raise OfflinePackageBuildError(OfflinePackageBuildErrorCode.EMPTY_SELECTION)

    return sorted(selected)


def build_manifest_entries(
    root: Path, selected_paths: Sequence[str], provenance: ManifestProvenance
) -> tuple[ManifestEntry, ...]:
    return tuple(
        ManifestEntry(
            path=rel_posix,
            sha256=compute_sha256(root / rel_posix),
            origin=provenance.origin,
            tag=provenance.tag,
            commit=provenance.commit,
            policy=provenance.policy,
        )
        for rel_posix in selected_paths
    )


def plan_build(
    git_state: GitState,
    version: str,
    options: BuildOptions,
    tracked_paths: Sequence[str],
    policy: PolicyDocument,
    *,
    dist_root: str = "dist",
    qa_root: str = "artifacts/qa",
) -> BuildPlan:
    """Orchestrates option validation, release/QA context determination,
    and allow-list path selection. Raises on the first violation
    (fail-closed); never produces a partial plan.
    """
    validate_build_options(options)
    context = determine_release_context(git_state, version, dist_root=dist_root, qa_root=qa_root)
    selected = select_allowlisted_paths(tracked_paths, policy)
    return BuildPlan(context=context, selected_paths=tuple(selected))


def validate_sandbox_launch_options(
    options: SandboxLaunchOptions, *, max_timeout_minutes: int = _MAX_SANDBOX_TIMEOUT_MINUTES
) -> None:
    """Fail-closed guard for the Windows Sandbox smoke-test harness launch
    parameters: networking must stay disabled, no interactive pause is
    allowed (the guest bootstrap must run unattended end-to-end), and the
    timeout must be a positive value not exceeding the policy ceiling.
    """
    if options.networking_enabled:
        raise OfflinePackageBuildError(OfflinePackageBuildErrorCode.NETWORK_SANDBOX_FORBIDDEN)
    if options.interactive_pause:
        raise OfflinePackageBuildError(OfflinePackageBuildErrorCode.INTERACTIVE_PAUSE_FORBIDDEN)
    if options.timeout_minutes <= 0 or options.timeout_minutes > max_timeout_minutes:
        raise OfflinePackageBuildError(OfflinePackageBuildErrorCode.SANDBOX_TIMEOUT_INVALID)
