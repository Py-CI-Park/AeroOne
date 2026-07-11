from __future__ import annotations

import zipfile
from collections.abc import Callable
from pathlib import Path

import pytest

from app.operations.offline_package_build_contracts import (
    BuildOptions,
    GitState,
    OfflinePackageBuildError,
    OfflinePackageBuildErrorCode,
    SandboxLaunchOptions,
)
from app.operations.offline_package_policy import (
    build_manifest_entries,
    determine_release_context,
    plan_build,
    select_allowlisted_paths,
    validate_build_options,
    validate_requirements_source,
    validate_sandbox_launch_options,
)
from app.operations.package_policy_contracts import (
    AuthenticodeSignatureInfo,
    ForbiddenCategory,
    ManifestProvenance,
    PackageManifest,
    PolicyDocument,
    RequiredInstaller,
)
from app.operations.package_policy_verifier import compute_sha256, verify_post_zip, verify_pre_stage

_VERSION = "1.13.0"
_PY_INSTALLER = "python-3.12.7-amd64.exe"
_NODE_INSTALLER = "node-v20.18.0-x64.msi"


def _policy() -> PolicyDocument:
    return PolicyDocument(
        policy_version=1,
        profile="test-builder",
        allow_top_level_entries=(
            "backend",
            "frontend",
            "docs",
            "scripts",
            "packaging",
            "offline_assets",
            "alembic.ini",
            "README.md",
            "start_offline.bat",
            "setup_offline.bat",
            "offline_package.bat",
        ),
        forbidden_categories=(
            ForbiddenCategory(
                category="env-secret",
                patterns=("**/.env", ".env"),
                allow_patterns=("**/.env.example", ".env.example"),
            ),
            ForbiddenCategory(category="database", patterns=("**/*.db", "backend/data/**")),
            ForbiddenCategory(category="storage-runtime", patterns=("storage/**",)),
            ForbiddenCategory(category="agent-state", patterns=(".gjc/**", ".omo/**", ".ug-*")),
            ForbiddenCategory(
                category="dev-artifact",
                patterns=(
                    "**/__pycache__/**",
                    "dist/**",
                    "artifacts/**",
                    "**/node_modules/**",
                    "**/.next/**",
                    "offline_assets/python-wheels/**",
                    "backend/requirements-dev.txt",
                    ".worktrees/**",
                ),
            ),
        ),
        required_installers=(
            RequiredInstaller(
                filename=_PY_INSTALLER,
                sha256="1" * 64,
                authenticode_thumbprint="A" * 40,
                authenticode_subject="Fixture Python Foundation",
            ),
            RequiredInstaller(
                filename=_NODE_INSTALLER,
                sha256="2" * 64,
                authenticode_thumbprint="B" * 40,
                authenticode_subject="Fixture OpenJS Foundation",
            ),
        ),
    )


_TRACKED_PATHS_HAPPY = [
    "backend/app/__init__.py",
    "backend/requirements.txt",
    "frontend/package.json",
    "docs/README.md",
    "scripts/tool.py",
    "README.md",
    "setup_offline.bat",
    # Forbidden / out-of-allow-list entries that must be excluded, not just
    # rejected, from the selection.
    "backend/.env",
    "backend/data/aeroone.db",
    "storage/markdown/newsletters/sample.md",
    ".omo/evidence/task-6.md",
    ".gjc/state/x.json",
    "backend/requirements-dev.txt",
    "frontend/node_modules/pkg/index.js",
    "frontend/.next/cache/x",
    "vendor/unexpected.txt",
    "dist/leftover.zip",
    ".worktrees/other/file.py",
]


def test_select_allowlisted_paths_excludes_forbidden_and_out_of_allowlist_entries() -> None:
    selected = select_allowlisted_paths(_TRACKED_PATHS_HAPPY, _policy())

    assert selected == sorted(
        [
            "backend/app/__init__.py",
            "backend/requirements.txt",
            "frontend/package.json",
            "docs/README.md",
            "scripts/tool.py",
            "README.md",
            "setup_offline.bat",
        ]
    )
    for forbidden in (
        "backend/.env",
        "backend/data/aeroone.db",
        "storage/markdown/newsletters/sample.md",
        ".omo/evidence/task-6.md",
        ".gjc/state/x.json",
        "backend/requirements-dev.txt",
        "frontend/node_modules/pkg/index.js",
        "frontend/.next/cache/x",
        "vendor/unexpected.txt",
        "dist/leftover.zip",
        ".worktrees/other/file.py",
    ):
        assert forbidden not in selected


