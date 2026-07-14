from __future__ import annotations

from pathlib import Path

import pytest

from app.operations.provider_credential_store import (
    ProviderCredentialEnvelope,
    ProviderCredentialStore,
    ProviderCredentialStoreError,
    ProviderCredentialStoreErrorCode,
)

_FIXED_SID = "S-1-5-21-1111111111-2222222222-3333333333-1001"


def _make_store(tmp_path: Path) -> ProviderCredentialStore:
    return ProviderCredentialStore(
        root_dir=tmp_path,
        sid_provider=lambda: _FIXED_SID,
        unsafe_skip_host_validation=True,
    )


def test_store_credential_writes_blob_and_returns_envelope(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    envelope = store.store_credential(
        "test-ref-1",
        b"synthetic-test-secret-value",
        binding_version=1,
        existing_binding_version=None,
    )

    assert isinstance(envelope, ProviderCredentialEnvelope)
    assert envelope.credential_ref == "test-ref-1"
    assert envelope.credential_binding_version == 1
    assert isinstance(envelope.created_at, float)

    blob_path = tmp_path / "test-ref-1.dpapi"
    assert blob_path.exists()
    raw = blob_path.read_bytes()
    assert b"synthetic-test-secret-value" not in raw


def test_load_plaintext_round_trips_exact_secret_bytes(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    secret = b"synthetic-roundtrip-secret-\x00\x01\xff"
    store.store_credential(
        "roundtrip-ref",
        secret,
        binding_version=1,
        existing_binding_version=None,
    )

    recovered = store.load_plaintext("roundtrip-ref")

    assert recovered == secret


def test_get_envelope_returns_metadata_without_plaintext(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    secret = b"synthetic-metadata-secret"
    store.store_credential(
        "metadata-ref",
        secret,
        binding_version=7,
        existing_binding_version=None,
    )

    envelope = store.get_envelope("metadata-ref")

    assert envelope is not None
    assert envelope.credential_binding_version == 7
    assert isinstance(envelope.credential_binding_version, int)
    dumped = envelope.model_dump()
    assert secret not in repr(dumped).encode()
    assert "credential_ref" in dumped
    assert "created_at" in dumped
    assert set(dumped.keys()) == {"credential_ref", "credential_binding_version", "created_at"}


def test_get_envelope_returns_none_for_missing_ref(tmp_path: Path) -> None:
    store = _make_store(tmp_path)

    assert store.get_envelope("does-not-exist") is None


def test_binding_version_immutable_on_mismatch(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    store.store_credential(
        "immutable-ref",
        b"synthetic-first-secret",
        binding_version=1,
        existing_binding_version=None,
    )

    with pytest.raises(ProviderCredentialStoreError) as exc_info:
        store.store_credential(
            "immutable-ref",
            b"synthetic-second-secret",
            binding_version=2,
            existing_binding_version=1,
        )

    assert exc_info.value.code == ProviderCredentialStoreErrorCode.BINDING_VERSION_IMMUTABLE


def test_binding_version_immutable_on_existing_mismatch(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    store.store_credential(
        "immutable-ref-2",
        b"synthetic-first-secret",
        binding_version=3,
        existing_binding_version=None,
    )

    with pytest.raises(ProviderCredentialStoreError) as exc_info:
        store.store_credential(
            "immutable-ref-2",
            b"synthetic-second-secret",
            binding_version=3,
            existing_binding_version=99,
        )

    assert exc_info.value.code == ProviderCredentialStoreErrorCode.BINDING_VERSION_IMMUTABLE


def test_fresh_ref_rejects_non_null_existing_binding_version(tmp_path: Path) -> None:
    store = _make_store(tmp_path)

    with pytest.raises(ProviderCredentialStoreError) as exc_info:
        store.store_credential(
            "brand-new-ref",
            b"synthetic-secret",
            binding_version=1,
            existing_binding_version=1,
        )

    assert exc_info.value.code == ProviderCredentialStoreErrorCode.CREDENTIAL_NOT_FOUND


def test_envelope_corruption_truncated_magic_raises_envelope_corrupt(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    store.store_credential(
        "corrupt-ref",
        b"synthetic-secret",
        binding_version=1,
        existing_binding_version=None,
    )
    blob_path = tmp_path / "corrupt-ref.dpapi"
    blob_path.write_bytes(b"AEROONE-PC")  # truncated magic

    with pytest.raises(ProviderCredentialStoreError) as exc_info:
        store.get_envelope("corrupt-ref")
    assert exc_info.value.code == ProviderCredentialStoreErrorCode.ENVELOPE_CORRUPT

    with pytest.raises(ProviderCredentialStoreError) as exc_info2:
        store.load_plaintext("corrupt-ref")
    assert exc_info2.value.code == ProviderCredentialStoreErrorCode.ENVELOPE_CORRUPT


def test_envelope_corruption_garbage_magic_raises_envelope_corrupt(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    store.store_credential(
        "corrupt-ref-2",
        b"synthetic-secret",
        binding_version=1,
        existing_binding_version=None,
    )
    blob_path = tmp_path / "corrupt-ref-2.dpapi"
    blob_path.write_bytes(b"NOT-A-VALID-MAGIC-HEADER\nfoo\nbar")

    with pytest.raises(ProviderCredentialStoreError) as exc_info:
        store.get_envelope("corrupt-ref-2")
    assert exc_info.value.code == ProviderCredentialStoreErrorCode.ENVELOPE_CORRUPT


def test_delete_credential_removes_blob_and_second_delete_is_noop(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    store.store_credential(
        "delete-ref",
        b"synthetic-secret",
        binding_version=1,
        existing_binding_version=None,
    )
    blob_path = tmp_path / "delete-ref.dpapi"
    assert blob_path.exists()

    store.delete_credential("delete-ref")
    assert not blob_path.exists()
    assert store.get_envelope("delete-ref") is None

    # Second delete is a no-op: no exception raised.
    store.delete_credential("delete-ref")
    assert not blob_path.exists()


@pytest.mark.parametrize(
    "bad_ref",
    [
        "../escape",
        "..\\escape",
        "a/b",
        "a\\b",
        "",
        "has space",
        "bad!char",
        "a" * 200,
    ],
)
def test_invalid_ref_raises_invalid_ref(tmp_path: Path, bad_ref: str) -> None:
    store = _make_store(tmp_path)

    with pytest.raises(ProviderCredentialStoreError) as exc_info:
        store.store_credential(
            bad_ref,
            b"synthetic-secret",
            binding_version=1,
            existing_binding_version=None,
        )

    assert exc_info.value.code == ProviderCredentialStoreErrorCode.INVALID_REF


def test_unsafe_skip_host_validation_requires_explicit_root_dir() -> None:
    with pytest.raises(ValueError):
        ProviderCredentialStore(
            root_dir=None,
            sid_provider=lambda: _FIXED_SID,
            unsafe_skip_host_validation=True,
        )
