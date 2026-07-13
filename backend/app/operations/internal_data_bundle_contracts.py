"""Boundary/business-rule validation for AeroOne internal data bundles.

This module is the single source of truth for the *non-cryptographic*
boundary rules that gate the internal data bundle pipeline (approval
schema, TTL, dual-role signer separation, trust policy pinning, ACL shape,
target path containment, inventory integrity, EKU/AES OID exactness).

Actual cryptographic operations (SignedCms / EnvelopedCms, X509Chain
building, certificate store and registry access) live in the PowerShell
CMS layer (``scripts/*.ps1``). Those scripts feed the *evidence* they
extract (already-verified signature/chain booleans, EKU OIDs, validity
windows, ACL entries, ...) into the pure functions below so that every
policy decision is unit-testable without touching a real certificate
store or the Windows registry.

``ConvertFrom-Json`` alone is never used as boundary validation: the
PowerShell layer pipes raw approval bytes into this module's CLI
(``python -m app.operations.internal_data_bundle_contracts``) which
performs strict, duplicate-key-rejecting parsing before any field is
trusted.
"""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum, unique

from typing import ClassVar, Sequence, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

SCHEMA_VERSION = "1.0"

# EnvelopedCms content-encryption algorithm OID: AES-256-CBC.
AES_256_CBC_OID = "2.16.840.1.101.3.4.1.42"

# Certificate Enhanced Key Usage OIDs.
DOCUMENT_SIGNING_EKU_OID = "1.3.6.1.4.1.311.10.3.12"
EMAIL_PROTECTION_EKU_OID = "1.3.6.1.5.5.7.3.4"

NORMAL_ROOTS = frozenset({"newsletter", "civil_aircraft", "document"})
NSA_ROOT = frozenset({"nsa"})
ALL_ROOTS = NORMAL_ROOTS | NSA_ROOT

NORMAL_SIGNER_ROLES = frozenset({"data_owner", "security_officer"})
NSA_SIGNER_ROLES = frozenset({"nsa_data_owner", "security_officer"})

MAX_APPROVAL_TTL = timedelta(hours=24)

REQUIRED_ENVELOPE_ENTRIES = frozenset({"approval.json", "inventory.json"})

_ACL_READ_RIGHT = "Read"


@unique
class InternalDataBundleErrorCode(StrEnum):
    DUPLICATE_JSON_KEY = "duplicate-json-key"
    INVALID_JSON = "invalid-json"
    SCHEMA_VIOLATION = "schema-violation"
    TTL_EXCEEDED = "ttl-exceeded"
    EXPIRES_BEFORE_ISSUED = "expires-before-issued"
    APPROVAL_EXPIRED = "approval-expired"
    APPROVAL_NOT_YET_VALID = "approval-not-yet-valid"
    MIXED_ROOTS = "mixed-roots"
    ROOTS_NSA_FLAG_MISMATCH = "roots-nsa-flag-mismatch"
    UNKNOWN_ROOT = "unknown-root"
    SIGNER_ROLE_SET_MISMATCH = "signer-role-set-mismatch"
    SIGNER_SAME_THUMBPRINT = "signer-same-thumbprint"
    SIGNER_ROLE_INVALID_FOR_BUNDLE = "signer-role-invalid-for-bundle"
    RECIPIENT_MISMATCH = "recipient-mismatch"
    RECIPIENT_ENVIRONMENT_MISMATCH = "recipient-environment-mismatch"
    RECIPIENT_PRIVATE_KEY_MISSING = "recipient-private-key-missing"
    EKU_MISMATCH = "eku-mismatch"
    CERT_NOT_YET_VALID = "cert-not-yet-valid"
    CERT_EXPIRED = "cert-expired"
    SIGNATURE_INVALID = "signature-invalid"
    CHAIN_INVALID = "chain-invalid"
    AES_OID_MISMATCH = "aes-oid-mismatch"
    TRUST_POLICY_DIGEST_MISMATCH = "trust-policy-digest-mismatch"
    TRUST_POLICY_DIGEST_ABSENT = "trust-policy-digest-absent"
    TRUST_POLICY_EXPIRED = "trust-policy-expired"
    ACL_MISMATCH = "acl-mismatch"
    ALLOWED_ROOTS_NOT_SUBSET = "allowed-roots-not-subset"
    PATH_TRAVERSAL = "path-traversal"
    PATH_ESCAPES_ALLOWED_ROOTS = "path-escapes-allowed-roots"
    INVENTORY_HASH_MISMATCH = "inventory-hash-mismatch"
    ENVELOPE_ENTRY_MISMATCH = "envelope-entry-mismatch"


