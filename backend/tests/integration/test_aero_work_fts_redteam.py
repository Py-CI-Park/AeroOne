"""G004: FTS5 키워드 검색 + 비동기 재색인 적대적(red-team) 통합 검증.

``test_aero_work_knowledge_api.py``(정상 왕복)와 ``test_aero_work_async_reindex_api.py``
(비동기 가드 동시성)를 전제로, 실 sqlite3 빌드(FTS5 trigram 지원, ``backend/alembic/versions/
20260719_0031_aero_work_knowledge_fts.py`` 참조)에서만 드러나는 경계 케이스를 겨냥한다:

1. FTS 특수문자 질의(", *, (, ), NEAR, AND, OR, -, %, _, SQL 인젝션 유사 문자열) → 500 없이
   안전한 결과(빈 배열 허용) — 구현이 FTS5 ``MATCH`` 가 아니라 파라미터 바인딩된
   ``content LIKE :t`` 를 쓰므로 원천적으로 FTS 쿼리 문법 인젝션 표면이 없다는 걸 실측 확인.
2. 한국어 2글자/1글자/공백만/이모지 질의 — 전부 200, 공백만은 빈 배열.
3. 색인 중(가드 점유) 폴더 삭제 — M1 이후 DELETE 도 재색인 가드를 확인해 409 로 거절한다
   (재색인 스레드가 같은 세션에서 flush 중인 행을 지워 FK 위반으로 조용히 죽던 경쟁을
   원천 차단). 완료 후 가드가 풀리면 정상적으로 삭제할 수 있다.
4. reindex 중 동일 폴더 재요청 409, 다른 폴더는 202 로 독립적으로 진행.
5. 백그라운드 임베더 실패(EmbeddingUnavailable) 시 폴더가 error 상태 + 사유 기록, 가드는
   해제되어 재요청이 즉시 가능해야 한다.
6. FTS 가상 테이블을 강제 DROP 한 뒤 검색해도 LIKE 폴백으로 계속 응답한다(500 없음).
7. 증분 재색인으로 디스크에서 사라진 파일의 청크는 FTS 잔재 없이 검색에서 사라진다.
8. 익명 401(키워드 검색), CSRF 미첨부 403(재색인 뮤테이션).
"""

from __future__ import annotations

import importlib.util
import threading
import time
from pathlib import Path
from types import ModuleType
from typing import Protocol, TypeGuard

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

import app.modules.aero_work.api as aero_api
from app.modules.aero_work.embedding_client import EmbeddingUnavailable
from app.modules.aero_work.models import KnowledgeChunk, KnowledgeFile, KnowledgeFolder

FTS_TABLE = 'aero_work_chunk_fts'
FTS_MIGRATION_FILE = '20260719_0031_aero_work_knowledge_fts.py'


# ---- 0031 마이그레이션 직접 적용(conftest 의 app 픽스처는 Base.metadata.create_all 만 쓰고
# alembic 을 타지 않으므로, FTS 관련 케이스는 이 파일에서 명시적으로 승격해야 한다) ----


class _MigrationModule(Protocol):
    revision: str
    down_revision: str
    op: Operations

    def upgrade(self) -> None: ...
    def downgrade(self) -> None: ...


def _is_migration_module(module: ModuleType) -> TypeGuard[_MigrationModule]:
    return all(hasattr(module, attribute) for attribute in ('revision', 'down_revision', 'op', 'upgrade', 'downgrade'))


