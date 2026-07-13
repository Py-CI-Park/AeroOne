from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from app.operations.internal_data_bundle_contracts import (
    AceEntry,
    ApprovalRecord,
    InternalDataBundleError,
    InternalDataBundleErrorCode,
    RecipientEvidence,
    SignatureEvidence,
    TrustPolicy,
    classify_bundle_type,
    compute_sha256_hex,
    parse_approval_strict,
    parse_strict_json_object,
    parse_trust_policy,
    validate_aes_oid,
    validate_approval_against_trust_policy,
    validate_envelope_entries,
    validate_inventory,
    validate_recipient,
    validate_signers,
    validate_target_root,
    validate_trust_policy_acl,
)

_NOW = datetime(2026, 7, 11, 12, 0, 0, tzinfo=timezone.utc)
_RECIPIENT_THUMBPRINT = "A1B2C3D4E5F60718293A4B5C6D7E8F9001020304"
_OWNER_THUMBPRINT = "11111111111111111111111111111111111111AA"
_SECURITY_THUMBPRINT = "22222222222222222222222222222222222222BB"
_NSA_OWNER_THUMBPRINT = "33333333333333333333333333333333333333CC"

_SYSTEM_SID = "S-1-5-18"
_ADMINISTRATORS_SID = "S-1-5-32-544"
_AUTHORIZED_SID = "S-1-5-21-1-2-3-1001"
_UNAUTHORIZED_SID = "S-1-5-21-9-9-9-9999"


def _approval_dict(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "schema_version": "1.0",
        "request_id": "req-0001",
        "ticket_id": "TCK-42",
        "purpose": "quarterly civil aircraft data refresh",
        "issued_at": "2026-07-11T10:00:00Z",
        "expires_at": "2026-07-11T18:00:00Z",
        "target_environment_id": "env-prod-01",
        "recipient_thumbprint": _RECIPIENT_THUMBPRINT,
        "allowed_roots": ["civil_aircraft", "document"],
        "source_inventory_sha256": "a" * 64,
        "include_nsa": False,
    }
    base.update(overrides)
    return base


def _approval_bytes(**overrides: object) -> bytes:
    return json.dumps(_approval_dict(**overrides)).encode("utf-8")


def _nsa_approval_bytes(**overrides: object) -> bytes:
    overrides.setdefault("allowed_roots", ["nsa"])
    overrides.setdefault("include_nsa", True)
    overrides.setdefault("source_inventory_sha256", "b" * 64)
    return _approval_bytes(**overrides)


def _signature(role: str, thumbprint: str, *, valid: bool = True, chain: bool = True,
                eku: str = "1.3.6.1.4.1.311.10.3.12") -> SignatureEvidence:
    return SignatureEvidence(
        role=role,
        thumbprint=thumbprint,
        subject=f"CN={role}",
        eku_oid=eku,
        signature_valid=valid,
        chain_valid=chain,
        not_before=_NOW - timedelta(days=30),
        not_after=_NOW + timedelta(days=30),
    )


def _recipient(**overrides: object) -> RecipientEvidence:
    base = dict(
        target_environment_id="env-prod-01",
        thumbprint=_RECIPIENT_THUMBPRINT,
        subject="CN=recipient",
        eku_oid="1.3.6.1.5.5.7.3.4",
        has_private_key=True,
        not_before=_NOW - timedelta(days=30),
        not_after=_NOW + timedelta(days=30),
    )
    base.update(overrides)
    return RecipientEvidence(**base)


# ---------------------------------------------------------------------------
# Strict JSON parsing
# ---------------------------------------------------------------------------


def test_strict_parser_rejects_duplicate_keys() -> None:
    raw = b'{"a": 1, "a": 2}'
    with pytest.raises(InternalDataBundleError) as excinfo:
        parse_strict_json_object(raw)
    assert excinfo.value.code == InternalDataBundleErrorCode.DUPLICATE_JSON_KEY


def test_strict_parser_rejects_invalid_utf8() -> None:
    with pytest.raises(InternalDataBundleError) as excinfo:
        parse_strict_json_object(b"\xff\xfe{}")
    assert excinfo.value.code == InternalDataBundleErrorCode.INVALID_JSON


