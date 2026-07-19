"""G004: 키워드 검색 SQLite FTS5(trigram/unicode61 폴백) 승격 단위 검증.

마이그레이션 0031(가상 테이블 생성 + 토크나이저 감지)과 ``KnowledgeService`` 의 FTS 동기화
(청크 upsert/삭제), 한국어 부분일치, LIKE 폴백 경로를 확인한다. 임베딩은 keyword_search 와
무관하므로 항상 널 벡터를 돌려주는 결정적 임베더를 쓴다.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Protocol, TypeGuard

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.orm import Session

from app.db.base import Base
from app.modules.aero_work import knowledge_service as ks
from app.modules.aero_work import models as aero_work_models  # noqa: F401  (register tables)
from app.modules.aero_work.knowledge_service import KnowledgeService

FTS_MIGRATION_FILE = '20260719_0031_aero_work_knowledge_fts.py'


class _MigrationModule(Protocol):
    revision: str
    down_revision: str
    op: Operations

    def upgrade(self) -> None: ...
    def downgrade(self) -> None: ...


def _is_migration_module(module: ModuleType) -> TypeGuard[_MigrationModule]:
    return all(hasattr(module, attribute) for attribute in ('revision', 'down_revision', 'op', 'upgrade', 'downgrade'))


def _load_migration(filename: str) -> _MigrationModule:
    path = Path(__file__).resolve().parents[3] / 'alembic' / 'versions' / filename
    spec = importlib.util.spec_from_file_location(filename, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert _is_migration_module(module)
    return module


class _NullEmbedder:
    """keyword_search 는 임베딩을 쓰지 않으므로, reindex 가 요구하는 형태만 만족시킨다."""

    model = 'null-embed'

    def embed_one(self, text: str) -> list[float]:
        return [0.0]

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] for _ in texts]


# ---- 마이그레이션 0031 ----


def test_0031_migration_is_linear_after_0030() -> None:
    module = _load_migration(FTS_MIGRATION_FILE)
    assert (module.down_revision, module.revision) == ('20260719_0030', '20260719_0031')


def test_0031_upgrade_creates_fts_table_and_downgrade_removes_it(tmp_path: Path) -> None:
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'migration.db'}")
    with engine.begin() as connection:
        module = _load_migration(FTS_MIGRATION_FILE)
        module.op = Operations(MigrationContext.configure(connection))
        module.upgrade()

        row = connection.execute(
            sa.text("SELECT sql FROM sqlite_master WHERE type='table' AND name='aero_work_chunk_fts'")
        ).first()
        assert row is not None, 'FTS5 를 지원하는 sqlite3 빌드라면 가상 테이블이 생성돼야 한다'
        # 이 실행 환경의 sqlite3(3.45.3)는 trigram 토크나이저를 지원하므로 우선 선택되어야
        # 한다(미지원 빌드라면 unicode61 로 폴백 — 런타임 감지는 _pick_tokenizer 참조).
        assert 'trigram' in row[0]

        module.downgrade()
        row_after = connection.execute(
            sa.text("SELECT sql FROM sqlite_master WHERE type='table' AND name='aero_work_chunk_fts'")
        ).first()
        assert row_after is None


# ---- KnowledgeService × FTS 동기화/검색 ----


@pytest.fixture()
def engine_with_fts(tmp_path: Path):
    """지식폴더 3테이블 + 0031 로 생성한 FTS5 가상 테이블을 갖춘 엔진."""

    engine = sa.create_engine(f"sqlite:///{tmp_path / 'fts.db'}")
    Base.metadata.create_all(
        bind=engine,
        tables=[
            Base.metadata.tables['aero_work_knowledge_folders'],
            Base.metadata.tables['aero_work_knowledge_files'],
            Base.metadata.tables['aero_work_knowledge_chunks'],
        ],
    )
    with engine.begin() as connection:
        module = _load_migration(FTS_MIGRATION_FILE)
        module.op = Operations(MigrationContext.configure(connection))
        module.upgrade()
    return engine


@pytest.fixture()
def engine_without_fts(tmp_path: Path):
    """FTS5 가상 테이블이 없는(구형 sqlite3 빌드를 흉내낸) 엔진 — LIKE 폴백 경로 검증용."""

    engine = sa.create_engine(f"sqlite:///{tmp_path / 'no_fts.db'}")
    Base.metadata.create_all(
        bind=engine,
        tables=[
            Base.metadata.tables['aero_work_knowledge_folders'],
            Base.metadata.tables['aero_work_knowledge_files'],
            Base.metadata.tables['aero_work_knowledge_chunks'],
        ],
    )
    return engine


def _seed_folder(tmp_path: Path) -> Path:
    root = tmp_path / 'kb'
    root.mkdir()
    (root / 'budget.md').write_text('예산편성 계획 수립 지침', encoding='utf-8')
    (root / 'travel.md').write_text('여행 경비 정산 규정', encoding='utf-8')
    return root


def test_keyword_search_partial_korean_match_via_fts(engine_with_fts, tmp_path: Path) -> None:
    root = _seed_folder(tmp_path)
    with Session(engine_with_fts) as db:
        service = KnowledgeService(db, _NullEmbedder())
        folder = service.register_folder('kb', str(root))
        db.commit()
        service.reindex(folder.id)
        db.commit()

        assert ks._fts_available(db) is True  # 이 빌드는 FTS5 를 지원 → FTS 경로 사용

        hits = service.keyword_search('예산')  # 2글자 부분일치 → '예산편성' 히트
        assert hits and hits[0]['rel_path'] == 'budget.md'

        assert service.keyword_search('경비')[0]['rel_path'] == 'travel.md'
        assert service.keyword_search('존재하지않는키워드zzz') == []


def test_keyword_search_falls_back_to_like_when_fts_missing(engine_without_fts, tmp_path: Path) -> None:
    root = _seed_folder(tmp_path)
    with Session(engine_without_fts) as db:
        service = KnowledgeService(db, _NullEmbedder())
        folder = service.register_folder('kb', str(root))
        db.commit()
        service.reindex(folder.id)
        db.commit()

        assert ks._fts_available(db) is False  # 가상 테이블이 없으니 폴백 확정

        # LIKE 폴백도 동일하게 부분일치를 지원한다(응답 형태·score 정의 불변).
        hits = service.keyword_search('예산')
        assert hits and hits[0]['rel_path'] == 'budget.md'
        assert hits[0]['score'] == 1.0


def test_fts_sync_removes_entries_on_file_deletion(engine_with_fts, tmp_path: Path) -> None:
    root = tmp_path / 'kb'
    root.mkdir()
    target = root / 'gone.md'
    target.write_text('삭제예정 문서 내용', encoding='utf-8')
    with Session(engine_with_fts) as db:
        service = KnowledgeService(db, _NullEmbedder())
        folder = service.register_folder('kb', str(root))
        db.commit()
        service.reindex(folder.id)
        db.commit()
        assert service.keyword_search('삭제예정')

        target.unlink()
        service.reindex(folder.id)
        db.commit()

        assert service.keyword_search('삭제예정') == []
        count = db.execute(sa.text('SELECT COUNT(*) FROM aero_work_chunk_fts')).scalar_one()
        assert count == 0


def test_fts_sync_removes_entries_on_folder_delete(engine_with_fts, tmp_path: Path) -> None:
    root = tmp_path / 'kb'
    root.mkdir()
    (root / 'a.md').write_text('청소 대상 문서', encoding='utf-8')
    with Session(engine_with_fts) as db:
        service = KnowledgeService(db, _NullEmbedder())
        folder = service.register_folder('kb', str(root))
        db.commit()
        service.reindex(folder.id)
        db.commit()
        assert db.execute(sa.text('SELECT COUNT(*) FROM aero_work_chunk_fts')).scalar_one() > 0

        service.delete_folder(folder.id)
        db.commit()
        assert db.execute(sa.text('SELECT COUNT(*) FROM aero_work_chunk_fts')).scalar_one() == 0


def test_reindex_progress_callback_fires_every_five_files_and_at_end(engine_with_fts, tmp_path: Path) -> None:
    root = tmp_path / 'kb'
    root.mkdir()
    for i in range(7):
        (root / f'doc{i}.md').write_text(f'문서 {i} 내용', encoding='utf-8')

    calls: list[tuple[int, int]] = []
    with Session(engine_with_fts) as db:
        service = KnowledgeService(db, _NullEmbedder())
        folder = service.register_folder('kb', str(root))
        db.commit()
        service.reindex(folder.id, progress_cb=lambda done, total: calls.append((done, total)))
        db.commit()

    assert calls == [(5, 7), (7, 7)]
