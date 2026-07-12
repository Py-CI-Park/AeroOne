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
_PRODUCTION_REQUIREMENTS_FILENAME = "requirements.txt"


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
    """The wheelhouse must always be built from the production
    ``backend/requirements.txt``. ``requirements-dev.txt`` (QA-only
    dependencies such as pytest/ruff) must never reach the production tree
    or the public ZIP.
    """
    if Path(requirements_filename).name != _PRODUCTION_REQUIREMENTS_FILENAME:
        raise OfflinePackageBuildError(OfflinePackageBuildErrorCode.DEV_DEPENDENCIES_FORBIDDEN)


def determine_release_context(
    git_state: GitState,
    version: str,
    *,
    dist_root: str = "dist",
    qa_root: str = "artifacts/qa",
) -> ReleaseContext:
    """release mode requires an *exact* annotated tag at HEAD that equals
    ``version`` (``v<version>`` or ``<version>``) on a clean worktree.
    Anything else (no tag, mismatched tag) is QA mode: deterministic
    ``<version>-pr-<commit-short>`` naming under ``artifacts/qa/``, never a
    wall-clock timestamp, and ``publishable=False``. A dirty worktree is
    rejected outright regardless of mode.
    """
    if not git_state.is_clean:
        raise OfflinePackageBuildError(OfflinePackageBuildErrorCode.DIRTY_WORKTREE)

    normalized_tag = git_state.head_tag.lstrip("v") if git_state.head_tag else None
    commit_short = git_state.head_commit[:8]

    if normalized_tag is not None and normalized_tag == version:
        return ReleaseContext(
            mode="release",
            publishable=True,
            output_dir=dist_root,
            zip_name=f"AeroOne-offline-{version}.zip",
            version=version,
            tag=git_state.head_tag,
            commit=git_state.head_commit,
        )

    pr_id = f"{version}-pr-{commit_short}"
    return ReleaseContext(
        mode="qa",
        publishable=False,
        output_dir=f"{qa_root}/{version}/{pr_id}",
        zip_name=f"AeroOne-offline-{pr_id}.zip",
        version=version,
        tag=git_state.head_tag,
        commit=git_state.head_commit,
    )


def _is_builder_denied_path(rel_posix: str) -> bool:
    """Additional builder-owned denylist for git-tracked source files that
    the generic Task 5 allow-list policy does not categorically forbid
    (because that policy is shared with other packaging profiles), but
    which must never reach the public offline package regardless: QA-only
    dependency manifests, and any generated tree the builder itself
    produces fresh (``git ls-files`` never actually reports these since
    they are gitignored, but the check stays defense-in-depth).
    """
    denied_exact = {"backend/requirements-dev.txt"}
    if rel_posix in denied_exact:
        return True
    denied_prefixes = ("frontend/node_modules/", "frontend/.next/", "offline_assets/python-wheels/")
    return rel_posix.startswith(denied_prefixes)


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
