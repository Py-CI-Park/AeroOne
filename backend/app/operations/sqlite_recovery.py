from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import os
from pathlib import Path
import sqlite3
from typing import ClassVar, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.operations.sqlite_recovery_snapshot import (
    RecoveryErrorCode,
    SqliteRecoveryError,
    snapshot_bytes,
    snapshot_connection,
)

from app.operations.windows_dpapi import (
    DpapiPurpose,
    protect_for_current_user,
    unprotect_for_current_user,
)

class DatabaseRecoveryEnvelope(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, strict=True, extra="forbid")

    schema_version: Literal[1] = 1
    artifact_type: Literal["database-recovery"] = "database-recovery"
    rotation_id: UUID
    database_id: UUID
    snapshot_size: int = Field(ge=1)
    snapshot_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    snapshot_base64: str = Field(repr=False)


def _write_new_durable(path: Path, payload: bytes | bytearray) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    descriptor = os.open(path, flags, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        _ = stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def _write_precreated_durable(path: Path, payload: bytes | bytearray) -> None:
    file_state = path.stat()
    if file_state.st_size != 0 or file_state.st_nlink != 1:
        raise SqliteRecoveryError(RecoveryErrorCode.ARTIFACT_INVALID)
    flags = os.O_WRONLY | os.O_TRUNC
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    descriptor = os.open(path, flags)
    with os.fdopen(descriptor, "wb") as stream:
        _ = stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def create_database_recovery(
    database_path: Path,
    recovery_path: Path,
    rotation_id: UUID,
    database_id: UUID,
) -> None:
    snapshot = snapshot_bytes(database_path)
    _ = _write_database_recovery(snapshot, recovery_path, rotation_id, database_id)


def _write_database_recovery(
    snapshot: bytearray,
    recovery_path: Path,
    rotation_id: UUID,
    database_id: UUID,
    *,
    precreated: bool = False,
) -> str:
    try:
        envelope = DatabaseRecoveryEnvelope(
            rotation_id=rotation_id,
            database_id=database_id,
            snapshot_size=len(snapshot),
            snapshot_sha256=hashlib.sha256(snapshot).hexdigest(),
            snapshot_base64=base64.b64encode(snapshot).decode("ascii"),
        )
        plaintext = bytearray(envelope.model_dump_json().encode("utf-8"))
        try:
            protected = bytearray(
                protect_for_current_user(
                    bytes(plaintext),
                    DpapiPurpose.DATABASE_RECOVERY,
                )
            )
            try:
                if precreated:
                    _write_precreated_durable(recovery_path, protected)
                else:
                    _write_new_durable(recovery_path, protected)
                return hashlib.sha256(protected).hexdigest()
            finally:
                protected[:] = b"\0" * len(protected)
        finally:
            plaintext[:] = b"\0" * len(plaintext)
    finally:
        snapshot[:] = b"\0" * len(snapshot)


def create_database_recovery_from_connection(
    source: sqlite3.Connection,
    recovery_path: Path,
    rotation_id: UUID,
    database_id: UUID,
) -> str:
    snapshot = snapshot_connection(source)
    return _write_database_recovery(
        snapshot,
        recovery_path,
        rotation_id,
        database_id,
        precreated=True,
    )


def load_database_recovery(
    recovery_path: Path,
    rotation_id: UUID,
    database_id: UUID,
) -> bytearray:
    plaintext = bytearray(
        unprotect_for_current_user(
            recovery_path.read_bytes(),
            DpapiPurpose.DATABASE_RECOVERY,
        )
    )
    try:
        try:
            envelope = DatabaseRecoveryEnvelope.model_validate_json(plaintext)
            snapshot = bytearray(base64.b64decode(envelope.snapshot_base64, validate=True))
        except (ValidationError, binascii.Error) as error:
            raise SqliteRecoveryError(RecoveryErrorCode.ARTIFACT_INVALID) from error
    finally:
        plaintext[:] = b"\0" * len(plaintext)
    binding_matches = envelope.rotation_id == rotation_id and envelope.database_id == database_id
    digest_matches = (
        len(snapshot) == envelope.snapshot_size
        and hashlib.sha256(snapshot).hexdigest() == envelope.snapshot_sha256
    )
    if not binding_matches:
        snapshot[:] = b"\0" * len(snapshot)
        raise SqliteRecoveryError(RecoveryErrorCode.BINDING_MISMATCH)
    if not digest_matches:
        snapshot[:] = b"\0" * len(snapshot)
        raise SqliteRecoveryError(RecoveryErrorCode.ARTIFACT_INVALID)
    with sqlite3.connect(":memory:") as recovered:
        recovered.deserialize(snapshot)
        if recovered.execute("PRAGMA integrity_check").fetchone() != ("ok",):
            snapshot[:] = b"\0" * len(snapshot)
            raise SqliteRecoveryError(RecoveryErrorCode.INTEGRITY_FAILURE)
    return snapshot


def _assert_snapshot_precedes_rotation(snapshot: bytearray, rotation_id: UUID) -> None:
    with sqlite3.connect(":memory:") as recovered:
        recovered.deserialize(snapshot)
        if (
            recovered.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'credential_rotation_ledger'"
            ).fetchone()
            is None
        ):
            return
        if (
            recovered.execute(
                "SELECT 1 FROM credential_rotation_ledger WHERE rotation_id = ? LIMIT 1",
                (str(rotation_id),),
            ).fetchone()
            is not None
        ):
            raise SqliteRecoveryError(RecoveryErrorCode.RESTORE_STATE_MISMATCH)


