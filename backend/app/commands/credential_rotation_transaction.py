from __future__ import annotations

from pathlib import Path
import sqlite3
import sys
from typing import Annotated, ClassVar, Literal, assert_never
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.commands.credential_rotation_commands import CommandError, CommandSuccess
from app.operations.credential_bundle import load_credential_bundle
from app.operations.credential_rotation import CredentialRotationError, RotationRequest
from app.operations.credential_rotation_ledger import (
    find_existing_rotation_result,
    rotate_credentials_in_session,
    validate_rotation_transaction,
)
from app.operations.sqlite_recovery import (
    confirm_connection_matches_recovery,
    create_database_recovery_from_connection,
    validate_pre_rotation_recovery,
)
from app.operations.sqlite_recovery_snapshot import (
    RecoveryErrorCode,
    SqliteRecoveryError,
)
from app.operations.windows_dpapi import DpapiError


class _StrictModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, strict=True, extra="forbid")


class BeginTransactionCommand(_StrictModel):
    action: Literal["begin"]
    database_url: str = Field(repr=False, pattern=r"^sqlite:///")
    bundle_path: Path
    recovery_path: Path
    recovery_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    reuse_recovery: bool = False
    fail_before_commit: bool = False


class CommitDecision(_StrictModel):
    action: Literal["commit"]


class BeginRestoreGuardCommand(_StrictModel):
    action: Literal["begin_restore_guard"]
    database_path: Path
    recovery_path: Path
    rotation_id: UUID
    database_id: UUID
    recovery_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class ArchiveCompleteDecision(_StrictModel):
    action: Literal["archive_complete"]


class RecoveryReady(_StrictModel):
    status: Literal["ready"] = "ready"
    recovery_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    user_count_before: int = Field(gt=0)
    session_count_before: int = Field(ge=0)


class AlreadyCommitted(_StrictModel):
    status: Literal["already_committed"] = "already_committed"
    user_count_before: int = Field(gt=0)
    user_count_after: int = Field(gt=0)
    password_count_changed: int = Field(gt=0)
    session_count_before: int = Field(ge=0)
    session_count_after: int = Field(ge=0)


class RestoreGuardReady(_StrictModel):
    status: Literal["restore_guard_ready"] = "restore_guard_ready"


class ArchiveComplete(_StrictModel):
    status: Literal["archive_complete"] = "archive_complete"


type BeginCommand = Annotated[
    BeginTransactionCommand | BeginRestoreGuardCommand,
    Field(discriminator="action"),
]
BEGIN_COMMAND_ADAPTER: TypeAdapter[BeginCommand] = TypeAdapter(BeginCommand)


def _read_frame() -> bytes:
    line = sys.stdin.buffer.readline()
    utf8_bom = b"\xef\xbb\xbf"
    return line[len(utf8_bom) :] if line.startswith(utf8_bom) else line


def _write_line(payload: BaseModel) -> None:
    _ = sys.stdout.write(payload.model_dump_json() + "\n")
    _ = sys.stdout.flush()


def _run_transaction(command: BeginTransactionCommand) -> CommandSuccess | None:
    bundle = load_credential_bundle(command.bundle_path)
    request = RotationRequest(
        database_url=command.database_url,
        bundle=bundle,
        fail_before_commit=command.fail_before_commit,
    )
    engine = create_engine(command.database_url)
    with engine.connect() as connection:
        _ = connection.exec_driver_sql("BEGIN IMMEDIATE")
        driver_connection = connection.connection.driver_connection
        if not isinstance(driver_connection, sqlite3.Connection):
            raise SqliteRecoveryError(RecoveryErrorCode.DRIVER_INVALID)
        with Session(bind=connection) as session:
            existing = find_existing_rotation_result(session, request)
            if existing is not None:
                if not command.reuse_recovery or command.recovery_sha256 is None:
                    raise SqliteRecoveryError(RecoveryErrorCode.ARTIFACT_INVALID)
                validate_pre_rotation_recovery(
                    command.recovery_path,
                    bundle.rotation_id,
                    bundle.database_id,
                    command.recovery_sha256,
                )
                _write_line(
                    AlreadyCommitted(
                        user_count_before=existing.user_count_before,
                        user_count_after=existing.user_count_after,
                        password_count_changed=existing.password_count_changed,
                        session_count_before=existing.session_count_before,
                        session_count_after=existing.session_count_after,
                    )
                )
                return None
            preflight = validate_rotation_transaction(session, request)
            if command.reuse_recovery:
                if command.recovery_sha256 is None:
                    raise SqliteRecoveryError(RecoveryErrorCode.ARTIFACT_INVALID)
                confirm_connection_matches_recovery(
                    driver_connection,
                    command.recovery_path,
                    bundle.rotation_id,
                    bundle.database_id,
                    command.recovery_sha256,
                )
                recovery_sha256 = command.recovery_sha256
            else:
                if command.recovery_sha256 is not None:
                    raise SqliteRecoveryError(RecoveryErrorCode.ARTIFACT_INVALID)
                recovery_sha256 = create_database_recovery_from_connection(
                    driver_connection,
                    command.recovery_path,
                    bundle.rotation_id,
                    bundle.database_id,
                )
            _write_line(
                RecoveryReady(
                    recovery_sha256=recovery_sha256,
                    user_count_before=preflight.user_count,
                    session_count_before=preflight.session_count,
                )
            )
            _ = CommitDecision.model_validate_json(_read_frame())
            result = rotate_credentials_in_session(session, request)
        connection.commit()
    return CommandSuccess(
        user_count_before=result.user_count_before,
        user_count_after=result.user_count_after,
        password_count_changed=result.password_count_changed,
        session_count_before=result.session_count_before,
        session_count_after=result.session_count_after,
    )


def _run_restore_guard(command: BeginRestoreGuardCommand) -> ArchiveComplete:
    with sqlite3.connect(command.database_path, timeout=30) as connection:
        _ = connection.execute("BEGIN IMMEDIATE")
        confirm_connection_matches_recovery(
            connection,
            command.recovery_path,
            command.rotation_id,
            command.database_id,
            command.recovery_sha256,
        )
        _write_line(RestoreGuardReady())
        _ = ArchiveCompleteDecision.model_validate_json(_read_frame())
        connection.rollback()
    return ArchiveComplete()


def main() -> int:
    try:
        command = BEGIN_COMMAND_ADAPTER.validate_json(_read_frame())
        match command:
            case BeginTransactionCommand():
                result = _run_transaction(command)
            case BeginRestoreGuardCommand():
                result = _run_restore_guard(command)
            case unreachable:
                assert_never(unreachable)
    except ValidationError:
        _write_line(CommandError(code="invalid-command-shape"))
        return 2
    except CredentialRotationError as error:
        _write_line(CommandError(code=error.code.value))
        return 3
    except SqliteRecoveryError as error:
        _write_line(CommandError(code=error.code.value))
        return 3
    except DpapiError:
        _write_line(CommandError(code="dpapi-failure"))
        return 4
    except (OSError, SQLAlchemyError, sqlite3.Error):
        _write_line(CommandError(code="storage-failure"))
        return 5
    if result is not None:
        _write_line(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
