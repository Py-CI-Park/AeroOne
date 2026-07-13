from __future__ import annotations

from pathlib import Path
from typing import Annotated, ClassVar, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from app.operations.credential_bundle import (
    BundlePreparationRequest,
    inspect_credential_scope,
    load_credential_bundle,
    prepare_credential_bundle,
)
from app.operations.credential_rotation_artifacts import (
    RotationJournal,
    RotationJournalPayload,
    RotationPhase,
    advance_rotation_journal,
    seal_rotation_journal,
)
from app.operations.credential_rotation import (
    RotationRequest,
    rotate_all_credentials,
    verify_rotation_state,
)
from app.operations.sqlite_recovery import (
    confirm_database_matches_recovery,
    create_database_recovery,
)


class _StrictModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, strict=True, extra="forbid")


class PrepareCommand(_StrictModel):
    action: Literal["prepare"]
    database_url: str = Field(repr=False, pattern=r"^sqlite:///")
    admin_username: str
    bundle_path: Path


class InspectCommand(_StrictModel):
    action: Literal["inspect"]
    database_url: str = Field(repr=False, pattern=r"^sqlite:///")
    admin_username: str


class CommitCommand(_StrictModel):
    action: Literal["commit"]
    database_url: str = Field(repr=False, pattern=r"^sqlite:///")
    bundle_path: Path
    fail_before_commit: bool = False


class VerifyCommand(_StrictModel):
    action: Literal["verify"]
    database_url: str = Field(repr=False, pattern=r"^sqlite:///")
    bundle_path: Path


class BackupCommand(_StrictModel):
    action: Literal["backup"]
    database_path: Path
    recovery_path: Path
    rotation_id: UUID
    database_id: UUID


class ConfirmRestoreCommand(_StrictModel):
    action: Literal["confirm_restore"]
    database_path: Path
    recovery_path: Path
    rotation_id: UUID
    database_id: UUID


class SealJournalCommand(_StrictModel):
    action: Literal["journal_seal"]
    journal: RotationJournalPayload


class AdvanceJournalCommand(_StrictModel):
    action: Literal["journal_advance"]
    journal: RotationJournal
    phase: RotationPhase


class ValidateJournalCommand(_StrictModel):
    action: Literal["journal_validate"]
    journal: RotationJournal


type RotationCommand = Annotated[
    InspectCommand
    | PrepareCommand
    | CommitCommand
    | VerifyCommand
    | BackupCommand
    | ConfirmRestoreCommand
    | SealJournalCommand
    | AdvanceJournalCommand
    | ValidateJournalCommand,
    Field(discriminator="action"),
]
COMMAND_ADAPTER: TypeAdapter[RotationCommand] = TypeAdapter(RotationCommand)


class CommandSuccess(_StrictModel):
    status: Literal["ok"] = "ok"
    user_count_before: int
    user_count_after: int
    password_count_changed: int
    session_count_before: int
    session_count_after: int


class CommandError(_StrictModel):
    status: Literal["error"] = "error"
    code: str


class JournalCommandSuccess(_StrictModel):
    status: Literal["ok"] = "ok"
    journal: RotationJournal


def run_command(command: RotationCommand) -> CommandSuccess | JournalCommandSuccess:
    match command:
        case InspectCommand(database_url=database_url, admin_username=admin_username):
            user_count = inspect_credential_scope(database_url, admin_username)
            return CommandSuccess(
                user_count_before=user_count,
                user_count_after=user_count,
                password_count_changed=0,
                session_count_before=0,
                session_count_after=0,
            )
        case PrepareCommand(
            database_url=database_url, admin_username=admin_username, bundle_path=bundle_path
        ):
            prepared = prepare_credential_bundle(
                BundlePreparationRequest(
                    database_url=database_url,
                    admin_username=admin_username,
                    bundle_path=bundle_path,
                )
            )
            return CommandSuccess(
                user_count_before=prepared.user_count,
                user_count_after=prepared.user_count,
                password_count_changed=0,
                session_count_before=0,
                session_count_after=0,
            )
        case CommitCommand(
            database_url=database_url,
            bundle_path=bundle_path,
            fail_before_commit=fail_before_commit,
        ):
            result = rotate_all_credentials(
                RotationRequest(
                    database_url=database_url,
                    bundle=load_credential_bundle(bundle_path),
                    fail_before_commit=fail_before_commit,
                )
            )
            return CommandSuccess(
                user_count_before=result.user_count_before,
                user_count_after=result.user_count_after,
                password_count_changed=result.password_count_changed,
                session_count_before=result.session_count_before,
                session_count_after=result.session_count_after,
            )
        case VerifyCommand(database_url=database_url, bundle_path=bundle_path):
            result = verify_rotation_state(
                RotationRequest(
                    database_url=database_url,
                    bundle=load_credential_bundle(bundle_path),
                )
            )
            return CommandSuccess(
                user_count_before=result.user_count,
                user_count_after=result.user_count,
                password_count_changed=result.password_count_verified,
                session_count_before=result.session_count,
                session_count_after=result.session_count,
            )
        case BackupCommand(
            database_path=database_path,
            recovery_path=recovery_path,
            rotation_id=rotation_id,
            database_id=database_id,
        ):
            create_database_recovery(
                database_path,
                recovery_path,
                rotation_id,
                database_id,
            )
            return CommandSuccess(
                user_count_before=0,
                user_count_after=0,
                password_count_changed=0,
                session_count_before=0,
                session_count_after=0,
            )
        case ConfirmRestoreCommand(
            database_path=database_path,
            recovery_path=recovery_path,
            rotation_id=rotation_id,
            database_id=database_id,
        ):
            confirm_database_matches_recovery(
                database_path,
                recovery_path,
                rotation_id,
                database_id,
            )
            return CommandSuccess(
                user_count_before=0,
                user_count_after=0,
                password_count_changed=0,
                session_count_before=0,
                session_count_after=0,
            )
        case SealJournalCommand(journal=journal):
            return JournalCommandSuccess(journal=seal_rotation_journal(journal))
        case AdvanceJournalCommand(journal=journal, phase=phase):
            return JournalCommandSuccess(journal=advance_rotation_journal(journal, phase))
        case ValidateJournalCommand(journal=journal):
            return JournalCommandSuccess(journal=journal)