def test_strict_parser_rejects_non_object_root() -> None:
    with pytest.raises(InternalDataBundleError) as excinfo:
        parse_strict_json_object(b"[1, 2, 3]")
    assert excinfo.value.code == InternalDataBundleErrorCode.INVALID_JSON


def test_strict_parser_rejects_malformed_json_ciphertext_tamper_surrogate() -> None:
    # Represents the boundary effect of ciphertext bit-flip corruption
    # surfacing as unparsable plaintext once decrypted.
    corrupted = _approval_bytes()[:-1]
    with pytest.raises(InternalDataBundleError) as excinfo:
        parse_strict_json_object(corrupted)
    assert excinfo.value.code == InternalDataBundleErrorCode.INVALID_JSON


# ---------------------------------------------------------------------------
# Approval parsing / schema exactness / TTL / roots
# ---------------------------------------------------------------------------


def test_parse_approval_happy_normal() -> None:
    approval = parse_approval_strict(_approval_bytes(), now=_NOW)
    assert isinstance(approval, ApprovalRecord)
    assert classify_bundle_type(approval) == "normal"


def test_parse_approval_happy_nsa() -> None:
    approval = parse_approval_strict(_nsa_approval_bytes(), now=_NOW)
    assert classify_bundle_type(approval) == "nsa"


def test_parse_approval_rejects_additional_property() -> None:
    with pytest.raises(InternalDataBundleError) as excinfo:
        parse_approval_strict(_approval_bytes(extra_field="nope"), now=_NOW)
    assert excinfo.value.code == InternalDataBundleErrorCode.SCHEMA_VIOLATION


def test_parse_approval_rejects_missing_field() -> None:
    obj = _approval_dict()
    del obj["purpose"]
    raw = json.dumps(obj).encode("utf-8")
    with pytest.raises(InternalDataBundleError) as excinfo:
        parse_approval_strict(raw, now=_NOW)
    assert excinfo.value.code == InternalDataBundleErrorCode.SCHEMA_VIOLATION


def test_parse_approval_rejects_duplicate_key() -> None:
    raw = b'{"schema_version": "1.0", "schema_version": "1.0"}'
    with pytest.raises(InternalDataBundleError) as excinfo:
        parse_approval_strict(raw, now=_NOW)
    assert excinfo.value.code == InternalDataBundleErrorCode.DUPLICATE_JSON_KEY


def test_parse_approval_rejects_ttl_over_24h() -> None:
    raw = _approval_bytes(issued_at="2026-07-11T00:00:00Z", expires_at="2026-07-12T00:00:01Z")
    with pytest.raises(InternalDataBundleError) as excinfo:
        parse_approval_strict(raw, now=_NOW)
    assert excinfo.value.code == InternalDataBundleErrorCode.TTL_EXCEEDED


def test_parse_approval_allows_ttl_exactly_24h() -> None:
    raw = _approval_bytes(issued_at="2026-07-11T00:00:00Z", expires_at="2026-07-12T00:00:00Z")
    approval = parse_approval_strict(raw, now=datetime(2026, 7, 11, 1, 0, tzinfo=timezone.utc))
    assert approval.request_id == "req-0001"


def test_parse_approval_rejects_expires_before_issued() -> None:
    raw = _approval_bytes(issued_at="2026-07-11T10:00:00Z", expires_at="2026-07-11T09:00:00Z")
    with pytest.raises(InternalDataBundleError) as excinfo:
        parse_approval_strict(raw, now=_NOW)
    assert excinfo.value.code == InternalDataBundleErrorCode.EXPIRES_BEFORE_ISSUED


def test_parse_approval_rejects_expired_approval() -> None:
    raw = _approval_bytes()
    with pytest.raises(InternalDataBundleError) as excinfo:
        parse_approval_strict(raw, now=datetime(2026, 7, 12, 0, 0, tzinfo=timezone.utc))
    assert excinfo.value.code == InternalDataBundleErrorCode.APPROVAL_EXPIRED


