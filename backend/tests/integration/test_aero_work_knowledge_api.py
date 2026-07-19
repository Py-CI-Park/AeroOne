"""Aero Work 지식폴더 REST — 실 앱 HTTP 스택(라우팅·CSRF·인증·서비스) 통합 검증.

임베더는 결정적 fake 로 대체해 실 Ollama 없이 CI/폐쇄망에서도 결정적으로 돈다(실 Ollama
의미검색은 별도 서비스 E2E 로 확인). 익명 차단·CSRF 강제·등록/색인/검색/삭제 왕복을 본다.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import app.modules.aero_work.api as aero_api


class _FakeEmbedder:
    """route 가 생성하는 OllamaEmbedder 를 대체하는 결정적 bag-of-vocab 임베더."""

    model = 'fake-embed'
    VOCAB = ('travel', 'expense', 'security', 'usb', 'export', 'meeting')

    def __init__(self, settings=None) -> None:  # noqa: ANN001 (route 시그니처 호환)
        pass

    def embed_one(self, text: str) -> list[float]:
        low = text.lower()
        return [float(low.count(term)) for term in self.VOCAB]

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_one(text) for text in texts]


@pytest.fixture()
def fake_embedder(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(aero_api, 'OllamaEmbedder', _FakeEmbedder)


@pytest.fixture()
def kb_dir(tmp_path: Path) -> Path:
    root = tmp_path / 'kb'
    root.mkdir()
    (root / 'travel.md').write_text('travel expense settlement rules apply', encoding='utf-8')
    (root / 'security.md').write_text('security pledge: usb export is banned', encoding='utf-8')
    return root


def test_anonymous_is_rejected(client) -> None:
    assert client.get('/api/v1/aero-work/knowledge/folders').status_code == 401


def test_mutation_requires_csrf(client, kb_dir: Path) -> None:
    login = client.post('/api/v1/auth/login', json={'username': 'admin', 'password': 'password'})
    assert login.status_code == 200  # 로그인은 됐지만 x-csrf-token 헤더는 없음
    resp = client.post('/api/v1/aero-work/knowledge/folders', json={'name': 'x', 'path': str(kb_dir)})
    assert resp.status_code == 403


def test_register_reindex_search_delete_flow(csrf_client, fake_embedder, kb_dir: Path) -> None:
    created = csrf_client.post(
        '/api/v1/aero-work/knowledge/folders', json={'name': '규정', 'path': str(kb_dir)}
    )
    assert created.status_code == 201, created.text
    folder = created.json()
    assert folder['status'] == 'pending'
    folder_id = folder['id']

    listing = csrf_client.get('/api/v1/aero-work/knowledge/folders')
    assert listing.status_code == 200
    assert any(item['id'] == folder_id for item in listing.json()['folders'])

    reindex = csrf_client.post(f'/api/v1/aero-work/knowledge/folders/{folder_id}/reindex')
    assert reindex.status_code == 200, reindex.text
    indexed = reindex.json()
    assert indexed['status'] == 'ready'
    assert indexed['file_count'] == 2
    assert indexed['chunk_count'] >= 2

    search = csrf_client.post('/api/v1/aero-work/knowledge/search', json={'query': 'usb export'})
    assert search.status_code == 200, search.text
    body = search.json()
    assert body['model'] == 'fake-embed'
    assert body['hits'], '근거가 있어야 한다'
    assert body['hits'][0]['rel_path'] == 'security.md'

    deleted = csrf_client.delete(f'/api/v1/aero-work/knowledge/folders/{folder_id}')
    assert deleted.status_code == 204
    assert csrf_client.get('/api/v1/aero-work/knowledge/folders').json()['folders'] == []


def test_register_rejects_missing_path(csrf_client, tmp_path: Path) -> None:
    resp = csrf_client.post(
        '/api/v1/aero-work/knowledge/folders',
        json={'name': 'x', 'path': str(tmp_path / 'does-not-exist')},
    )
    assert resp.status_code == 400


def test_keyword_search_flow(csrf_client, fake_embedder, kb_dir: Path) -> None:
    created = csrf_client.post(
        '/api/v1/aero-work/knowledge/folders', json={'name': '규정', 'path': str(kb_dir)}
    )
    folder_id = created.json()['id']
    csrf_client.post(f'/api/v1/aero-work/knowledge/folders/{folder_id}/reindex')

    resp = csrf_client.post('/api/v1/aero-work/knowledge/keyword-search', json={'query': 'usb'})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body['model'] == 'keyword'
    assert body['hits']
    assert body['hits'][0]['rel_path'] == 'security.md'


def test_wiki_groups_version_families(csrf_client, fake_embedder, tmp_path: Path) -> None:
    root = tmp_path / 'kb'
    root.mkdir()
    (root / '예산_20260101.md').write_text('예산 옛판', encoding='utf-8')
    (root / '예산_20260715.md').write_text('예산 최신', encoding='utf-8')
    (root / '단일문서.md').write_text('단독', encoding='utf-8')
    created = csrf_client.post(
        '/api/v1/aero-work/knowledge/folders', json={'name': '규정', 'path': str(root)}
    )
    folder_id = created.json()['id']
    csrf_client.post(f'/api/v1/aero-work/knowledge/folders/{folder_id}/reindex')

    resp = csrf_client.get('/api/v1/aero-work/knowledge/wiki')
    assert resp.status_code == 200, resp.text
    families = resp.json()['families']

    budget = next(f for f in families if f['representative']['rel_path'].startswith('예산'))
    assert budget['has_versions'] is True
    assert budget['representative']['rel_path'] == '예산_20260715.md'
    assert len(budget['items']) == 2

    solo = next(f for f in families if f['representative']['rel_path'] == '단일문서.md')
    assert solo['has_versions'] is False