def _load_migration(filename: str) -> _MigrationModule:
    path = Path(__file__).resolve().parents[2] / 'alembic' / 'versions' / filename
    spec = importlib.util.spec_from_file_location(filename, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert _is_migration_module(module)
    return module


def _apply_fts_migration(app) -> None:
    with app.state.db.engine.begin() as connection:
        module = _load_migration(FTS_MIGRATION_FILE)
        module.op = Operations(MigrationContext.configure(connection))
        module.upgrade()


def _drop_fts_table(app) -> None:
    """색인이 끝난 뒤 FTS 테이블을 강제로 지워 폴백 경로를 켠다(운영에서는 sqlite3 빌드
    교체·파일 손상 등으로 벌어질 수 있는 시나리오를 흉내낸다)."""

    with app.state.db.engine.begin() as connection:
        connection.exec_driver_sql(f'DROP TABLE IF EXISTS {FTS_TABLE}')


# ---- 결정적 임베더들 ----


class _FakeEmbedder:
    """route 가 생성하는 OllamaEmbedder 를 대체하는 결정적 임베더 — 벡터 값은 검색 무관."""

    model = 'fake-embed'

    def __init__(self, settings=None) -> None:  # noqa: ANN001 (route 시그니처 호환)
        pass

    def embed_one(self, text: str) -> list[float]:
        return [0.0]

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] for _ in texts]


class _PausingEmbedder:
    """``pause_at`` 번째 ``embed()`` 호출에서 ``resume_event`` 까지 대기하는 결정적 임베더."""

    model = 'fake-embed'

    def __init__(self) -> None:
        self.call_count = 0
        self.pause_at: int | None = None
        self.reached_pause = threading.Event()
        self.resume_event = threading.Event()

    def embed_one(self, text: str) -> list[float]:
        return [0.0]

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.call_count += 1
        if self.pause_at is not None and self.call_count == self.pause_at:
            self.reached_pause.set()
            self.resume_event.wait(timeout=5)
        return [[0.0] for _ in texts]


class _FailingEmbedder:
    """모든 ``embed()`` 호출에서 Ollama 미기동을 흉내내는 ``EmbeddingUnavailable`` 을 던진다."""

    model = 'failing-embed'

    def embed_one(self, text: str) -> list[float]:
        return [0.0]

    def embed(self, texts: list[str]) -> list[list[float]]:
        raise EmbeddingUnavailable('테스트: Ollama 연결 실패를 흉내낸다')