def test_parse_approval_rejects_future_approval() -> None:
    raw = _approval_bytes()
    with pytest.raises(InternalDataBundleError) as excinfo:
        parse_approval_strict(raw, now=datetime(2026, 7, 11, 0, 0, tzinfo=timezone.utc))
    assert excinfo.value.code == InternalDataBundleErrorCode.APPROVAL_NOT_YET_VALID


def test_parse_approval_rejects_mixed_roots() -> None:
    raw = _approval_bytes(allowed_roots=["nsa", "document"], include_nsa=True)
    with pytest.raises(InternalDataBundleError) as excinfo:
        parse_approval_strict(raw, now=_NOW)
    assert excinfo.value.code == InternalDataBundleErrorCode.MIXED_ROOTS


def test_parse_approval_rejects_nsa_flag_mismatch_true() -> None:
    raw = _approval_bytes(include_nsa=True)
    with pytest.raises(InternalDataBundleError) as excinfo:
        parse_approval_strict(raw, now=_NOW)
    assert excinfo.value.code == InternalDataBundleErrorCode.ROOTS_NSA_FLAG_MISMATCH


def test_parse_approval_rejects_nsa_flag_mismatch_false() -> None:
    raw = _approval_bytes(allowed_roots=["nsa"], include_nsa=False)
    with pytest.raises(InternalDataBundleError) as excinfo:
        parse_approval_strict(raw, now=_NOW)
    assert excinfo.value.code == InternalDataBundleErrorCode.ROOTS_NSA_FLAG_MISMATCH


def test_parse_approval_rejects_unknown_root() -> None:
    raw = _approval_bytes(allowed_roots=["newsletter", "not-a-real-root"])
    with pytest.raises(InternalDataBundleError) as excinfo:
        parse_approval_strict(raw, now=_NOW)
    assert excinfo.value.code == InternalDataBundleErrorCode.UNKNOWN_ROOT


def test_parse_approval_rejects_duplicate_roots() -> None:
    raw = _approval_bytes(allowed_roots=["document", "document"])
    with pytest.raises(InternalDataBundleError) as excinfo:
        parse_approval_strict(raw, now=_NOW)
    assert excinfo.value.code == InternalDataBundleErrorCode.SCHEMA_VIOLATION


def test_parse_approval_rejects_bad_thumbprint_format() -> None:
    raw = _approval_bytes(recipient_thumbprint="not-hex")
    with pytest.raises(InternalDataBundleError) as excinfo:
        parse_approval_strict(raw, now=_NOW)
    assert excinfo.value.code == InternalDataBundleErrorCode.SCHEMA_VIOLATION


# ---------------------------------------------------------------------------
# Dual-role signer validation
# ---------------------------------------------------------------------------


def test_validate_signers_happy_normal() -> None:
    validate_signers(
        "normal",
        [_signature("data_owner", _OWNER_THUMBPRINT), _signature("security_officer", _SECURITY_THUMBPRINT)],
        now=_NOW,
    )


def test_validate_signers_happy_nsa() -> None:
    validate_signers(
        "nsa",
        [_signature("nsa_data_owner", _NSA_OWNER_THUMBPRINT), _signature("security_officer", _SECURITY_THUMBPRINT)],
        now=_NOW,
    )


def test_validate_signers_rejects_same_signer_dual_role() -> None:
    with pytest.raises(InternalDataBundleError) as excinfo:
        validate_signers(
            "normal",
            [
                _signature("data_owner", _OWNER_THUMBPRINT),
                _signature("security_officer", _OWNER_THUMBPRINT),
            ],
            now=_NOW,
        )
    assert excinfo.value.code == InternalDataBundleErrorCode.SIGNER_SAME_THUMBPRINT


def test_validate_signers_rejects_normal_owner_signing_nsa_bundle() -> None:
    with pytest.raises(InternalDataBundleError) as excinfo:
        validate_signers(
            "nsa",
            [_signature("data_owner", _OWNER_THUMBPRINT), _signature("security_officer", _SECURITY_THUMBPRINT)],
            now=_NOW,
        )
    assert excinfo.value.code == InternalDataBundleErrorCode.SIGNER_ROLE_SET_MISMATCH


