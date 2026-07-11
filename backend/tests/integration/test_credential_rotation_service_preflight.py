from __future__ import annotations

from pathlib import Path
import subprocess
import sys

from tests.rotation_harness import create_synthetic_workspace, invoke_rotation


def test_actual_aeroone_listener_blocks_before_rotation_mutation(tmp_path: Path) -> None:
    # Given: a synthetic backend/frontend process owns both configured listener ports.
    listener_program = "\n".join(
        (
            "import socket",
            "import sys",
            "listeners = []",
            "for _ in range(2):",
            "    listener = socket.socket()",
            "    listener.bind(('127.0.0.1', 0))",
            "    listener.listen()",
            "    listeners.append(listener)",
            "print(*(item.getsockname()[1] for item in listeners), flush=True)",
            "sys.stdin.buffer.read(1)",
        )
    )
    listener = subprocess.Popen(
        [sys.executable, "-c", listener_program],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert listener.stdout is not None
    backend_port, frontend_port = (int(value) for value in listener.stdout.readline().split())
    workspace = create_synthetic_workspace(tmp_path)
    for env_path in (workspace.root / ".env", workspace.root / "backend" / ".env"):
        with env_path.open("a", encoding="utf-8") as stream:
            stream.write(f"BACKEND_PORT={backend_port}\nFRONTEND_PORT={frontend_port}\n")
    root_before = (workspace.root / ".env").read_bytes()
    backend_before = (workspace.root / "backend" / ".env").read_bytes()
    database_path = workspace.root / "backend" / "data" / "aeroone.db"
    database_before = database_path.read_bytes()

    # When: a live rotation reaches stopped-service preflight before creating secure output.
    try:
        completed = invoke_rotation(workspace)
    finally:
        assert listener.stdin is not None
        listener.stdin.write("x")
        listener.stdin.flush()
        listener.communicate(timeout=10)

    # Then: the listener is rejected before secure output, database, or env mutation.
    assert completed.returncode != 0
    assert "aeroone-listener-running" in completed.stderr
    assert not (workspace.root / ".rotation-secure").exists()
    assert (workspace.root / ".env").read_bytes() == root_before
    assert (workspace.root / "backend" / ".env").read_bytes() == backend_before
    assert database_path.read_bytes() == database_before
    assert listener.returncode == 0
