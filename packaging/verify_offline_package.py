"""Fail-closed CLI wrapper around the pre-stage/post-ZIP package policy
verifier (Task 5, AeroOne v1.13.0).

This script owns only the policy/manifest/entry logic (delegated to
``app.operations.package_policy_verifier``). Authenticode signature
verification and OS-level file existence checks are the responsibility of
the paired PowerShell module (``scripts/packaging/Verify-OfflinePackage.psm1``);
this CLI accepts the signature results that module already gathered as a
small JSON file rather than re-implementing Authenticode itself.

Usage:
    python verify_offline_package.py pre-stage \
        --stage-root <dir> --manifest <manifest.json> --policy <policy.json> \
        --origin AeroOne --tag 1.13.0 --commit <sha> --policy-label release-qa@1 \
        --signatures <signatures.json> --digests-out <digests.json>

    python verify_offline_package.py post-zip \
        --zip <package.zip> --manifest <manifest.json> --digests <digests.json>

On success, prints ``{"ok": true, ...}`` and exits 0.
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

from app.operations.package_policy_contracts import (  # noqa: E402
    AuthenticodeSignatureInfo,
    ManifestProvenance,
    PackagePolicyError,
)
from app.operations.package_policy_verifier import (  # noqa: E402
    load_manifest,
    load_policy,
    verify_post_zip,
    verify_pre_stage,
)


def _load_signature_lookup(path: Path) -> dict[str, AuthenticodeSignatureInfo]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {
        filename: AuthenticodeSignatureInfo(
            status=info["status"], thumbprint=info["thumbprint"], subject=info["subject"]
        )
        for filename, info in raw.items()
    }


def _run_pre_stage(args: argparse.Namespace) -> int:
    manifest = load_manifest(Path(args.manifest))
    policy = load_policy(Path(args.policy))
    signatures = _load_signature_lookup(Path(args.signatures))
    provenance = ManifestProvenance(
        origin=args.origin, tag=args.tag, commit=args.commit, policy=args.policy_label
    )

    try:
        result = verify_pre_stage(Path(args.stage_root), manifest, policy, provenance, signatures)
    except PackagePolicyError as exc:
        print(json.dumps({"ok": False, "code": exc.code.value}))
        return 1

    if args.digests_out:
        Path(args.digests_out).write_text(json.dumps(result.entry_digests), encoding="utf-8")

    print(json.dumps({"ok": True, "entry_count": result.entry_count, "installer_count": result.installer_count}))
    return 0


def _run_post_zip(args: argparse.Namespace) -> int:
    manifest = load_manifest(Path(args.manifest))
    digests = json.loads(Path(args.digests).read_text(encoding="utf-8"))

    try:
        result = verify_post_zip(Path(args.zip), manifest, digests)
    except PackagePolicyError as exc:
        print(json.dumps({"ok": False, "code": exc.code.value}))
        return 1

    print(json.dumps({"ok": True, "entry_count": result.entry_count}))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    pre_stage = subparsers.add_parser("pre-stage")
    pre_stage.add_argument("--stage-root", required=True)
    pre_stage.add_argument("--manifest", required=True)
    pre_stage.add_argument("--policy", required=True)
    pre_stage.add_argument("--origin", required=True)
    pre_stage.add_argument("--tag", required=False, default="")
    pre_stage.add_argument("--commit", required=True)
    pre_stage.add_argument("--policy-label", required=True)
    pre_stage.add_argument("--signatures", required=True)
    pre_stage.add_argument("--digests-out", required=False, default=None)
    pre_stage.set_defaults(handler=_run_pre_stage)

    post_zip = subparsers.add_parser("post-zip")
    post_zip.add_argument("--zip", required=True)
    post_zip.add_argument("--manifest", required=True)
    post_zip.add_argument("--digests", required=True)
    post_zip.set_defaults(handler=_run_post_zip)

    args = parser.parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