def test_validate_signers_rejects_wrong_role_set() -> None:
    with pytest.raises(InternalDataBundleError) as excinfo:
        validate_signers(
            "normal",
            [_signature("data_owner", _OWNER_THUMBPRINT), _signature("nsa_data_owner", _NSA_OWNER_THUMBPRINT)],
            now=_NOW,
        )
    assert excinfo.value.code == InternalDataBundleErrorCode.SIGNER_ROLE_SET_MISMATCH


def test_validate_signers_rejects_not_exactly_two() -> None:
    with pytest.raises(InternalDataBundleError) as excinfo:
        validate_signers("normal", [_signature("data_owner", _OWNER_THUMBPRINT)], now=_NOW)
    assert excinfo.value.code == InternalDataBundleErrorCode.SIGNER_ROLE_SET_MISMATCH


def test_validate_signers_rejects_signature_bit_flip() -> None:
    with pytest.raises(InternalDataBundleError) as excinfo:
        validate_signers(
            "normal",
            [
                _signature("data_owner", _OWNER_THUMBPRINT, valid=False),
                _signature("security_officer", _SECURITY_THUMBPRINT),
            ],
            now=_NOW,
        )
    assert excinfo.value.code == InternalDataBundleErrorCode.SIGNATURE_INVALID


def test_validate_signers_rejects_broken_chain() -> None:
    with pytest.raises(InternalDataBundleError) as excinfo:
        validate_signers(
            "normal",
            [
                _signature("data_owner", _OWNER_THUMBPRINT, chain=False),
                _signature("security_officer", _SECURITY_THUMBPRINT),
            ],
            now=_NOW,
        )
    assert excinfo.value.code == InternalDataBundleErrorCode.CHAIN_INVALID


def test_validate_signers_rejects_wrong_eku() -> None:
    with pytest.raises(InternalDataBundleError) as excinfo:
        validate_signers(
            "normal",
            [
                _signature("data_owner", _OWNER_THUMBPRINT, eku="1.3.6.1.5.5.7.3.4"),
                _signature("security_officer", _SECURITY_THUMBPRINT),
            ],
            now=_NOW,
        )
    assert excinfo.value.code == InternalDataBundleErrorCode.EKU_MISMATCH


def test_validate_signers_rejects_expired_signer_cert() -> None:
    expired = SignatureEvidence(
        role="data_owner",
        thumbprint=_OWNER_THUMBPRINT,
        subject="CN=data_owner",
        eku_oid="1.3.6.1.4.1.311.10.3.12",
        signature_valid=True,
        chain_valid=True,
        not_before=_NOW - timedelta(days=400),
        not_after=_NOW - timedelta(days=1),
    )
    with pytest.raises(InternalDataBundleError) as excinfo:
        validate_signers("normal", [expired, _signature("security_officer", _SECURITY_THUMBPRINT)], now=_NOW)
    assert excinfo.value.code == InternalDataBundleErrorCode.CERT_EXPIRED


def test_validate_signers_rejects_not_yet_valid_signer_cert() -> None:
    future = SignatureEvidence(
        role="data_owner",
        thumbprint=_OWNER_THUMBPRINT,
        subject="CN=data_owner",
        eku_oid="1.3.6.1.4.1.311.10.3.12",
        signature_valid=True,
        chain_valid=True,
        not_before=_NOW + timedelta(days=1),
        not_after=_NOW + timedelta(days=400),
    )
    with pytest.raises(InternalDataBundleError) as excinfo:
        validate_signers("normal", [future, _signature("security_officer", _SECURITY_THUMBPRINT)], now=_NOW)
    assert excinfo.value.code == InternalDataBundleErrorCode.CERT_NOT_YET_VALID


# ---------------------------------------------------------------------------
# Recipient validation
# ---------------------------------------------------------------------------


def test_validate_recipient_happy() -> None:
    approval = parse_approval_strict(_approval_bytes(), now=_NOW)
    validate_recipient(approval, _recipient(), now=_NOW)


