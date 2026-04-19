from __future__ import annotations

import sqlite3
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) < 2:
        return 1
    db_path = Path(sys.argv[1]).resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if not db_path.exists():
        return 2
    conn = sqlite3.connect(db_path)
    try:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        has_alembic_row = False
        if 'alembic_version' in tables:
            rows = list(conn.execute('SELECT version_num FROM alembic_version'))
            has_alembic_row = len(rows) > 0 and bool(rows[0][0])
    finally:
        conn.close()
    if has_alembic_row:
        return 0
    if {'users', 'newsletters', 'categories'} & tables:
        return 3
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
