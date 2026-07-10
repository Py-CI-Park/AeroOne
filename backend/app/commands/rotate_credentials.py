from __future__ import annotations

from codecs import BOM_UTF8
import sys

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.commands.credential_rotation_commands import (
    COMMAND_ADAPTER,
    CommandError,
    CommitCommand,
    InspectCommand,
    run_command,
)
from app.operations.credential_rotation import CredentialRotationError
from app.operations.sqlite_recovery import SqliteRecoveryError
from app.operations.windows_dpapi import DpapiError

__all__ = ["CommitCommand", "InspectCommand", "main"]


def _validation_error_code(error: ValidationError) -> str:
    errors = error.errors(include_input=False)
    if not errors:
        return "invalid-input"
    first = errors[0]
    location = {str(part) for part in first["loc"]}
    if first["type"] == "json_invalid":
        return "invalid-json"
    if "database_url" in location:
        return "invalid-database-url"
    if "action" in location:
        return "invalid-action"
    return "invalid-command-shape"


def main() -> int:
    try:
        raw_command = sys.stdin.buffer.read()
        if raw_command.startswith(BOM_UTF8):
            raw_command = raw_command[len(BOM_UTF8) :]
        command = COMMAND_ADAPTER.validate_json(raw_command)
        result = run_command(command)
    except ValidationError as error:
        print(CommandError(code=_validation_error_code(error)).model_dump_json())
        return 2
    except CredentialRotationError as error:
        print(CommandError(code=error.code.value).model_dump_json())
        return 3
    except SqliteRecoveryError as error:
        print(CommandError(code=error.code.value).model_dump_json())
        return 3
    except DpapiError:
        print(CommandError(code="dpapi-failure").model_dump_json())
        return 4
    except (OSError, SQLAlchemyError):
        print(CommandError(code="storage-failure").model_dump_json())
        return 5
    print(result.model_dump_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