class InternalDataBundleError(Exception):
    code: InternalDataBundleErrorCode

    def __init__(self, code: InternalDataBundleErrorCode, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code.value}: {detail}" if detail else code.value)

    def __str__(self) -> str:
        return self.code.value


class ApprovalRecord(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    schema_version: str
    request_id: str = Field(min_length=1)
    ticket_id: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    issued_at: datetime
    expires_at: datetime
    target_environment_id: str = Field(min_length=1)
    recipient_thumbprint: str = Field(pattern=r"^[0-9A-F]{40}$")
    allowed_roots: tuple[str, ...]
    source_inventory_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    include_nsa: bool

    @field_validator("issued_at", "expires_at")
    @classmethod
    def _require_tz(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value.astimezone(timezone.utc)

    @field_validator("allowed_roots")
    @classmethod
    def _roots_non_empty_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise ValueError("allowed_roots must not be empty")
        if len(set(value)) != len(value):
            raise ValueError("allowed_roots must not contain duplicates")
        return value


class TrustSigner(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    role: str = Field(min_length=1)
    thumbprint: str = Field(pattern=r"^[0-9A-F]{40}$")
    subject: str = Field(min_length=1)
    eku_oid: str = Field(min_length=1)


class TrustRecipient(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    target_environment_id: str = Field(min_length=1)
    thumbprint: str = Field(pattern=r"^[0-9A-F]{40}$")
    subject: str = Field(min_length=1)
    eku_oid: str = Field(min_length=1)


class TrustPolicy(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    schema_version: str
    policy_id: str = Field(min_length=1)
    expires_at: datetime
    max_approval_ttl_hours: int = Field(gt=0, le=24)
    allowed_roots: tuple[str, ...]
    signers: tuple[TrustSigner, ...]
    recipients: tuple[TrustRecipient, ...]

    @field_validator("expires_at")
    @classmethod
    def _require_tz(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class SignatureEvidence:
    role: str
    thumbprint: str
    subject: str
    eku_oid: str
    signature_valid: bool
    chain_valid: bool
    not_before: datetime
    not_after: datetime


@dataclass(frozen=True, slots=True)
class RecipientEvidence:
    target_environment_id: str
    thumbprint: str
    subject: str
    eku_oid: str
    has_private_key: bool
    not_before: datetime
    not_after: datetime


@dataclass(frozen=True, slots=True)
class AceEntry:
    identity_sid: str
    rights: str
    is_inherited: bool


def _no_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    seen: set[str] = set()
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in seen:
            raise InternalDataBundleError(InternalDataBundleErrorCode.DUPLICATE_JSON_KEY, key)
        seen.add(key)
        result[key] = value
    return result


def parse_strict_json_object(raw: bytes) -> dict[str, object]:
    """Strict UTF-8 JSON object parser: rejects invalid UTF-8, non-object
    roots, and duplicate keys. This is the only sanctioned way to read
    approval/trust-policy bytes into a trusted structure."""
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise InternalDataBundleError(InternalDataBundleErrorCode.INVALID_JSON, str(exc)) from exc
    try:
        parsed = json.loads(text, object_pairs_hook=_no_duplicate_keys)
    except json.JSONDecodeError as exc:
        raise InternalDataBundleError(InternalDataBundleErrorCode.INVALID_JSON, str(exc)) from exc
    if not isinstance(parsed, dict):
        raise InternalDataBundleError(InternalDataBundleErrorCode.INVALID_JSON, "root must be an object")
    return parsed


def compute_sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_approval_strict(raw: bytes, *, now: datetime | None = None) -> ApprovalRecord:
    obj = parse_strict_json_object(raw)
    try:
        approval = ApprovalRecord.model_validate(obj)
    except ValidationError as exc:
        raise InternalDataBundleError(InternalDataBundleErrorCode.SCHEMA_VIOLATION, str(exc)) from exc

    if approval.schema_version != SCHEMA_VERSION:
        raise InternalDataBundleError(InternalDataBundleErrorCode.SCHEMA_VIOLATION, "schema_version")

    if approval.expires_at <= approval.issued_at:
        raise InternalDataBundleError(InternalDataBundleErrorCode.EXPIRES_BEFORE_ISSUED)

    if approval.expires_at - approval.issued_at > MAX_APPROVAL_TTL:
        raise InternalDataBundleError(InternalDataBundleErrorCode.TTL_EXCEEDED)

    reference_time = now or datetime.now(timezone.utc)
    if reference_time < approval.issued_at:
        raise InternalDataBundleError(InternalDataBundleErrorCode.APPROVAL_NOT_YET_VALID)
    if reference_time > approval.expires_at:
        raise InternalDataBundleError(InternalDataBundleErrorCode.APPROVAL_EXPIRED)

    roots = set(approval.allowed_roots)
    unknown = roots - ALL_ROOTS
    if unknown:
        raise InternalDataBundleError(InternalDataBundleErrorCode.UNKNOWN_ROOT, ",".join(sorted(unknown)))

    if roots & NSA_ROOT and roots - NSA_ROOT:
        raise InternalDataBundleError(InternalDataBundleErrorCode.MIXED_ROOTS)

    is_nsa = roots == NSA_ROOT
    if is_nsa != approval.include_nsa:
        raise InternalDataBundleError(InternalDataBundleErrorCode.ROOTS_NSA_FLAG_MISMATCH)

    return approval


def classify_bundle_type(approval: ApprovalRecord) -> str:
    return "nsa" if set(approval.allowed_roots) == NSA_ROOT else "normal"


def validate_signers(
    bundle_type: str,
    signatures: Sequence[SignatureEvidence],
    *,
    now: datetime | None = None,
) -> None:
    if len(signatures) != 2:
        raise InternalDataBundleError(
            InternalDataBundleErrorCode.SIGNER_ROLE_SET_MISMATCH, "expected-exactly-2-signatures"
        )

    reference_time = now or datetime.now(timezone.utc)
    expected_roles = NSA_SIGNER_ROLES if bundle_type == "nsa" else NORMAL_SIGNER_ROLES

    thumbprints = {sig.thumbprint for sig in signatures}
    if len(thumbprints) != 2:
        raise InternalDataBundleError(InternalDataBundleErrorCode.SIGNER_SAME_THUMBPRINT)

    roles = {sig.role for sig in signatures}
    if roles != expected_roles:
        raise InternalDataBundleError(InternalDataBundleErrorCode.SIGNER_ROLE_SET_MISMATCH)

    for sig in signatures:
        if sig.role not in expected_roles:
            raise InternalDataBundleError(InternalDataBundleErrorCode.SIGNER_ROLE_INVALID_FOR_BUNDLE, sig.role)
        if sig.eku_oid != DOCUMENT_SIGNING_EKU_OID:
            raise InternalDataBundleError(InternalDataBundleErrorCode.EKU_MISMATCH, sig.eku_oid)
        if not sig.signature_valid:
            raise InternalDataBundleError(InternalDataBundleErrorCode.SIGNATURE_INVALID, sig.role)
        if not sig.chain_valid:
            raise InternalDataBundleError(InternalDataBundleErrorCode.CHAIN_INVALID, sig.role)
        if reference_time < sig.not_before:
            raise InternalDataBundleError(InternalDataBundleErrorCode.CERT_NOT_YET_VALID, sig.role)
        if reference_time > sig.not_after:
            raise InternalDataBundleError(InternalDataBundleErrorCode.CERT_EXPIRED, sig.role)


def validate_recipient(
    approval: ApprovalRecord,
    recipient: RecipientEvidence,
    *,
    now: datetime | None = None,
) -> None:
    reference_time = now or datetime.now(timezone.utc)
    if recipient.thumbprint != approval.recipient_thumbprint:
        raise InternalDataBundleError(InternalDataBundleErrorCode.RECIPIENT_MISMATCH)
    if recipient.target_environment_id != approval.target_environment_id:
        raise InternalDataBundleError(InternalDataBundleErrorCode.RECIPIENT_ENVIRONMENT_MISMATCH)
    if recipient.eku_oid != EMAIL_PROTECTION_EKU_OID:
        raise InternalDataBundleError(InternalDataBundleErrorCode.EKU_MISMATCH, recipient.eku_oid)
    if not recipient.has_private_key:
        raise InternalDataBundleError(InternalDataBundleErrorCode.RECIPIENT_PRIVATE_KEY_MISSING)
    if reference_time < recipient.not_before:
        raise InternalDataBundleError(InternalDataBundleErrorCode.CERT_NOT_YET_VALID, "recipient")
    if reference_time > recipient.not_after:
        raise InternalDataBundleError(InternalDataBundleErrorCode.CERT_EXPIRED, "recipient")


def validate_aes_oid(oid: str) -> None:
    if oid != AES_256_CBC_OID:
        raise InternalDataBundleError(InternalDataBundleErrorCode.AES_OID_MISMATCH, oid)


def parse_trust_policy(
    raw: bytes,
    *,
    pinned_sha256: str | None,
    now: datetime | None = None,
) -> TrustPolicy:
    if not pinned_sha256:
        raise InternalDataBundleError(InternalDataBundleErrorCode.TRUST_POLICY_DIGEST_ABSENT)

    actual = compute_sha256_hex(raw)
    if actual.lower() != pinned_sha256.lower():
        raise InternalDataBundleError(InternalDataBundleErrorCode.TRUST_POLICY_DIGEST_MISMATCH)

    obj = parse_strict_json_object(raw)
    try:
        policy = TrustPolicy.model_validate(obj)
    except ValidationError as exc:
        raise InternalDataBundleError(InternalDataBundleErrorCode.SCHEMA_VIOLATION, str(exc)) from exc

    if policy.schema_version != SCHEMA_VERSION:
        raise InternalDataBundleError(InternalDataBundleErrorCode.SCHEMA_VIOLATION, "schema_version")

    reference_time = now or datetime.now(timezone.utc)
    if reference_time > policy.expires_at:
        raise InternalDataBundleError(InternalDataBundleErrorCode.TRUST_POLICY_EXPIRED)

    return policy


def validate_approval_against_trust_policy(approval: ApprovalRecord, policy: TrustPolicy) -> None:
    ttl = approval.expires_at - approval.issued_at
    if ttl > timedelta(hours=policy.max_approval_ttl_hours):
        raise InternalDataBundleError(InternalDataBundleErrorCode.TTL_EXCEEDED)
    if not set(approval.allowed_roots).issubset(set(policy.allowed_roots)):
        raise InternalDataBundleError(InternalDataBundleErrorCode.ALLOWED_ROOTS_NOT_SUBSET)


def validate_trust_policy_acl(
    aces: Sequence[AceEntry],
    *,
    inheritance_disabled: bool,
    system_sid: str,
    administrators_sid: str,
    authorized_sid: str,
) -> None:
    if not inheritance_disabled:
        raise InternalDataBundleError(InternalDataBundleErrorCode.ACL_MISMATCH, "inheritance-enabled")
    if any(ace.is_inherited for ace in aces):
        raise InternalDataBundleError(InternalDataBundleErrorCode.ACL_MISMATCH, "inherited-ace-present")

    expected_sids = {system_sid, administrators_sid, authorized_sid}
    actual_sids = [ace.identity_sid for ace in aces]
    if len(aces) != 3 or set(actual_sids) != expected_sids or len(set(actual_sids)) != 3:
        raise InternalDataBundleError(InternalDataBundleErrorCode.ACL_MISMATCH, "unexpected-ace-set")

    for ace in aces:
        if ace.rights != _ACL_READ_RIGHT:
            raise InternalDataBundleError(InternalDataBundleErrorCode.ACL_MISMATCH, f"{ace.identity_sid}:{ace.rights}")


def validate_target_root(target_root: str, allowed_roots: Sequence[str]) -> str:
    normalized_str = target_root.replace("\\", "/")
    if normalized_str.startswith("/") or ":" in normalized_str:
        raise InternalDataBundleError(InternalDataBundleErrorCode.PATH_TRAVERSAL, target_root)
    components = [part for part in normalized_str.split("/") if part != ""]
    if not components:
        raise InternalDataBundleError(InternalDataBundleErrorCode.PATH_TRAVERSAL, target_root)
    if any(part in (".", "..") for part in components):
        raise InternalDataBundleError(InternalDataBundleErrorCode.PATH_TRAVERSAL, target_root)
    top = components[0]
    if top not in allowed_roots:
        raise InternalDataBundleError(InternalDataBundleErrorCode.PATH_ESCAPES_ALLOWED_ROOTS, target_root)
    return top


def validate_inventory(inventory_bytes: bytes, approval: ApprovalRecord) -> dict[str, object]:
    actual = compute_sha256_hex(inventory_bytes)
    if actual != approval.source_inventory_sha256:
        raise InternalDataBundleError(InternalDataBundleErrorCode.INVENTORY_HASH_MISMATCH)
    return parse_strict_json_object(inventory_bytes)


def validate_envelope_entries(entry_names: Sequence[str], allowed_roots: Sequence[str]) -> None:
    if len(entry_names) != len(set(entry_names)):
        raise InternalDataBundleError(InternalDataBundleErrorCode.ENVELOPE_ENTRY_MISMATCH, "duplicate-entry")

    names = set(entry_names)
    missing = REQUIRED_ENVELOPE_ENTRIES - names
    if missing:
        raise InternalDataBundleError(
            InternalDataBundleErrorCode.ENVELOPE_ENTRY_MISMATCH, f"missing:{','.join(sorted(missing))}"
        )

    signature_entries = {name for name in names if name.endswith(".p7s")}
    if len(signature_entries) != 2:
        raise InternalDataBundleError(
            InternalDataBundleErrorCode.SIGNER_ROLE_SET_MISMATCH, "expected-exactly-2-signature-entries"
        )

    content_entries = names - REQUIRED_ENVELOPE_ENTRIES - signature_entries
    for entry in content_entries:
        validate_target_root(entry, allowed_roots)


def _decode_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _decode_datetime_required(value: object) -> datetime:
    parsed = _decode_datetime(value)
    if parsed is None:
        raise InternalDataBundleError(InternalDataBundleErrorCode.SCHEMA_VIOLATION, "missing-datetime")
    return parsed


def _decode_signature(payload: dict[str, object]) -> SignatureEvidence:
    return SignatureEvidence(
        role=str(payload["role"]),
        thumbprint=str(payload["thumbprint"]),
        subject=str(payload["subject"]),
        eku_oid=str(payload["eku_oid"]),
        signature_valid=bool(payload["signature_valid"]),
        chain_valid=bool(payload["chain_valid"]),
        not_before=_decode_datetime_required(payload["not_before"]),
        not_after=_decode_datetime_required(payload["not_after"]),
    )


def _decode_recipient(payload: dict[str, object]) -> RecipientEvidence:
    return RecipientEvidence(
        target_environment_id=str(payload["target_environment_id"]),
        thumbprint=str(payload["thumbprint"]),
        subject=str(payload["subject"]),
        eku_oid=str(payload["eku_oid"]),
        has_private_key=bool(payload["has_private_key"]),
        not_before=_decode_datetime_required(payload["not_before"]),
        not_after=_decode_datetime_required(payload["not_after"]),
    )


def _decode_ace(payload: dict[str, object]) -> AceEntry:
    return AceEntry(
        identity_sid=str(payload["identity_sid"]),
        rights=str(payload["rights"]),
        is_inherited=bool(payload["is_inherited"]),
    )


def dispatch_rpc(request: dict[str, object]) -> dict[str, object]:
    """Single dispatch point the PowerShell CMS layer uses for every
    boundary decision beyond raw approval parsing (dual-role signer
    separation, recipient checks, trust-policy digest pinning, ACL shape,
    envelope entry containment, inventory integrity, AES/EKU OID checks).
    Keeping this in Python -- not reimplemented in PowerShell -- is what
    makes the boundary layer independently unit-testable."""
    import base64

    action = request.get("action")
    now = _decode_datetime(request.get("now"))

    if action == "parse_approval":
        raw = base64.b64decode(str(request["raw_base64"]))
        approval = parse_approval_strict(raw, now=now)
        return {
            "status": "ok",
            "bundle_type": classify_bundle_type(approval),
            "approval": json.loads(approval.model_dump_json()),
        }

    if action == "validate_signers":
        signatures = [_decode_signature(s) for s in cast("list[dict[str, object]]", request["signatures"])]
        validate_signers(str(request["bundle_type"]), signatures, now=now)
        return {"status": "ok"}

    if action == "validate_recipient":
        approval = ApprovalRecord.model_validate(request["approval"])
        recipient = _decode_recipient(cast("dict[str, object]", request["recipient"]))
        validate_recipient(approval, recipient, now=now)
        return {"status": "ok"}

    if action == "validate_trust_policy":
        raw = base64.b64decode(str(request["policy_raw_base64"]))
        pinned = request.get("pinned_sha256")
        policy = parse_trust_policy(raw, pinned_sha256=None if pinned is None else str(pinned), now=now)
        result: dict[str, object] = {"status": "ok", "policy": json.loads(policy.model_dump_json())}
        if "approval" in request:
            approval = ApprovalRecord.model_validate(request["approval"])
            validate_approval_against_trust_policy(approval, policy)
        return result

    if action == "validate_acl":
        aces = [_decode_ace(a) for a in cast("list[dict[str, object]]", request["aces"])]
        validate_trust_policy_acl(
            aces,
            inheritance_disabled=bool(request["inheritance_disabled"]),
            system_sid=str(request["system_sid"]),
            administrators_sid=str(request["administrators_sid"]),
            authorized_sid=str(request["authorized_sid"]),
        )
        return {"status": "ok"}

    if action == "validate_envelope_entries":
        validate_envelope_entries(list(cast("list[str]", request["entry_names"])), list(cast("list[str]", request["allowed_roots"])))
        return {"status": "ok"}

    if action == "validate_inventory":
        raw = base64.b64decode(str(request["inventory_raw_base64"]))
        approval = ApprovalRecord.model_validate(request["approval"])
        inventory = validate_inventory(raw, approval)
        return {"status": "ok", "inventory": inventory}

    if action == "validate_aes_oid":
        validate_aes_oid(str(request["oid"]))
        return {"status": "ok"}

    if action == "validate_target_root":
        top = validate_target_root(str(request["target_root"]), list(cast("list[str]", request["allowed_roots"])))
        return {"status": "ok", "root": top}

    raise InternalDataBundleError(InternalDataBundleErrorCode.SCHEMA_VIOLATION, f"unknown-action:{action}")


def _main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point used by the PowerShell CMS layer.

    Default mode: reads raw approval bytes from stdin, writes canonical
    JSON to stdout on success (exit 0), or an error code to stderr (exit 1).
    This is the only sanctioned way approval bytes are read; ConvertFrom-Json
    alone is never sufficient boundary validation.

    ``--rpc`` mode: reads a single JSON request object from stdin and
    dispatches it via :func:`dispatch_rpc`, covering every other boundary
    decision (dual-role signers, recipient, trust policy digest pin, ACL,
    envelope entries, inventory, AES/EKU OIDs). Writes a JSON response
    object to stdout; exit 0 on ``status: ok``, exit 1 with the error code
    on stderr otherwise.
    """
    args = list(sys.argv[1:] if argv is None else argv)

    if args and args[0] == "--rpc":
        raw_request = sys.stdin.buffer.read()
        try:
            request = json.loads(raw_request.decode("utf-8"))
            response = dispatch_rpc(request)
        except InternalDataBundleError as exc:
            sys.stderr.write(str(exc) + "\n")
            return 1
        except (ValidationError, KeyError, ValueError) as exc:
            sys.stderr.write(f"schema-violation: {exc}\n")
            return 1
        sys.stdout.write(json.dumps(response))
        return 0

    raw = sys.stdin.buffer.read()
    try:
        approval = parse_approval_strict(raw)
    except InternalDataBundleError as exc:
        sys.stderr.write(str(exc) + "\n")
        return 1
    sys.stdout.write(approval.model_dump_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())