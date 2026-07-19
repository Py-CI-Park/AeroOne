"""G003 L2: aero_work_task_category_files.file_id 단독 인덱스 마이그레이션(0030) 검증.

0029 테스트 방식(단일 스텝 임시 sqlite)을 그대로 따른다 — 0029 로 두 테이블을 만든 뒤 0030 을
단독으로 적용해 인덱스가 생기는지, downgrade 로 가역인지를 확인한다.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Protocol, TypeGuard

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


class _MigrationModule(Protocol):
    revision: str
    down_revision: str
    op: Operations

    def upgrade(self) -> None: ...
    def downgrade(self) -> None: ...


def _is_migration_module(module: ModuleType) -> TypeGuard[_MigrationModule]:
    return all(hasattr(module, attribute) for attribute in ('revision', 'down_revision', 'op', 'upgrade', 'downgrade'))


def _load(filename: str) -> _MigrationModule:
    path = Path(__file__).resolve().parents[2] / 'alembic' / 'versions' / filename
    spec = importlib.util.spec_from_file_location(filename, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert _is_migration_module(module)
    return module


def test_0030_migration_is_linear_after_0029() -> None:
    module = _load('20260719_0030_aero_work_task_category_file_index.py')
    assert (module.down_revision, module.revision) == ('20260719_0029', '20260719_0030')


def test_0030_upgrade_creates_file_id_index_and_downgrade_removes_it(tmp_path: Path) -> None:
    # Given: a 0029-shaped database (분류/매핑 두 테이블만).
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'migration.db'}")
    with engine.begin() as connection:
        module_0029 = _load('20260719_0029_aero_work_task_taxonomy.py')
        module_0029.op = Operations(MigrationContext.configure(connection))
        module_0029.upgrade()

        # When: 0030 이 단독으로 적용된다.
        module_0030 = _load('20260719_0030_aero_work_task_category_file_index.py')
        module_0030.op = Operations(MigrationContext.configure(connection))
        module_0030.upgrade()

        # Then: file_id 단독 인덱스가 생긴다.
        index_names = {
            row[1]
            for row in connection.execute(
                sa.text("PRAGMA index_list('aero_work_task_category_files')")
            ).all()
        }
        assert 'ix_aero_work_task_category_files_file_id' in index_names

        # When: downgrade 하면 인덱스만 사라지고 테이블은 남는다(가역).
        module_0030.downgrade()
        index_names_after = {
            row[1]
            for row in connection.execute(
                sa.text("PRAGMA index_list('aero_work_task_category_files')")
            ).all()
        }
        assert 'ix_aero_work_task_category_files_file_id' not in index_names_after
        assert connection.scalar(sa.text('SELECT COUNT(*) FROM aero_work_task_category_files')) == 0
