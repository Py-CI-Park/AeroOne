from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Protocol, TypeGuard

from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa

from app.db.base import Base
from app.modules.auth.models import User
import app.operations.credential_rotation_models as credential_rotation_models


class _MigrationModule(Protocol):
    revision: str
    down_revision: str
    op: Operations

    def upgrade(self) -> None: ...


def _is_migration_module(module: ModuleType) -> TypeGuard[_MigrationModule]:
    return all(hasattr(module, attribute) for attribute in ('revision', 'down_revision', 'op', 'upgrade'))


def _migration_module() -> _MigrationModule:
    path = (
        Path(__file__).resolve().parents[2]
        / 'alembic'
        / 'versions'
        / '20260710_0009_credential_rotation_ledger.py'
    )
    spec = importlib.util.spec_from_file_location('credential_rotation_0009', path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert _is_migration_module(module)
    return module


def test_credential_rotation_migration_is_linear_after_user_display_name() -> None:
    # Given: the v1.13.0 credential rotation migration module.
    module = _migration_module()

    # When: its lineage identifiers are inspected.
    lineage = (module.down_revision, module.revision)

    # Then: the migration advances the existing 0008 head exactly once.
    assert lineage == ('20260707_0008', '20260710_0009')


def test_0009_upgrade_preserves_users_and_seeds_database_identity(tmp_path: Path) -> None:
    # Given: a 0008-compatible database with one existing user.
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'migration.db'}")
    assert User.__name__ == 'User'
    users_table = Base.metadata.tables['users']
    Base.metadata.create_all(engine, tables=[users_table])
    with engine.begin() as connection:
        _ = connection.execute(
            sa.insert(users_table).values(
                username='admin',
                password_hash='synthetic-hash',
                role='admin',
                is_active=True,
                session_version=0,
            )
        )
        operations = Operations(MigrationContext.configure(connection))
        module = _migration_module()
        module.op = operations

        # When: the credential rotation migration upgrades the database.
        module.upgrade()

        # Then: user data remains and both ledger tables satisfy their seed contract.
        assert connection.scalar(sa.text('SELECT COUNT(*) FROM users')) == 1
        assert connection.scalar(
            sa.text('SELECT COUNT(*) FROM credential_rotation_database_state')
        ) == 1
        assert connection.scalar(sa.text('SELECT COUNT(*) FROM credential_rotation_ledger')) == 0


def test_rotation_models_register_unique_identity_and_material_constraints() -> None:
    # Given: imported rotation ORM metadata.
    assert credential_rotation_models is not None

    # When: the two table definitions are inspected.
    state = Base.metadata.tables['credential_rotation_database_state']
    ledger = Base.metadata.tables['credential_rotation_ledger']

    # Then: database identity and material replay have database-enforced uniqueness.
    assert state.c.database_id.unique is True
    unique_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in ledger.constraints
        if isinstance(constraint, sa.UniqueConstraint)
    }
    assert ('database_id', 'material_fingerprint') in unique_columns
