"""docstring 에 명시된 0 / 1 / 2 / 3 종료 코드 분기가 회귀 없이 유지되는지 검증."""
from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest


REPO_BACKEND = Path(__file__).resolve().parents[2]
SCRIPT = REPO_BACKEND / "scripts" / "ensure_db_state.py"


def _run(*args: str) -> int:
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True).returncode


def test_missing_arg_returns_1() -> None:
    assert _run() == 1


def test_missing_file_returns_2(tmp_path: Path) -> None:
    p = tmp_path / "nope.db"
    assert _run(str(p)) == 2


def test_empty_db_returns_2(tmp_path: Path) -> None:
    p = tmp_path / "empty.db"
    sqlite3.connect(p).close()
    assert _run(str(p)) == 2


def test_tables_without_alembic_metadata_returns_3(tmp_path: Path) -> None:
    p = tmp_path / "tabs.db"
    conn = sqlite3.connect(p)
    try:
        conn.execute("CREATE TABLE users (id INTEGER)")
        conn.execute("CREATE TABLE newsletters (id INTEGER)")
        conn.commit()
    finally:
        conn.close()
    assert _run(str(p)) == 3


def test_alembic_version_filled_returns_0(tmp_path: Path) -> None:
    p = tmp_path / "normal.db"
    conn = sqlite3.connect(p)
    try:
        conn.execute("CREATE TABLE users (id INTEGER)")
        conn.execute("CREATE TABLE alembic_version (version_num TEXT)")
        conn.execute("INSERT INTO alembic_version VALUES ('abc123')")
        conn.commit()
    finally:
        conn.close()
    assert _run(str(p)) == 0


def test_alembic_version_empty_row_returns_3(tmp_path: Path) -> None:
    """alembic_version 테이블은 있으나 row 가 비어 있는 손상 케이스도 stamp head 분기로 처리."""
    p = tmp_path / "alembic-empty.db"
    conn = sqlite3.connect(p)
    try:
        conn.execute("CREATE TABLE users (id INTEGER)")
        conn.execute("CREATE TABLE alembic_version (version_num TEXT)")
        conn.commit()
    finally:
        conn.close()
    assert _run(str(p)) == 3


def test_parent_directory_is_created(tmp_path: Path) -> None:
    nested = tmp_path / "a" / "b" / "c.db"
    assert _run(str(nested)) == 2
    assert nested.parent.is_dir()
