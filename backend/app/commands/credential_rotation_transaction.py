from __future__ import annotations

from pathlib import Path
import sqlite3
import sys
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.commands.credential_rotation_commands import CommandError, CommandSuccess
from app.operations.credential_bundle import load_credential_bundle
from app.operations.credential_rotation import CredentialRotationError, RotationRequest
from app.operations.credential_rotation_ledger import (
    rotate_credentials_in_session,
    validate_rotation_transaction,
)
from app.operations.sqlite_recovery import (
    RecoveryErrorCode,
    SqliteRecoveryError,
    create_database_recovery_from_connection,
)
from app.operations.windows_dpapi import DpapiError


class _StrictModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, strict=True, extra="forbid")


class BeginTransactionCommand(_StrictModel):
    action: Literal["begin"]
    database_url: str = Field(repr=False, pattern=r"^sqlite:///")
    bundle_path: Path
    recovery_path: Path
    fail_before_commit: bool = False


class CommitDecision(_StrictModel):
    action: Literal["commit"]


class RecoveryReady(_StrictModel):
    status: Literal["ready"] = "ready"
    recovery_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    user_count_before: int = Field(gt=0)
    session_count_before: int = Field(ge=0)


def _read_frame() -> bytes:
    line = sys.stdin.buffer.readline()
    utf8_bom = b"\xef\xbb\xbf"
    return line[len(utf8_bom) :] if line.startswith(utf8_bom) else line


def _write_line(payload: BaseModel) -> None:
    _ = sys.stdout.write(payload.model_dump_json() + "\n")
    _ = sys.stdout.flush()


def _run_transaction(command: BeginTransactionCommand) -> CommandSuccess:
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
            preflight = validate_rotation_transaction(session, request)
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


def main() -> int:
    try:
        command = BeginTransactionCommand.model_validate_json(_read_frame())
        result = _run_transaction(command)
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
    _write_line(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