def test_select_allowlisted_paths_rejects_empty_selection() -> None:
    with pytest.raises(OfflinePackageBuildError) as excinfo:
        select_allowlisted_paths(["vendor/only.txt"], _policy())
    assert excinfo.value.code == OfflinePackageBuildErrorCode.EMPTY_SELECTION


# ---------------------------------------------------------------------------
# Release vs QA mode determination.
# ---------------------------------------------------------------------------


def test_release_mode_requires_exact_annotated_tag_equal_to_version() -> None:
    git_state = GitState(is_clean=True, head_commit="a" * 40, head_tag=f"v{_VERSION}")
    context = determine_release_context(git_state, _VERSION)

    assert context.mode == "release"
    assert context.publishable is True
    assert context.output_dir == "dist"
    assert context.zip_name == f"AeroOne-offline-{_VERSION}.zip"


@pytest.mark.parametrize(
    "head_tag",
    [None, "v1.12.2", "v1.13.0-dev"],
)
def test_mismatched_or_missing_tag_falls_back_to_qa_mode_not_release(head_tag: str | None) -> None:
    git_state = GitState(is_clean=True, head_commit="deadbeef" + "0" * 32, head_tag=head_tag)
    context = determine_release_context(git_state, _VERSION)

    assert context.mode == "qa"
    assert context.publishable is False
    assert context.output_dir == f"artifacts/qa/{_VERSION}/{_VERSION}-pr-deadbeef"
    assert context.zip_name == f"AeroOne-offline-{_VERSION}-pr-deadbeef.zip"
    assert "T" not in context.output_dir  # no wall-clock timestamp component


def test_dirty_worktree_is_rejected_regardless_of_tag_state() -> None:
    git_state = GitState(is_clean=False, head_commit="a" * 40, head_tag=f"v{_VERSION}")
    with pytest.raises(OfflinePackageBuildError) as excinfo:
        determine_release_context(git_state, _VERSION)
    assert excinfo.value.code == OfflinePackageBuildErrorCode.DIRTY_WORKTREE


# ---------------------------------------------------------------------------
# Fail-closed build-option validation: no override path for any toggle.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "make_options,expected_code",
    [
        (lambda: BuildOptions(reuse_node_modules=True), OfflinePackageBuildErrorCode.REUSE_NODE_MODULES_FORBIDDEN),
        (lambda: BuildOptions(reuse_next_build=True), OfflinePackageBuildErrorCode.REUSE_NEXT_BUILD_FORBIDDEN),
        (lambda: BuildOptions(reuse_wheelhouse=True), OfflinePackageBuildErrorCode.REUSE_WHEELHOUSE_FORBIDDEN),
        (
            lambda: BuildOptions(include_dev_dependencies=True),
            OfflinePackageBuildErrorCode.DEV_DEPENDENCIES_FORBIDDEN,
        ),
        (lambda: BuildOptions(allow_public_data=True), OfflinePackageBuildErrorCode.PUBLIC_DATA_FORBIDDEN),
        (lambda: BuildOptions(allow_timestamp_fallback=True), OfflinePackageBuildErrorCode.TAG_REQUIRED),
    ],
)
def test_validate_build_options_is_fail_closed(
    make_options: Callable[[], BuildOptions], expected_code: OfflinePackageBuildErrorCode
) -> None:
    with pytest.raises(OfflinePackageBuildError) as excinfo:
        validate_build_options(make_options())
    assert excinfo.value.code == expected_code


def test_validate_build_options_accepts_all_defaults() -> None:
    validate_build_options(BuildOptions())  # must not raise


def test_validate_requirements_source_rejects_dev_requirements_file() -> None:
    with pytest.raises(OfflinePackageBuildError) as excinfo:
        validate_requirements_source("backend/requirements-dev.txt")
    assert excinfo.value.code == OfflinePackageBuildErrorCode.DEV_DEPENDENCIES_FORBIDDEN


