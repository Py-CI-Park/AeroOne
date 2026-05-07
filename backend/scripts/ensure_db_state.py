"""SQLite 데이터베이스 상태를 점검해 setup 배치가 올바른 마이그레이션 경로를
선택하도록 종료 코드를 반환한다.

setup.bat / setup_offline.bat 가 본 모듈의 종료 코드를 보고 alembic 명령을
분기한다. 폐쇄망 PC 의 setup 재실행이 기존 데이터를 덮어쓰지 않도록
다음 세 가지 상황을 안전하게 구분하는 것이 목적이다.

종료 코드
---------
0 : DB 파일이 존재하고 alembic_version 행이 비어 있지 않다.
    alembic 메타데이터가 정상이라는 뜻이므로 setup 배치는 alembic upgrade
    head 를 호출해 (이미 head 면 no-op 으로) 마무리한다.

2 : DB 파일이 없거나, 있어도 user / newsletters / categories 어느 핵심
    테이블도 갖고 있지 않다. 새 PC 또는 비어 있는 DB 라는 뜻이므로 setup
    배치는 alembic upgrade head 를 호출해 스키마를 신규 생성한다.

3 : DB 파일에 user / newsletters / categories 같은 핵심 테이블은 이미
    존재하지만 alembic_version 행이 비어 있다. 운영자가 백업/복원이나
    다른 도구로 DB 파일만 옮겨와 metadata 만 누락된 상황이다. setup 배치는
    alembic upgrade head 대신 alembic stamp head 를 호출해 데이터를 보존
    하면서 metadata 만 head 로 표시한다.

1 : 사용 자체가 잘못된 호출 (인자 부족).

사용 예 (배치 안에서)
---------------------
    python scripts/ensure_db_state.py data/aeroone.db
    set "MIGRATION_MODE=%ERRORLEVEL%"
    if "%MIGRATION_MODE%"=="3" (alembic stamp head) else (alembic upgrade head)

본 모듈은 sqlite3 표준 라이브러리만 사용하므로 SQLAlchemy / alembic 이
설치되기 전에도 호출할 수 있다 (pip install --no-index 단계가 끝나기 전
배치 흐름의 가장 앞에 두어도 안전하다).
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path


CORE_TABLES = {'users', 'newsletters', 'categories'}


def main() -> int:
    """sqlite 파일을 열어 위 docstring 의 0 / 2 / 3 종료 코드를 반환한다.

    인자: argv[1] 에 SQLite 데이터베이스 파일 경로를 받는다. 부모 디렉토리
    가 없으면 자동으로 생성한다 (setup 첫 실행 시 backend/data/ 가 없을
    수 있다).

    반환:
        0 : 정상 (alembic_version 행이 채워져 있음).
        1 : 사용 오류 (DB 경로 인자 누락).
        2 : DB 가 비어 있거나 핵심 테이블이 없음 → upgrade head 로 신규 생성.
        3 : 핵심 테이블은 있지만 alembic 메타데이터 부재 → stamp head 로 보존.

    부수 효과는 DB 파일 부모 디렉토리 생성 한 번뿐이며, DB 자체는 읽기만
    한다. 잘못된 메타데이터를 자동으로 고치지 않는 이유는 데이터 손상
    가능성이 있는 결정을 setup 배치 (운영자 동의 흐름) 로 끌어올리기 위함
    이다.
    """

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
    if CORE_TABLES & tables:
        return 3
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