def test_validate_recipient_rejects_thumbprint_mismatch() -> None:
    approval = parse_approval_strict(_approval_bytes(), now=_NOW)
    with pytest.raises(InternalDataBundleError) as excinfo:
        validate_recipient(approval, _recipient(thumbprint="0" * 40), now=_NOW)
    assert excinfo.value.code == InternalDataBundleErrorCode.RECIPIENT_MISMATCH


def test_validate_recipient_rejects_environment_mismatch() -> None:
    approval = parse_approval_strict(_approval_bytes(), now=_NOW)
    with pytest.raises(InternalDataBundleError) as excinfo:
        validate_recipient(approval, _recipient(target_environment_id="env-other"), now=_NOW)
    assert excinfo.value.code == InternalDataBundleErrorCode.RECIPIENT_ENVIRONMENT_MISMATCH


def test_validate_recipient_rejects_missing_private_key() -> None:
    approval = parse_approval_strict(_approval_bytes(), now=_NOW)
    with pytest.raises(InternalDataBundleError) as excinfo:
        validate_recipient(approval, _recipient(has_private_key=False), now=_NOW)
    assert excinfo.value.code == InternalDataBundleErrorCode.RECIPIENT_PRIVATE_KEY_MISSING


def test_validate_recipient_rejects_wrong_eku() -> None:
    approval = parse_approval_strict(_approval_bytes(), now=_NOW)
    with pytest.raises(InternalDataBundleError) as excinfo:
        validate_recipient(approval, _recipient(eku_oid="1.3.6.1.4.1.311.10.3.12"), now=_NOW)
    assert excinfo.value.code == InternalDataBundleErrorCode.EKU_MISMATCH


def test_validate_recipient_rejects_expired_cert() -> None:
    approval = parse_approval_strict(_approval_bytes(), now=_NOW)
    with pytest.raises(InternalDataBundleError) as excinfo:
        validate_recipient(
            approval,
            _recipient(not_before=_NOW - timedelta(days=400), not_after=_NOW - timedelta(days=1)),
            now=_NOW,
        )
    assert excinfo.value.code == InternalDataBundleErrorCode.CERT_EXPIRED


# ---------------------------------------------------------------------------
# AES OID
# ---------------------------------------------------------------------------


def test_validate_aes_oid_accepts_exact() -> None:
    validate_aes_oid("2.16.840.1.101.3.4.1.42")


def test_validate_aes_oid_rejects_other_algorithm() -> None:
    with pytest.raises(InternalDataBundleError) as excinfo:
        validate_aes_oid("2.16.840.1.101.3.4.1.2")  # AES-128-CBC
    assert excinfo.value.code == InternalDataBundleErrorCode.AES_OID_MISMATCH


# ---------------------------------------------------------------------------
# Trust policy / registry digest pin
# ---------------------------------------------------------------------------


def _trust_policy_dict(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "schema_version": "1.0",
        "policy_id": "policy-2026-07",
        "expires_at": "2026-08-01T00:00:00Z",
        "max_approval_ttl_hours": 24,
        "allowed_roots": ["newsletter", "civil_aircraft", "document", "nsa"],
        "signers": [
            {
                "role": "data_owner",
                "thumbprint": _OWNER_THUMBPRINT,
                "subject": "CN=data_owner",
                "eku_oid": "1.3.6.1.4.1.311.10.3.12",
            },
            {
                "role": "security_officer",
                "thumbprint": _SECURITY_THUMBPRINT,
                "subject": "CN=security_officer",
                "eku_oid": "1.3.6.1.4.1.311.10.3.12",
            },
        ],
        "recipients": [
            {
                "target_environment_id": "env-prod-01",
                "thumbprint": _RECIPIENT_THUMBPRINT,
                "subject": "CN=recipient",
                "eku_oid": "1.3.6.1.5.5.7.3.4",
            }
        ],
    }
    base.update(overrides)
    return base


def _trust_policy_bytes(**overrides: object) -> bytes:
    return json.dumps(_trust_policy_dict(**overrides)).encode("utf-8")


