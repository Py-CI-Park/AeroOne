from __future__ import annotations

from enum import StrEnum, unique
from pathlib import Path
import sqlite3


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


def snapshot_connection(source: sqlite3.Connection) -> bytearray:
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


def snapshot_bytes(database_path: Path) -> bytearray:
    source_uri = f"{database_path.resolve().as_uri()}?mode=ro"
    with sqlite3.connect(source_uri, uri=True, timeout=5) as source:
        return snapshot_connection(source)