def test_validate_requirements_source_accepts_production_requirements_file() -> None:
    validate_requirements_source("backend/requirements.txt")  # must not raise


# ---------------------------------------------------------------------------
# Sandbox launch-option validation.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "make_options,expected_code",
    [
        (lambda: SandboxLaunchOptions(networking_enabled=True), OfflinePackageBuildErrorCode.NETWORK_SANDBOX_FORBIDDEN),
        (lambda: SandboxLaunchOptions(interactive_pause=True), OfflinePackageBuildErrorCode.INTERACTIVE_PAUSE_FORBIDDEN),
        (lambda: SandboxLaunchOptions(timeout_minutes=0), OfflinePackageBuildErrorCode.SANDBOX_TIMEOUT_INVALID),
        (lambda: SandboxLaunchOptions(timeout_minutes=21), OfflinePackageBuildErrorCode.SANDBOX_TIMEOUT_INVALID),
    ],
)
def test_validate_sandbox_launch_options_is_fail_closed(
    make_options: Callable[[], SandboxLaunchOptions], expected_code: OfflinePackageBuildErrorCode
) -> None:
    with pytest.raises(OfflinePackageBuildError) as excinfo:
        validate_sandbox_launch_options(make_options())
    assert excinfo.value.code == expected_code


def test_validate_sandbox_launch_options_accepts_default_offline_20_minute_window() -> None:
    validate_sandbox_launch_options(SandboxLaunchOptions())  # must not raise


# ---------------------------------------------------------------------------
# End-to-end chain: builder plan -> synthetic stage -> ZIP -> Task 5 verifier.
# ---------------------------------------------------------------------------


def _write(root: Path, rel_posix: str, content: bytes) -> Path:
    target = root / rel_posix
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return target


def test_builder_to_verifier_chain_passes_for_a_compliant_synthetic_repo(tmp_path: Path) -> None:
    source_repo = tmp_path / "source"
    for rel, content in {
        "backend/app/__init__.py": b"",
        "backend/requirements.txt": b"fastapi\n",
        "frontend/package.json": b'{"name": "aeroone-frontend"}\n',
        "docs/README.md": b"# docs\n",
        "scripts/tool.py": b"print('tool')\n",
        "README.md": b"# AeroOne\n",
        # Forbidden entries mixed into the synthetic tracked-file set to
        # prove the plan excludes them before staging even happens.
        "backend/.env": b"SECRET=leak\n",
        "backend/requirements-dev.txt": b"pytest\n",
        "frontend/node_modules/pkg/index.js": b"module.exports = {};\n",
        "storage/markdown/newsletters/sample.md": b"# sample\n",
        ".omo/evidence/task-6.md": b"internal\n",
    }.items():
        _write(source_repo, rel, content)

    policy = _policy()
    git_state = GitState(is_clean=True, head_commit="b" * 40, head_tag=f"v{_VERSION}")
    options = BuildOptions()

    tracked_paths = [
        "backend/app/__init__.py",
        "backend/requirements.txt",
        "frontend/package.json",
        "docs/README.md",
        "scripts/tool.py",
        "README.md",
        "backend/.env",
        "backend/requirements-dev.txt",
        "frontend/node_modules/pkg/index.js",
        "storage/markdown/newsletters/sample.md",
        ".omo/evidence/task-6.md",
    ]

    plan = plan_build(git_state, _VERSION, options, tracked_paths, policy)
    assert plan.context.mode == "release"
    assert plan.context.publishable is True

    # Materialize the release-only stage: only the selected (allow-listed,
    # non-forbidden) paths, plus the two required Task 5 installers.
    stage_root = tmp_path / "stage" / "AeroOne"
    for rel in plan.selected_paths:
        _write(stage_root, rel, (source_repo / rel).read_bytes())
    _write(stage_root, f"offline_assets/installers/{_PY_INSTALLER}", b"fixture-python-installer-bytes")
    _write(stage_root, f"offline_assets/installers/{_NODE_INSTALLER}", b"fixture-node-installer-bytes")

    provenance = ManifestProvenance(
        origin="AeroOne", tag=plan.context.tag or "", commit=plan.context.commit, policy="release-qa@1"
    )
    all_paths = (
        *plan.selected_paths,
        f"offline_assets/installers/{_PY_INSTALLER}",
        f"offline_assets/installers/{_NODE_INSTALLER}",
    )
    entries = build_manifest_entries(stage_root, all_paths, provenance)
    manifest = PackageManifest(entries=entries)

    signatures = {
        _PY_INSTALLER: AuthenticodeSignatureInfo(
            status="Valid", thumbprint="A" * 40, subject="Fixture Python Foundation"
        ),
        _NODE_INSTALLER: AuthenticodeSignatureInfo(
            status="Valid", thumbprint="B" * 40, subject="Fixture OpenJS Foundation"
        ),
    }
    # The installer hashes in the fixture policy above are placeholders; align them
    # to the actual materialized fixture bytes so verify_installers can pass.
    policy = policy.model_copy(
        update={
            "required_installers": tuple(
                RequiredInstaller(
                    filename=req.filename,
                    sha256=compute_sha256(stage_root / f"offline_assets/installers/{req.filename}"),
                    authenticode_thumbprint=req.authenticode_thumbprint,
                    authenticode_subject=req.authenticode_subject,
                )
                for req in policy.required_installers
            )
        }
    )

    pre_result = verify_pre_stage(stage_root, manifest, policy, provenance, signatures)
    assert pre_result.entry_count == len(all_paths)
    assert pre_result.installer_count == 2

    zip_path = tmp_path / plan.context.zip_name
    with zipfile.ZipFile(zip_path, "w") as archive:
        for entry in manifest.entries:
            archive.write(stage_root / entry.path, entry.path)

    post_result = verify_post_zip(zip_path, manifest, pre_result.entry_digests)
    assert post_result.entry_count == len(all_paths)