def test_parse_trust_policy_happy() -> None:
    raw = _trust_policy_bytes()
    digest = compute_sha256_hex(raw)
    policy = parse_trust_policy(raw, pinned_sha256=digest, now=_NOW)
    assert isinstance(policy, TrustPolicy)


def test_parse_trust_policy_rejects_absent_registry_pin() -> None:
    raw = _trust_policy_bytes()
    with pytest.raises(InternalDataBundleError) as excinfo:
        parse_trust_policy(raw, pinned_sha256=None, now=_NOW)
    assert excinfo.value.code == InternalDataBundleErrorCode.TRUST_POLICY_DIGEST_ABSENT


def test_parse_trust_policy_rejects_digest_mismatch() -> None:
    raw = _trust_policy_bytes()
    with pytest.raises(InternalDataBundleError) as excinfo:
        parse_trust_policy(raw, pinned_sha256="0" * 64, now=_NOW)
    assert excinfo.value.code == InternalDataBundleErrorCode.TRUST_POLICY_DIGEST_MISMATCH


def test_parse_trust_policy_rejects_expired_policy() -> None:
    raw = _trust_policy_bytes(expires_at="2026-01-01T00:00:00Z")
    digest = compute_sha256_hex(raw)
    with pytest.raises(InternalDataBundleError) as excinfo:
        parse_trust_policy(raw, pinned_sha256=digest, now=_NOW)
    assert excinfo.value.code == InternalDataBundleErrorCode.TRUST_POLICY_EXPIRED


def test_parse_trust_policy_rejects_additional_property() -> None:
    raw = _trust_policy_bytes(unexpected="nope")
    digest = compute_sha256_hex(raw)
    with pytest.raises(InternalDataBundleError) as excinfo:
        parse_trust_policy(raw, pinned_sha256=digest, now=_NOW)
    assert excinfo.value.code == InternalDataBundleErrorCode.SCHEMA_VIOLATION


def test_validate_approval_against_trust_policy_happy() -> None:
    approval = parse_approval_strict(_approval_bytes(), now=_NOW)
    raw = _trust_policy_bytes()
    policy = parse_trust_policy(raw, pinned_sha256=compute_sha256_hex(raw), now=_NOW)
    validate_approval_against_trust_policy(approval, policy)


def test_validate_approval_against_trust_policy_rejects_roots_not_subset() -> None:
    approval = parse_approval_strict(_approval_bytes(allowed_roots=["newsletter"]), now=_NOW)
    raw = _trust_policy_bytes(allowed_roots=["document"])
    policy = parse_trust_policy(raw, pinned_sha256=compute_sha256_hex(raw), now=_NOW)
    with pytest.raises(InternalDataBundleError) as excinfo:
        validate_approval_against_trust_policy(approval, policy)
    assert excinfo.value.code == InternalDataBundleErrorCode.ALLOWED_ROOTS_NOT_SUBSET


def test_validate_approval_against_trust_policy_rejects_ttl_over_policy_max() -> None:
    approval = parse_approval_strict(
        _approval_bytes(issued_at="2026-07-11T00:00:00Z", expires_at="2026-07-11T12:00:00Z"),
        now=datetime(2026, 7, 11, 1, tzinfo=timezone.utc),
    )
    raw = _trust_policy_bytes(max_approval_ttl_hours=6)
    policy = parse_trust_policy(raw, pinned_sha256=compute_sha256_hex(raw), now=_NOW)
    with pytest.raises(InternalDataBundleError) as excinfo:
        validate_approval_against_trust_policy(approval, policy)
    assert excinfo.value.code == InternalDataBundleErrorCode.TTL_EXCEEDED


# ---------------------------------------------------------------------------
# ACL exactness (SYSTEM + Administrators + one authorized SID, Read-only,
# inheritance disabled)
# ---------------------------------------------------------------------------


def _exact_aces() -> list[AceEntry]:
    return [
        AceEntry(identity_sid=_SYSTEM_SID, rights="Read", is_inherited=False),
        AceEntry(identity_sid=_ADMINISTRATORS_SID, rights="Read", is_inherited=False),
        AceEntry(identity_sid=_AUTHORIZED_SID, rights="Read", is_inherited=False),
    ]


