from __future__ import annotations

from codecs import BOM_UTF8
from pathlib import Path
import sys
from typing import Annotated, Literal, assert_never

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.operations.credential_bundle import (
    BundlePreparationRequest,
    inspect_credential_scope,
    load_credential_bundle,
    prepare_credential_bundle,
)
from app.operations.credential_rotation import (
    CredentialRotationError,
    RotationRequest,
    rotate_all_credentials,
    verify_rotation_state,
)
from app.operations.windows_dpapi import DpapiError


class PrepareCommand(BaseModel):
    model_config = ConfigDict(frozen=True)

    action: Literal['prepare']
    database_url: str = Field(repr=False, pattern=r'^sqlite:///')
    admin_username: str
    bundle_path: Path


class InspectCommand(BaseModel):
    model_config = ConfigDict(frozen=True)

    action: Literal['inspect']
    database_url: str = Field(repr=False, pattern=r'^sqlite:///')
    admin_username: str


class CommitCommand(BaseModel):
    model_config = ConfigDict(frozen=True)

    action: Literal['commit']
    database_url: str = Field(repr=False, pattern=r'^sqlite:///')
    bundle_path: Path
    fail_before_commit: bool = False


class VerifyCommand(BaseModel):
    model_config = ConfigDict(frozen=True)

    action: Literal['verify']
    database_url: str = Field(repr=False, pattern=r'^sqlite:///')
    bundle_path: Path


type RotationCommand = Annotated[
    InspectCommand | PrepareCommand | CommitCommand | VerifyCommand,
    Field(discriminator='action'),
]
_COMMAND_ADAPTER = TypeAdapter(RotationCommand)


class CommandSuccess(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: Literal['ok'] = 'ok'
    user_count_before: int
    user_count_after: int
    password_count_changed: int
    session_count_before: int
    session_count_after: int


class CommandError(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: Literal['error'] = 'error'
    code: str


def _run_command(command: RotationCommand) -> CommandSuccess:
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
        case PrepareCommand(database_url=database_url, admin_username=admin_username, bundle_path=bundle_path):
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
        case unreachable:
            assert_never(unreachable)


def _validation_error_code(error: ValidationError) -> str:
    errors = error.errors(include_input=False)
    if not errors:
        return 'invalid-input'
    first = errors[0]
    location = {str(part) for part in first['loc']}
    if first['type'] == 'json_invalid':
        return 'invalid-json'
    if 'database_url' in location:
        return 'invalid-database-url'
    if 'action' in location:
        return 'invalid-action'
    return 'invalid-command-shape'


def main() -> int:
    try:
        raw_command = sys.stdin.buffer.read()
        if raw_command.startswith(BOM_UTF8):
            raw_command = raw_command[len(BOM_UTF8):]
        command = _COMMAND_ADAPTER.validate_json(raw_command)
        result = _run_command(command)
    except ValidationError as error:
        print(CommandError(code=_validation_error_code(error)).model_dump_json())
        return 2
    except CredentialRotationError as error:
        print(CommandError(code=error.code.value).model_dump_json())
        return 3
    except DpapiError:
        print(CommandError(code='dpapi-failure').model_dump_json())
        return 4
    except (OSError, SQLAlchemyError):
        print(CommandError(code='storage-failure').model_dump_json())
        return 5
    print(result.model_dump_json())
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