def test_builder_to_verifier_chain_fails_closed_when_forbidden_path_smuggled_into_stage(tmp_path: Path) -> None:
    """Even if a forbidden path somehow ends up materialized in the stage
    (bypassing ``select_allowlisted_paths``), the Task 5 verifier still
    rejects the tree before a ZIP is trusted — defense in depth.
    """
    policy = _policy()
    stage_root = tmp_path / "stage" / "AeroOne"
    for rel, content in {
        "backend/app/__init__.py": b"",
        "backend/requirements.txt": b"fastapi\n",
    }.items():
        _write(stage_root, rel, content)
    _write(stage_root, f"offline_assets/installers/{_PY_INSTALLER}", b"fixture-python-installer-bytes")
    _write(stage_root, f"offline_assets/installers/{_NODE_INSTALLER}", b"fixture-node-installer-bytes")
    # Smuggled forbidden entry that never went through the builder's plan.
    _write(stage_root, "backend/.env", b"SECRET=leak\n")

    provenance = ManifestProvenance(origin="AeroOne", tag="v1.13.0", commit="c" * 40, policy="release-qa@1")
    all_paths = (
        "backend/app/__init__.py",
        "backend/requirements.txt",
        f"offline_assets/installers/{_PY_INSTALLER}",
        f"offline_assets/installers/{_NODE_INSTALLER}",
        "backend/.env",
    )
    entries = build_manifest_entries(stage_root, all_paths, provenance)
    manifest = PackageManifest(entries=entries)

    policy = policy.model_copy(
        update={
            "required_installers": tuple(
                RequiredInstaller(
                    filename=req.filename,
                    sha256=compute_sha256(stage_root / f"offline_assets/installers/{req.filename}"),
                    authenticode_thumbprint=req.authenticode_thumbprint,
                    authenticode_subject=req.authenticode_subject,
                )
                for req in policy.required_installers
            )
        }
    )
    signatures = {
        _PY_INSTALLER: AuthenticodeSignatureInfo(
            status="Valid", thumbprint="A" * 40, subject="Fixture Python Foundation"
        ),
        _NODE_INSTALLER: AuthenticodeSignatureInfo(
            status="Valid", thumbprint="B" * 40, subject="Fixture OpenJS Foundation"
        ),
    }

    from app.operations.package_policy_contracts import PackagePolicyError, PackagePolicyErrorCode

    with pytest.raises(PackagePolicyError) as excinfo:
        verify_pre_stage(stage_root, manifest, policy, provenance, signatures)
    assert excinfo.value.code == PackagePolicyErrorCode.FORBIDDEN_ENV_SECRET