@pytest.fixture()
def fake_embedder(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(aero_api, 'build_embedder', lambda _settings, _db: _FakeEmbedder())


@pytest.fixture(autouse=True)
def _reset_reindex_guard() -> None:
    """폴더별 진행 중 가드(모듈 전역 set)를 테스트마다 초기화해 교차 오염을 막는다."""

    aero_api._REINDEXING_FOLDER_IDS.clear()
    yield
    aero_api._REINDEXING_FOLDER_IDS.clear()


def _wait_until(predicate, *, timeout: float = 5.0, interval: float = 0.05):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        last = predicate()
        if last:
            return last
        time.sleep(interval)
    raise AssertionError(f'조건이 {timeout}초 내에 충족되지 않았다(마지막 값: {last!r})')


def _register_folder(csrf_client, root: Path, name: str = 'kb') -> int:
    created = csrf_client.post(
        '/api/v1/aero-work/knowledge/folders', json={'name': name, 'path': str(root)}
    )
    assert created.status_code == 201, created.text
    return created.json()['id']


# ---- 1. FTS 특수문자 질의 ----


SPECIAL_QUERIES = [
    '"',
    '*',
    '(',
    ')',
    'NEAR',
    'AND',
    'OR',
    '-',
    '%',
    '_',
    '"보안" NEAR(usb) AND *',
    "'; DROP TABLE aero_work_chunk_fts; --",
]


def test_fts_special_character_queries_never_500(csrf_client, fake_embedder, tmp_path: Path, app) -> None:
    _apply_fts_migration(app)
    root = tmp_path / 'kb'
    root.mkdir()
    (root / 'doc.md').write_text('예산편성 계획과 usb 보안 지침', encoding='utf-8')
    folder_id = _register_folder(csrf_client, root)
    reindex = csrf_client.post(f'/api/v1/aero-work/knowledge/folders/{folder_id}/reindex?inline=true')
    assert reindex.status_code == 200, reindex.text

    for query in SPECIAL_QUERIES:
        resp = csrf_client.post('/api/v1/aero-work/knowledge/keyword-search', json={'query': query})
        assert resp.status_code == 200, f'{query!r} -> {resp.status_code}: {resp.text}'
        assert isinstance(resp.json()['hits'], list)

    # SQL 인젝션 유사 질의가 파라미터 바인딩을 우회해 실제 DDL 로 새지 않았는지 확인.
    with app.state.db.session() as session:
        exists = session.execute(
            sa.text("SELECT 1 FROM sqlite_master WHERE type='table' AND name=:name"), {'name': FTS_TABLE}
        ).first()
        assert exists is not None, 'DROP TABLE 인젝션 문자열이 실행됐다면 심각 결함'


# ---- 2. 한국어 2글자/1글자/공백만/이모지 질의 ----


def test_keyword_search_korean_short_and_edge_queries(csrf_client, fake_embedder, tmp_path: Path, app) -> None:
    _apply_fts_migration(app)
    root = tmp_path / 'kb'
    root.mkdir()
    (root / 'doc.md').write_text('예산편성 계획 수립 지침', encoding='utf-8')
    folder_id = _register_folder(csrf_client, root)
    assert csrf_client.post(f'/api/v1/aero-work/knowledge/folders/{folder_id}/reindex?inline=true').status_code == 200

    two_char = csrf_client.post('/api/v1/aero-work/knowledge/keyword-search', json={'query': '예산'})
    assert two_char.status_code == 200, two_char.text
    assert any('예산편성' in hit['content'] for hit in two_char.json()['hits']), 'trigram FTS 는 2글자 부분일치를 잡아야 한다'

    one_char = csrf_client.post('/api/v1/aero-work/knowledge/keyword-search', json={'query': '예'})
    assert one_char.status_code == 200, one_char.text  # 매칭 유무와 무관하게 500 이 없어야 한다

    space_only = csrf_client.post('/api/v1/aero-work/knowledge/keyword-search', json={'query': ' '})
    assert space_only.status_code == 200, space_only.text
    assert space_only.json()['hits'] == []  # split() 이 공백만 걸러내 빈 term 목록 → 빈 결과

    emoji = csrf_client.post('/api/v1/aero-work/knowledge/keyword-search', json={'query': '📎🔥'})
    assert emoji.status_code == 200, emoji.text
    assert emoji.json()['hits'] == []


# ---- 3. 색인 중(가드 점유) 폴더 삭제 ----


def test_delete_folder_during_indexing_is_rejected_then_succeeds_after_completion(
    csrf_client, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, app
) -> None:
    """M1: 색인 중(가드 점유) 폴더는 삭제를 409 로 거절한다 — 재색인 스레드가 flush 중인 행을
    같은 트랜잭션에서 지워버려 FK 위반으로 조용히 죽던 예전 경쟁(레드팀 이전 관측)을
    원천 차단한다. 완료 후 가드가 풀리면 정상적으로 삭제 가능해야 한다.
    """

    embedder = _PausingEmbedder()
    embedder.pause_at = 1  # 임베딩이 시작되기 전(파일 행 flush 이전)에 멈춰 세운다
    monkeypatch.setattr(aero_api, 'build_embedder', lambda _settings, _db: embedder)

    root = tmp_path / 'kb'
    root.mkdir()
    (root / 'doc.md').write_text('삭제 대상 문서 내용', encoding='utf-8')
    folder_id = _register_folder(csrf_client, root)

    reindex = csrf_client.post(f'/api/v1/aero-work/knowledge/folders/{folder_id}/reindex')
    assert reindex.status_code == 202, reindex.text
    assert embedder.reached_pause.wait(timeout=5), '백그라운드 스레드가 첫 embed() 호출까지 도달해야 한다'

    delete_resp = csrf_client.delete(f'/api/v1/aero-work/knowledge/folders/{folder_id}')
    assert delete_resp.status_code == 409, delete_resp.text

    embedder.resume_event.set()
    _wait_until(lambda: True if folder_id not in aero_api._REINDEXING_FOLDER_IDS else None)

    with app.state.db.session() as session:
        assert session.get(KnowledgeFolder, folder_id) is not None

    delete_after = csrf_client.delete(f'/api/v1/aero-work/knowledge/folders/{folder_id}')
    assert delete_after.status_code == 204, delete_after.text

    with app.state.db.session() as session:
        assert session.get(KnowledgeFolder, folder_id) is None
        assert session.query(KnowledgeFile).filter_by(folder_id=folder_id).count() == 0
        assert session.query(KnowledgeChunk).count() == 0


# ---- 4. reindex 중 동일 폴더 재요청 409, 다른 폴더는 독립적으로 202 ----


def test_reindex_conflict_is_scoped_to_the_indexing_folder(
    csrf_client, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    embedder_a = _PausingEmbedder()
    embedder_a.pause_at = 1
    monkeypatch.setattr(aero_api, 'build_embedder', lambda _settings, _db: embedder_a)

    root_a = tmp_path / 'kb-a'
    root_a.mkdir()
    (root_a / 'a.md').write_text('내용 A', encoding='utf-8')
    root_b = tmp_path / 'kb-b'
    root_b.mkdir()
    (root_b / 'b.md').write_text('내용 B', encoding='utf-8')

    folder_a = _register_folder(csrf_client, root_a, 'a')
    folder_b = _register_folder(csrf_client, root_b, 'b')

    reindex_a = csrf_client.post(f'/api/v1/aero-work/knowledge/folders/{folder_a}/reindex')
    assert reindex_a.status_code == 202
    assert embedder_a.reached_pause.wait(timeout=5)

    same_folder_conflict = csrf_client.post(f'/api/v1/aero-work/knowledge/folders/{folder_a}/reindex')
    assert same_folder_conflict.status_code == 409, same_folder_conflict.text

    monkeypatch.setattr(aero_api, 'build_embedder', lambda _settings, _db: _FakeEmbedder())
    other_folder_ok = csrf_client.post(f'/api/v1/aero-work/knowledge/folders/{folder_b}/reindex?inline=true')
    assert other_folder_ok.status_code == 200, other_folder_ok.text
    assert other_folder_ok.json()['status'] == 'ready'

    embedder_a.resume_event.set()
    _wait_until(lambda: True if folder_a not in aero_api._REINDEXING_FOLDER_IDS else None)


# ---- 5. 백그라운드 임베더 실패 → error 상태 + 가드 해제(재요청 가능) ----


def test_background_embedder_failure_records_error_and_releases_guard(
    csrf_client, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(aero_api, 'build_embedder', lambda _settings, _db: _FailingEmbedder())

    root = tmp_path / 'kb'
    root.mkdir()
    (root / 'doc.md').write_text('임베딩 실패 시나리오', encoding='utf-8')
    folder_id = _register_folder(csrf_client, root)

    reindex = csrf_client.post(f'/api/v1/aero-work/knowledge/folders/{folder_id}/reindex')
    assert reindex.status_code == 202, reindex.text

    def _folder() -> dict:
        listing = csrf_client.get('/api/v1/aero-work/knowledge/folders')
        assert listing.status_code == 200
        return next(f for f in listing.json()['folders'] if f['id'] == folder_id)

    def _errored_or_none():
        current = _folder()
        return current if current['status'] == 'error' else None

    errored = _wait_until(_errored_or_none)
    assert errored['status_detail'] == '테스트: Ollama 연결 실패를 흉내낸다'
    assert folder_id not in aero_api._REINDEXING_FOLDER_IDS, '실패해도 가드는 해제되어야 재요청이 가능하다'

    # 가드가 실제로 풀렸는지 — 같은 폴더에 즉시 재요청해도 409 가 아니라 202/200 이어야 한다.
    monkeypatch.setattr(aero_api, 'build_embedder', lambda _settings, _db: _FakeEmbedder())
    retry = csrf_client.post(f'/api/v1/aero-work/knowledge/folders/{folder_id}/reindex?inline=true')
    assert retry.status_code == 200, retry.text
    assert retry.json()['status'] == 'ready'


# ---- 6. FTS 테이블 강제 DROP 후 검색 → LIKE 폴백 ----


def test_keyword_search_falls_back_to_like_after_fts_table_dropped(
    csrf_client, fake_embedder, tmp_path: Path, app
) -> None:
    _apply_fts_migration(app)
    root = tmp_path / 'kb'
    root.mkdir()
    (root / 'doc.md').write_text('예산편성 계획과 여행 경비 정산', encoding='utf-8')
    folder_id = _register_folder(csrf_client, root)
    assert csrf_client.post(f'/api/v1/aero-work/knowledge/folders/{folder_id}/reindex?inline=true').status_code == 200

    before = csrf_client.post('/api/v1/aero-work/knowledge/keyword-search', json={'query': '예산'})
    assert before.status_code == 200
    assert len(before.json()['hits']) >= 1

    _drop_fts_table(app)

    after = csrf_client.post('/api/v1/aero-work/knowledge/keyword-search', json={'query': '예산'})
    assert after.status_code == 200, after.text  # FTS 부재를 예외로 흘리지 않고 LIKE 폴백으로 흡수
    assert len(after.json()['hits']) >= 1
    assert after.json()['hits'][0]['rel_path'] == 'doc.md'


# ---- 7. 삭제된 파일 내용이 FTS 잔재로 검색되지 않음 ----


def test_deleted_file_content_does_not_linger_in_fts_after_reindex(
    csrf_client, fake_embedder, tmp_path: Path, app
) -> None:
    _apply_fts_migration(app)
    root = tmp_path / 'kb'
    root.mkdir()
    kept = root / 'kept.md'
    kept.write_text('유지되는 문서 본문', encoding='utf-8')
    removed = root / 'removed.md'
    removed.write_text('삭제예정고유토큰zzqq 본문', encoding='utf-8')

    folder_id = _register_folder(csrf_client, root)
    first = csrf_client.post(f'/api/v1/aero-work/knowledge/folders/{folder_id}/reindex?inline=true')
    assert first.status_code == 200, first.text
    assert first.json()['file_count'] == 2

    found_before = csrf_client.post('/api/v1/aero-work/knowledge/keyword-search', json={'query': '삭제예정고유토큰zzqq'})
    assert found_before.status_code == 200
    assert len(found_before.json()['hits']) == 1

    removed.unlink()
    second = csrf_client.post(f'/api/v1/aero-work/knowledge/folders/{folder_id}/reindex?inline=true')
    assert second.status_code == 200, second.text
    assert second.json()['file_count'] == 1

    found_after = csrf_client.post('/api/v1/aero-work/knowledge/keyword-search', json={'query': '삭제예정고유토큰zzqq'})
    assert found_after.status_code == 200
    assert found_after.json()['hits'] == []

    with app.state.db.session() as session:
        leftover = session.execute(
            sa.text(f"SELECT COUNT(*) FROM {FTS_TABLE} WHERE content LIKE :needle"),
            {'needle': '%삭제예정고유토큰zzqq%'},
        ).scalar_one()
        assert leftover == 0


# ---- 8. 익명 401 / CSRF 미첨부 403 ----


def test_anonymous_keyword_search_is_rejected(client) -> None:
    resp = client.post('/api/v1/aero-work/knowledge/keyword-search', json={'query': '예산'})
    assert resp.status_code == 401


def test_reindex_without_csrf_token_is_rejected(client, tmp_path: Path) -> None:
    login = client.post('/api/v1/auth/login', json={'username': 'admin', 'password': 'password'})
    assert login.status_code == 200
    # csrf_client 픽스처와 달리 x-csrf-token 헤더를 첨부하지 않은 채로 뮤테이션을 시도한다.
    root = tmp_path / 'kb'
    root.mkdir()
    created = client.post(
        '/api/v1/aero-work/knowledge/folders',
        json={'name': 'kb', 'path': str(root)},
        headers={'x-csrf-token': login.json()['csrf_token']},
    )
    assert created.status_code == 201, created.text
    folder_id = created.json()['id']

    resp = client.post(f'/api/v1/aero-work/knowledge/folders/{folder_id}/reindex')
    assert resp.status_code == 403, resp.text
