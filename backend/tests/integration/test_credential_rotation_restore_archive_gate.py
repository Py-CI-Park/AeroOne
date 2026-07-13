from __future__ import annotations

from pathlib import Path
import sqlite3
import subprocess
import sys

from tests.maintenance_gate_harness import rotation_at_database_barrier, terminate_process
from tests.rotation_harness import create_synthetic_workspace, invoke_rotation


def _external_writer(database_path: Path, display_name: str) -> subprocess.CompletedProcess[str]:
    writer_program = "\n".join(
        (
            "import sqlite3",
            "import sys",
            "connection = sqlite3.connect(sys.argv[1], timeout=0)",
            "connection.execute('BEGIN IMMEDIATE')",
            "connection.execute(\"UPDATE users SET display_name=? WHERE username='admin'\", (sys.argv[2],))",
            "connection.commit()",
            "print('writer-acquired')",
        )
    )
    return subprocess.run(
        [sys.executable, "-c", writer_program, str(database_path), display_name],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_restore_archive_holds_writer_lock_until_archive_acknowledgment(
    tmp_path: Path,
) -> None:
    # Given: a completed rotation whose database has been restored to the bound pre-rotation state.
    workspace = create_synthetic_workspace(tmp_path)
    database_path = Path(workspace.database_url.removeprefix("sqlite:///"))
    restored_database = tmp_path / "restored-pre-rotation.db"
    prepared = invoke_rotation(workspace, ("-Failpoint", "before_db_commit"))
    assert prepared.returncode != 0
    assert "python-test-failpoint" in prepared.stderr
    with (
        sqlite3.connect(database_path) as source,
        sqlite3.connect(restored_database) as destination,
    ):
        source.backup(destination)
    completed = invoke_rotation(workspace)
    assert completed.returncode == 0, completed.stderr
    for suffix in ("-wal", "-shm"):
        database_path.with_name(database_path.name + suffix).unlink(missing_ok=True)
    database_path.write_bytes(restored_database.read_bytes())
    archive, release = rotation_at_database_barrier(
        workspace.root,
        barrier="hold_after_restore_confirmation",
        extra_arguments=(
            "-RestoreConfirmation",
            "ARCHIVE_COMPLETED_ROTATION_AND_START_NEW",
        ),
    )

    # When: an independent writer races after restore confirmation but before archive completion.
    try:
        blocked_writer = _external_writer(database_path, "writer-during-archive")
        release.write_text("release", encoding="utf-8")
        archive_stdout, archive_stderr = archive.communicate(timeout=90)
    finally:
        release.write_text("release", encoding="utf-8")
        terminate_process(archive)
    released_writer = _external_writer(database_path, "writer-after-archive")

    # Then: confirmation and archive are one lock interval, and release restores writability.
    assert blocked_writer.returncode != 0, blocked_writer.stdout
    assert "writer-acquired" not in blocked_writer.stdout
    assert "database is locked" in blocked_writer.stderr.lower()
    assert archive.returncode == 0, archive_stderr
    assert "status=archived" in archive_stdout
    assert released_writer.returncode == 0, released_writer.stderr
    assert released_writer.stdout.strip() == "writer-acquired"
