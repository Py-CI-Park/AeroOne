from pathlib import Path

from pydantic import ValidationError
import pytest

from app.commands.rotate_credentials import CommitCommand, InspectCommand


def test_command_models_reject_unexpected_fields() -> None:
    # Given: an inspect command carrying an undeclared provider surface.
    payload = {
        "action": "inspect",
        "database_url": "sqlite:///synthetic.db",
        "admin_username": "admin",
        "provider": "unexpected",
    }

    # When: the command boundary parses the payload.
    with pytest.raises(ValidationError) as captured:
        InspectCommand.model_validate(payload)

    # Then: no undeclared field reaches command execution.
    assert captured.value.errors(include_input=False)[0]["type"] == "extra_forbidden"


def test_command_models_reject_coerced_failpoint_values() -> None:
    # Given: a commit command whose boolean arrived as a string.
    payload = {
        "action": "commit",
        "database_url": "sqlite:///synthetic.db",
        "bundle_path": Path("synthetic.dpapi"),
        "fail_before_commit": "false",
    }

    # When: the strict command boundary parses the payload.
    with pytest.raises(ValidationError) as captured:
        CommitCommand.model_validate(payload)

    # Then: string coercion cannot activate or disable a test failpoint.
    assert captured.value.errors(include_input=False)[0]["type"] == "bool_type"
