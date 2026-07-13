"""Fail-closed CLI wrapper around the offline-package builder's boundary
logic (Task 6, AeroOne v1.13.0).

This script owns only the plan/validation decision (delegated to
``app.operations.offline_package_policy``). It performs no ``git``/``npm``/
``pip`` calls itself; the paired PowerShell driver
(``scripts/build_offline_package.ps1``) gathers git state and the tracked
file list, calls this CLI to obtain a fail-closed build plan, and only then
performs the actual archive/build/wheelhouse/zip mechanics.

Usage:
    python build_offline_package_plan.py plan \
        --version 1.13.0 --commit <sha> --clean --tag 1.13.0 \
        --policy packaging/installer-policy.json \
        --tracked-paths <newline-delimited-file> \
        [--reuse-node-modules] [--reuse-next-build] [--reuse-wheelhouse] \
        [--include-dev-dependencies] [--allow-public-data] [--allow-timestamp-fallback]

On success, prints ``{"ok": true, "mode": ..., "publishable": ..., "output_dir": ...,
"zip_name": ..., "selected_count": ...}`` and exits 0.
On a policy violation, prints ``{"ok": false, "code": "<redacted-category-code>"}``
(no filenames, secrets, or path detail) and exits 1.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent / "backend"
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.operations.offline_package_build_contracts import (  # noqa: E402
    BuildOptions,
    GitState,
    OfflinePackageBuildError,
)
from app.operations.offline_package_policy import build_manifest_entries, plan_build  # noqa: E402
from app.operations.package_policy_contracts import ManifestProvenance, PackageManifest  # noqa: E402
from app.operations.package_policy_verifier import load_policy  # noqa: E402


def _run_plan(args: argparse.Namespace) -> int:
    policy = load_policy(Path(args.policy))
    tracked_paths = [
        line.strip() for line in Path(args.tracked_paths).read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    git_state = GitState(is_clean=args.clean, head_commit=args.commit, head_tag=args.tag)
    options = BuildOptions(
        reuse_node_modules=args.reuse_node_modules,
        reuse_next_build=args.reuse_next_build,
        reuse_wheelhouse=args.reuse_wheelhouse,
        include_dev_dependencies=args.include_dev_dependencies,
        allow_public_data=args.allow_public_data,
        allow_timestamp_fallback=args.allow_timestamp_fallback,
    )

    try:
        plan = plan_build(git_state, args.version, options, tracked_paths, policy)
    except OfflinePackageBuildError as exc:
        print(json.dumps({"ok": False, "code": exc.code.value}))
        return 1

    if args.selected_out:
        Path(args.selected_out).write_text("\n".join(plan.selected_paths), encoding="utf-8")

    print(
        json.dumps(
            {
                "ok": True,
                "mode": plan.context.mode,
                "publishable": plan.context.publishable,
                "output_dir": plan.context.output_dir,
                "zip_name": plan.context.zip_name,
                "selected_count": len(plan.selected_paths),
            }
        )
    )
    return 0


def _run_manifest(args: argparse.Namespace) -> int:
    selected_paths = [
        line.strip() for line in Path(args.selected_paths).read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    provenance = ManifestProvenance(origin="AeroOne", tag=args.tag or "", commit=args.commit, policy=args.policy_label)
    entries = build_manifest_entries(Path(args.stage_root), selected_paths, provenance)
    manifest = PackageManifest(entries=entries)
    Path(args.manifest_out).write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "entry_count": len(entries)}))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan_cmd = subparsers.add_parser("plan")
    plan_cmd.add_argument("--version", required=True)
    plan_cmd.add_argument("--commit", required=True)
    plan_cmd.add_argument("--tag", required=False, default=None)
    plan_cmd.add_argument("--clean", action="store_true")
    plan_cmd.add_argument("--policy", required=True)
    plan_cmd.add_argument("--tracked-paths", required=True)
    plan_cmd.add_argument("--selected-out", required=False, default=None)
    plan_cmd.add_argument("--reuse-node-modules", action="store_true")
    plan_cmd.add_argument("--reuse-next-build", action="store_true")
    plan_cmd.add_argument("--reuse-wheelhouse", action="store_true")
    plan_cmd.add_argument("--include-dev-dependencies", action="store_true")
    plan_cmd.add_argument("--allow-public-data", action="store_true")
    plan_cmd.add_argument("--allow-timestamp-fallback", action="store_true")
    plan_cmd.set_defaults(handler=_run_plan)
    manifest_cmd = subparsers.add_parser("manifest")
    manifest_cmd.add_argument("--stage-root", required=True)
    manifest_cmd.add_argument("--selected-paths", required=True)
    manifest_cmd.add_argument("--tag", required=False, default=None)
    manifest_cmd.add_argument("--commit", required=True)
    manifest_cmd.add_argument("--policy-label", required=True)
    manifest_cmd.add_argument("--manifest-out", required=True)
    manifest_cmd.set_defaults(handler=_run_manifest)

    args = parser.parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