def _assert_recovery_digest(recovery_path: Path, expected_sha256: str) -> None:
    actual = hashlib.sha256(recovery_path.read_bytes()).hexdigest()
    if not hmac.compare_digest(actual, expected_sha256):
        raise SqliteRecoveryError(RecoveryErrorCode.ARTIFACT_INVALID)


def confirm_connection_matches_recovery(
    source: sqlite3.Connection,
    recovery_path: Path,
    rotation_id: UUID,
    database_id: UUID,
    expected_sha256: str,
) -> None:
    _assert_recovery_digest(recovery_path, expected_sha256)
    expected = load_database_recovery(recovery_path, rotation_id, database_id)
    actual = snapshot_connection(source)
    try:
        _assert_snapshot_precedes_rotation(expected, rotation_id)
        if len(expected) != len(actual) or not hmac.compare_digest(
            hashlib.sha256(expected).digest(),
            hashlib.sha256(actual).digest(),
        ):
            raise SqliteRecoveryError(RecoveryErrorCode.RESTORE_STATE_MISMATCH)
    finally:
        expected[:] = b"\0" * len(expected)
        actual[:] = b"\0" * len(actual)


def validate_pre_rotation_recovery(
    recovery_path: Path,
    rotation_id: UUID,
    database_id: UUID,
    expected_sha256: str,
) -> None:
    _assert_recovery_digest(recovery_path, expected_sha256)
    snapshot = load_database_recovery(recovery_path, rotation_id, database_id)
    try:
        _assert_snapshot_precedes_rotation(snapshot, rotation_id)
    finally:
        snapshot[:] = b"\0" * len(snapshot)


def confirm_database_matches_recovery(
    database_path: Path,
    recovery_path: Path,
    rotation_id: UUID,
    database_id: UUID,
) -> None:
    sidecars = (
        database_path.with_name(database_path.name + "-wal"),
        database_path.with_name(database_path.name + "-shm"),
    )
    if any(path.exists() for path in sidecars):
        raise SqliteRecoveryError(RecoveryErrorCode.RESTORE_SIDECAR_PRESENT)
    expected = load_database_recovery(recovery_path, rotation_id, database_id)
    actual = snapshot_bytes(database_path)
    try:
        _assert_snapshot_precedes_rotation(expected, rotation_id)
        if (
            len(expected) != len(actual)
            or not hmac.compare_digest(
                hashlib.sha256(expected).digest(),
                hashlib.sha256(actual).digest(),
            )
        ):
            raise SqliteRecoveryError(RecoveryErrorCode.RESTORE_STATE_MISMATCH)
    finally:
        expected[:] = b"\0" * len(expected)
        actual[:] = b"\0" * len(actual)