def test_validate_acl_happy() -> None:
    validate_trust_policy_acl(
        _exact_aces(),
        inheritance_disabled=True,
        system_sid=_SYSTEM_SID,
        administrators_sid=_ADMINISTRATORS_SID,
        authorized_sid=_AUTHORIZED_SID,
    )


def test_validate_acl_rejects_broad_extra_ace() -> None:
    aces = _exact_aces() + [AceEntry(identity_sid="S-1-1-0", rights="Read", is_inherited=False)]  # Everyone
    with pytest.raises(InternalDataBundleError) as excinfo:
        validate_trust_policy_acl(
            aces,
            inheritance_disabled=True,
            system_sid=_SYSTEM_SID,
            administrators_sid=_ADMINISTRATORS_SID,
            authorized_sid=_AUTHORIZED_SID,
        )
    assert excinfo.value.code == InternalDataBundleErrorCode.ACL_MISMATCH


def test_validate_acl_rejects_unauthorized_sid() -> None:
    aces = [
        AceEntry(identity_sid=_SYSTEM_SID, rights="Read", is_inherited=False),
        AceEntry(identity_sid=_ADMINISTRATORS_SID, rights="Read", is_inherited=False),
        AceEntry(identity_sid=_UNAUTHORIZED_SID, rights="Read", is_inherited=False),
    ]
    with pytest.raises(InternalDataBundleError) as excinfo:
        validate_trust_policy_acl(
            aces,
            inheritance_disabled=True,
            system_sid=_SYSTEM_SID,
            administrators_sid=_ADMINISTRATORS_SID,
            authorized_sid=_AUTHORIZED_SID,
        )
    assert excinfo.value.code == InternalDataBundleErrorCode.ACL_MISMATCH


def test_validate_acl_rejects_write_rights() -> None:
    aces = _exact_aces()
    aces[2] = AceEntry(identity_sid=_AUTHORIZED_SID, rights="FullControl", is_inherited=False)
    with pytest.raises(InternalDataBundleError) as excinfo:
        validate_trust_policy_acl(
            aces,
            inheritance_disabled=True,
            system_sid=_SYSTEM_SID,
            administrators_sid=_ADMINISTRATORS_SID,
            authorized_sid=_AUTHORIZED_SID,
        )
    assert excinfo.value.code == InternalDataBundleErrorCode.ACL_MISMATCH


def test_validate_acl_rejects_inherited_ace() -> None:
    aces = _exact_aces()
    aces[0] = AceEntry(identity_sid=_SYSTEM_SID, rights="Read", is_inherited=True)
    with pytest.raises(InternalDataBundleError) as excinfo:
        validate_trust_policy_acl(
            aces,
            inheritance_disabled=True,
            system_sid=_SYSTEM_SID,
            administrators_sid=_ADMINISTRATORS_SID,
            authorized_sid=_AUTHORIZED_SID,
        )
    assert excinfo.value.code == InternalDataBundleErrorCode.ACL_MISMATCH


def test_validate_acl_rejects_inheritance_enabled() -> None:
    with pytest.raises(InternalDataBundleError) as excinfo:
        validate_trust_policy_acl(
            _exact_aces(),
            inheritance_disabled=False,
            system_sid=_SYSTEM_SID,
            administrators_sid=_ADMINISTRATORS_SID,
            authorized_sid=_AUTHORIZED_SID,
        )
    assert excinfo.value.code == InternalDataBundleErrorCode.ACL_MISMATCH


# ---------------------------------------------------------------------------
# Path traversal / allowed-roots containment
# ---------------------------------------------------------------------------


def test_validate_target_root_happy() -> None:
    assert validate_target_root("civil_aircraft/2026/inventory.json", ["civil_aircraft", "document"]) == "civil_aircraft"


