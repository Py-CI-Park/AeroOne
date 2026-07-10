from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import time

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.modules.auth.models import User
from app.operations.credential_rotation_models import CredentialRotationLedger
from tests.rotation_harness import create_synthetic_workspace


def test_external_writer_cannot_begin_between_recovery_ready_and_commit(
    tmp_path: Path,
) -> None:
    # Given: a real rotation paused after durable recovery and journal preparation.
    workspace = create_synthetic_workspace(tmp_path)
    script = Path(__file__).resolve().parents[3] / "scripts" / "rotate_aeroone_credentials.ps1"
    process_environment = os.environ.copy()
    for key in tuple(process_environment):
        if key.startswith("AEROONE_ROTATION_"):
            del process_environment[key]
    nonce = workspace.root.name.removeprefix("aeroone-rotation-test-")
    process_environment["AEROONE_ROTATION_PYTHON"] = sys.executable
    process_environment["AEROONE_ROTATION_INTERNAL_DB_BARRIER"] = f"{nonce}:hold_after_recovery"
    process_environment["TEMP"] = str(workspace.root.parent)
    process_environment["TMP"] = str(workspace.root.parent)
    rotation = subprocess.Popen(
        [
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            "-TestMode",
            "-TestWorkspaceRoot",
            str(workspace.root),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=process_environment,
    )
    ready = workspace.root / ".aeroone-rotation-db-barrier-ready"
    release = workspace.root / ".aeroone-rotation-db-barrier-release"
    deadline = time.monotonic() + 30
    while not ready.is_file():
        if rotation.poll() is not None:
            stdout, stderr = rotation.communicate()
            raise AssertionError(f"rotation exited before barrier: {stdout=} {stderr=}")
        if time.monotonic() >= deadline:
            rotation.kill()
            stdout, stderr = rotation.communicate()
            raise AssertionError(f"rotation barrier timed out: {stdout=} {stderr=}")
        time.sleep(0.05)

    secure_root = workspace.root / ".rotation-secure"
    recovery = secure_root / "recovery" / "aeroone-db-before-rotation.dpapi"
    journal = secure_root / "rotation-state.json.dpapi"
    assert recovery.stat().st_size > 0
    assert journal.is_file()
    database_path = Path(workspace.database_url.removeprefix("sqlite:///"))
    writer_program = "\n".join(
        (
            "import sqlite3",
            "import sys",
            "connection = sqlite3.connect(sys.argv[1], timeout=0)",
            "connection.execute('BEGIN IMMEDIATE')",
            "connection.execute(\"UPDATE users SET display_name='external-writer' WHERE username='admin'\")",
            "connection.commit()",
            "print('writer-acquired')",
        )
    )

    # When: an independent process attempts a writer transaction while that seam is held.
    try:
        writer = subprocess.run(
            [sys.executable, "-c", writer_program, str(database_path)],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    finally:
        release.write_text("release", encoding="utf-8")
    stdout, stderr = rotation.communicate(timeout=60)

    # Then: the writer is rejected and the same rotation transaction commits exactly once.
    assert writer.returncode != 0, writer.stdout
    assert "writer-acquired" not in writer.stdout
    assert "database is locked" in writer.stderr.lower()
    assert rotation.returncode == 0, stderr
    assert "status=complete" in stdout
    engine = create_engine(workspace.database_url)
    with Session(engine) as session:
        admin = session.scalar(select(User).where(User.username == "admin"))
        ledger_count = session.scalar(select(func.count()).select_from(CredentialRotationLedger))
        assert admin is not None
        assert admin.display_name != "external-writer"
        assert admin.session_version == 3
        assert ledger_count == 1
    engine.dispose()
