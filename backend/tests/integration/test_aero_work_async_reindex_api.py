"""G004: 재색인 API 비동기화(202 + 진행률 status_detail + 409 가드) 통합 검증.

기존 ``/reindex`` 는 동기 완료 후 200 을 돌려줬지만, 이제 기본 호출은 즉시 202
``{"status":"indexing"}`` 를 반환하고 백그라운드 스레드가 색인한다(``inline=true`` 는 예전
동작을 유지하는 테스트 전용 훅 — 다른 지식폴더 테스트들이 이걸로 결정성을 확보한다).

이 파일은 실제 백그라운드 스레드 동시성을 검증해야 하므로, 5번째 파일 처리 직후 진행률이
커밋된 시점에서 멈춰 세우는 결정적 임베더(``_PausingEmbedder``)로 타이밍을 통제한다 —
sleep 폴링에 기대지 않고 ``threading.Event`` 로 "5/8 파일" 상태를 확실히 관찰한다.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

import app.modules.aero_work.api as aero_api


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


def test_reindex_returns_202_then_progresses_and_completes(csrf_client, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    embedder = _PausingEmbedder()
    embedder.pause_at = 6  # 5번째 파일까지 처리·커밋된 뒤, 6번째 embed() 호출에서 대기
    monkeypatch.setattr(aero_api, 'OllamaEmbedder', lambda settings=None: embedder)

    root = tmp_path / 'kb'
    root.mkdir()
    for i in range(8):
        (root / f'doc{i}.md').write_text(f'문서 {i} 예산편성 내용', encoding='utf-8')

    created = csrf_client.post(
        '/api/v1/aero-work/knowledge/folders', json={'name': 'kb', 'path': str(root)}
    )
    assert created.status_code == 201, created.text
    folder_id = created.json()['id']

    reindex = csrf_client.post(f'/api/v1/aero-work/knowledge/folders/{folder_id}/reindex')
    assert reindex.status_code == 202, reindex.text
    assert reindex.json() == {'status': 'indexing'}

    assert embedder.reached_pause.wait(timeout=5), '백그라운드 스레드가 6번째 파일까지 도달해야 한다'

    def _get_folder() -> dict:
        listing = csrf_client.get('/api/v1/aero-work/knowledge/folders')
        assert listing.status_code == 200
        return next(f for f in listing.json()['folders'] if f['id'] == folder_id)

    folder = _get_folder()
    assert folder['status'] == 'indexing'
    assert folder['status_detail'] == '5/8 파일'

    # 진행 중인 폴더에 다시 재색인을 걸면 409(가드).
    conflict = csrf_client.post(f'/api/v1/aero-work/knowledge/folders/{folder_id}/reindex')
    assert conflict.status_code == 409

    embedder.resume_event.set()

    def _ready_or_none():
        current = _get_folder()
        return current if current['status'] == 'ready' else None

    ready_folder = _wait_until(_ready_or_none)
    assert ready_folder['file_count'] == 8
    assert ready_folder['chunk_count'] >= 8
    assert '8개 파일' in ready_folder['status_detail']

    # 완료 후에는 다시 재색인을 걸 수 있다(가드 해제).
    reindex_again = csrf_client.post(f'/api/v1/aero-work/knowledge/folders/{folder_id}/reindex?inline=true')
    assert reindex_again.status_code == 200, reindex_again.text


def test_reindex_conflict_only_for_same_folder(csrf_client, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    embedder_a = _PausingEmbedder()
    embedder_a.pause_at = 1
    monkeypatch.setattr(aero_api, 'OllamaEmbedder', lambda settings=None: embedder_a)

    root_a = tmp_path / 'kb-a'
    root_a.mkdir()
    (root_a / 'a.md').write_text('내용 A', encoding='utf-8')
    root_b = tmp_path / 'kb-b'
    root_b.mkdir()
    (root_b / 'b.md').write_text('내용 B', encoding='utf-8')

    folder_a = csrf_client.post(
        '/api/v1/aero-work/knowledge/folders', json={'name': 'a', 'path': str(root_a)}
    ).json()['id']
    folder_b = csrf_client.post(
        '/api/v1/aero-work/knowledge/folders', json={'name': 'b', 'path': str(root_b)}
    ).json()['id']

    reindex_a = csrf_client.post(f'/api/v1/aero-work/knowledge/folders/{folder_a}/reindex')
    assert reindex_a.status_code == 202
    assert embedder_a.reached_pause.wait(timeout=5)

    # 다른 폴더는 첫 폴더가 진행 중이어도 영향받지 않는다(폴더별 가드).
    monkeypatch.setattr(aero_api, 'OllamaEmbedder', lambda settings=None: _PausingEmbedder())
    reindex_b = csrf_client.post(f'/api/v1/aero-work/knowledge/folders/{folder_b}/reindex?inline=true')
    assert reindex_b.status_code == 200, reindex_b.text
    assert reindex_b.json()['status'] == 'ready'

    embedder_a.resume_event.set()
    # L4: 백그라운드 스레드가 가드를 해제할 때까지 기다린다 — 기다리지 않으면 스레드가
    # 다음 테스트의 fixture teardown(세션/엔진 정리)과 경합해 간헐적으로 깨질 수 있다.
    _wait_until(lambda: True if folder_a not in aero_api._REINDEXING_FOLDER_IDS else None)


def test_reindex_missing_folder_returns_404(csrf_client) -> None:
    resp = csrf_client.post('/api/v1/aero-work/knowledge/folders/999999/reindex')
    assert resp.status_code == 404

def test_startup_sweep_resets_stale_indexing_folders(csrf_client, app, tmp_path: Path) -> None:
    """기동 스윕(H2) — 이전 프로세스가 남긴 좀비 'indexing' 폴더를 error 로 되돌린다.

    재리뷰 P3 반영: reset_stale_indexing_folders 를 직접 호출해 상태 전환과 사유 문구,
    정상(ready) 폴더 불간섭을 함께 잠근다.
    """

    root = tmp_path / 'kb-stale'
    root.mkdir()
    (root / 'doc.md').write_text('예산편성 내용', encoding='utf-8')
    created = csrf_client.post(
        '/api/v1/aero-work/knowledge/folders', json={'name': 'kb-stale', 'path': str(root)}
    )
    assert created.status_code == 201, created.text
    folder_id = created.json()['id']

    from app.modules.aero_work.models import KnowledgeFolder

    # 이전 프로세스가 죽으며 남긴 좀비 상태를 시드한다(인메모리 가드는 비어 있음).
    with app.state.db.session() as session:
        folder = session.get(KnowledgeFolder, folder_id)
        folder.status = 'indexing'
        folder.status_detail = '3/9 파일'
        session.commit()

    with app.state.db.session() as session:
        swept = aero_api.reset_stale_indexing_folders(session)
    assert swept == 1

    with app.state.db.session() as session:
        folder = session.get(KnowledgeFolder, folder_id)
        assert folder.status == 'error'
        assert folder.status_detail == '서버 재시작으로 중단됨'

    # 이미 터미널 상태인 폴더는 스윕이 건드리지 않는다.
    with app.state.db.session() as session:
        assert aero_api.reset_stale_indexing_folders(session) == 0
