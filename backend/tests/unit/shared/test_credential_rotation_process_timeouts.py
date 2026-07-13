from __future__ import annotations

import ast
from pathlib import Path
import re


def _subprocess_run_calls(path: Path) -> tuple[ast.Call, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return tuple(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "subprocess"
        and node.func.attr == "run"
    )


def _integer_assignments(path: Path) -> dict[str, int]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    assignments: dict[str, int] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if isinstance(target, ast.Name) and isinstance(node.value, ast.Constant):
            if isinstance(node.value.value, int):
                assignments[target.id] = node.value.value
    return assignments


def test_rotation_python_test_children_have_positive_bounded_timeouts() -> None:
    # Given: the shared rotation harness and viewer subprocess adapters.
    backend = Path(__file__).resolve().parents[3]
    paths = (backend / "tests" / "rotation_harness.py", backend / "tests" / "integration" / "test_credential_rotation_viewer.py")

    # When: every subprocess invocation and timeout constant is inspected.
    calls = tuple(call for path in paths for call in _subprocess_run_calls(path))
    assignments = {name: value for path in paths for name, value in _integer_assignments(path).items()}

    # Then: no child is unbounded and every configured duration is positive.
    assert calls
    assert all(any(keyword.arg == "timeout" for keyword in call.keywords) for call in calls)
    timeout_values = (value for name, value in assignments.items() if name.endswith("TIMEOUT_SECONDS"))
    assert all(value > 0 for value in timeout_values)


def test_rotation_python_command_bounds_normal_and_post_kill_waits() -> None:
    # Given: the PowerShell adapter that owns the credential-transaction child.
    root = Path(__file__).resolve().parents[4]
    source = (
        root / "scripts" / "credential_rotation" / "Rotation.PythonCommand.psm1"
    ).read_text(encoding="utf-8")

    # When: command and termination wait contracts are enumerated.
    waits = tuple(match.group(1) for match in re.finditer(r"WaitForExit\(([^)]*)\)", source))

    # Then: both waits are bounded and no parameterless fallback can hang.
    assert "PythonCommandTimeoutMilliseconds = 60000" in source
    assert "PythonTerminationTimeoutMilliseconds = 5000" in source
    assert waits
    assert all(wait.strip() for wait in waits)
    assert "$Process.Kill()" in source
    assert "WaitForExit()" not in source