@pytest.mark.parametrize(
    "path",
    [
        "../civil_aircraft/escape.json",
        "civil_aircraft/../../etc/passwd",
        "/etc/passwd",
        "C:\\Windows\\System32\\evil.dll",
        "civil_aircraft/./file.json",
    ],
)
def test_validate_target_root_rejects_traversal(path: str) -> None:
    with pytest.raises(InternalDataBundleError) as excinfo:
        validate_target_root(path, ["civil_aircraft", "document"])
    assert excinfo.value.code == InternalDataBundleErrorCode.PATH_TRAVERSAL


def test_validate_target_root_rejects_root_not_allowed() -> None:
    with pytest.raises(InternalDataBundleError) as excinfo:
        validate_target_root("nsa/leak.json", ["civil_aircraft", "document"])
    assert excinfo.value.code == InternalDataBundleErrorCode.PATH_ESCAPES_ALLOWED_ROOTS


# ---------------------------------------------------------------------------
# Inventory integrity
# ---------------------------------------------------------------------------


def test_validate_inventory_happy() -> None:
    inventory_bytes = b'{"files": ["a.json"]}'
    approval = parse_approval_strict(
        _approval_bytes(source_inventory_sha256=compute_sha256_hex(inventory_bytes)), now=_NOW
    )
    inventory = validate_inventory(inventory_bytes, approval)
    assert inventory == {"files": ["a.json"]}


def test_validate_inventory_rejects_mutation() -> None:
    inventory_bytes = b'{"files": ["a.json"]}'
    approval = parse_approval_strict(
        _approval_bytes(source_inventory_sha256=compute_sha256_hex(inventory_bytes)), now=_NOW
    )
    mutated = b'{"files": ["a.json", "b.json"]}'
    with pytest.raises(InternalDataBundleError) as excinfo:
        validate_inventory(mutated, approval)
    assert excinfo.value.code == InternalDataBundleErrorCode.INVENTORY_HASH_MISMATCH


# ---------------------------------------------------------------------------
# Envelope inner entry set
# ---------------------------------------------------------------------------


def test_validate_envelope_entries_happy() -> None:
    validate_envelope_entries(
        ["approval.json", "inventory.json", "data_owner.p7s", "security_officer.p7s", "document/report.pdf"],
        ["document"],
    )


def test_validate_envelope_entries_rejects_missing_inventory() -> None:
    with pytest.raises(InternalDataBundleError) as excinfo:
        validate_envelope_entries(["approval.json", "a.p7s", "b.p7s"], ["document"])
    assert excinfo.value.code == InternalDataBundleErrorCode.ENVELOPE_ENTRY_MISMATCH


def test_validate_envelope_entries_rejects_wrong_signature_count() -> None:
    with pytest.raises(InternalDataBundleError) as excinfo:
        validate_envelope_entries(["approval.json", "inventory.json", "a.p7s"], ["document"])
    assert excinfo.value.code == InternalDataBundleErrorCode.SIGNER_ROLE_SET_MISMATCH


def test_validate_envelope_entries_rejects_content_outside_allowed_roots() -> None:
    with pytest.raises(InternalDataBundleError) as excinfo:
        validate_envelope_entries(
            ["approval.json", "inventory.json", "a.p7s", "b.p7s", "nsa/leak.json"],
            ["document"],
        )
    assert excinfo.value.code == InternalDataBundleErrorCode.PATH_ESCAPES_ALLOWED_ROOTS


def test_validate_envelope_entries_rejects_path_traversal_content() -> None:
    with pytest.raises(InternalDataBundleError) as excinfo:
        validate_envelope_entries(
            ["approval.json", "inventory.json", "a.p7s", "b.p7s", "../escape.json"],
            ["document"],
        )
    assert excinfo.value.code == InternalDataBundleErrorCode.PATH_TRAVERSAL


def test_validate_envelope_entries_rejects_duplicate_entry_names() -> None:
    with pytest.raises(InternalDataBundleError) as excinfo:
        validate_envelope_entries(
            ["approval.json", "approval.json", "inventory.json", "a.p7s", "b.p7s"],
            ["document"],
        )
    assert excinfo.value.code == InternalDataBundleErrorCode.ENVELOPE_ENTRY_MISMATCH
