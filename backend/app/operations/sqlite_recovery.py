from __future__ import annotations

import base64
import binascii
from enum import StrEnum, unique
import hashlib
import os
from pathlib import Path
import sqlite3
from typing import ClassVar, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.operations.windows_dpapi import (
    DpapiPurpose,
    protect_for_current_user,
    unprotect_for_current_user,
)


@unique
class RecoveryErrorCode(StrEnum):
    INTEGRITY_FAILURE = "recovery-integrity-failure"
    ARTIFACT_INVALID = "recovery-artifact-invalid"
    BINDING_MISMATCH = "recovery-binding-mismatch"
    RESTORE_STATE_MISMATCH = "recovery-restore-state-mismatch"
    RESTORE_SIDECAR_PRESENT = "recovery-restore-sidecar-present"
    DRIVER_INVALID = "recovery-driver-invalid"


class SqliteRecoveryError(Exception):
    code: RecoveryErrorCode

    def __init__(self, code: RecoveryErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


class DatabaseRecoveryEnvelope(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, strict=True, extra="forbid")

    schema_version: Literal[1] = 1
    artifact_type: Literal["database-recovery"] = "database-recovery"
    rotation_id: UUID
    database_id: UUID
    snapshot_size: int = Field(ge=1)
    snapshot_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    snapshot_base64: str = Field(repr=False)


def _snapshot_connection(source: sqlite3.Connection) -> bytearray:
    serialized = bytearray(source.serialize())
    try:
        serialized[18] = 1
        serialized[19] = 1
        with sqlite3.connect(":memory:") as destination:
            destination.deserialize(serialized)
            destination.execute("PRAGMA journal_mode=DELETE").close()
            destination.execute("PRAGMA schema_version=0").close()
            destination.execute("VACUUM").close()
            snapshot = bytearray(destination.serialize())
        verified_snapshot = False
        try:
            canonical_counter = (1).to_bytes(4, byteorder="big")
            snapshot[24:28] = canonical_counter
            snapshot[92:96] = canonical_counter
            with sqlite3.connect(":memory:") as verified:
                verified.deserialize(snapshot)
                if verified.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                    raise SqliteRecoveryError(RecoveryErrorCode.INTEGRITY_FAILURE)
            verified_snapshot = True
            return snapshot
        finally:
            if not verified_snapshot:
                snapshot[:] = b"\0" * len(snapshot)
    finally:
        serialized[:] = b"\0" * len(serialized)


def _snapshot_bytes(database_path: Path) -> bytearray:
    source_uri = f"{database_path.resolve().as_uri()}?mode=ro"
    with sqlite3.connect(source_uri, uri=True, timeout=5) as source:
        return _snapshot_connection(source)


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
    snapshot = _snapshot_bytes(database_path)
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
    snapshot = _snapshot_connection(source)
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
    actual = _snapshot_bytes(database_path)
    try:
        if (
            len(expected) != len(actual)
            or not hashlib.sha256(expected).digest() == hashlib.sha256(actual).digest()
        ):
            raise SqliteRecoveryError(RecoveryErrorCode.RESTORE_STATE_MISMATCH)
    finally:
        expected[:] = b"\0" * len(expected)
        actual[:] = b"\0" * len(actual)
