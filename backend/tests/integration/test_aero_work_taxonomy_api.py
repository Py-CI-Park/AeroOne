"""Aero Work 업무 분류체계 마법사 REST — 실 앱 HTTP 스택(라우팅·CSRF·인증·서비스) 통합 검증.

propose 단계는 실 LLM 호출을 결정적 스텁으로 대체해(``taxonomy_service.propose_categories``
자체를 monkeypatch) CI/폐쇄망에서도 결정적으로 돈다. 색인은 결정적 fake 임베더로 실 Ollama
없이 만든다. 익명 차단·CSRF 강제·propose→apply→GET→DELETE 왕복을 본다.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import app.modules.aero_work.api as aero_api


class _FakeEmbedder:
    """route 가 생성하는 OllamaEmbedder 를 대체하는 결정적 임베더(지식폴더 색인용)."""

    model = 'fake-embed'

    def __init__(self, settings=None) -> None:  # noqa: ANN001 (route 시그니처 호환)
        pass

    def embed_one(self, text: str) -> list[float]:
        return [1.0]

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0] for _ in texts]


@pytest.fixture()
def fake_embedder(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(aero_api, 'OllamaEmbedder', _FakeEmbedder)


@pytest.fixture()
def kb_dir(tmp_path: Path) -> Path:
    root = tmp_path / 'kb'
    root.mkdir()
    (root / '예산지침.md').write_text('예산 편성 기준과 집행 절차를 정리한 문서', encoding='utf-8')
    (root / '출장규정.md').write_text('출장 여비 정산 규정', encoding='utf-8')
    return root


def _index_kb(csrf_client, kb_dir: Path) -> list[int]:
    created = csrf_client.post('/api/v1/aero-work/knowledge/folders', json={'name': '규정', 'path': str(kb_dir)})
    assert created.status_code == 201, created.text
    folder_id = created.json()['id']
    reindex = csrf_client.post(f'/api/v1/aero-work/knowledge/folders/{folder_id}/reindex')
    assert reindex.status_code == 200, reindex.text
    wiki = csrf_client.get('/api/v1/aero-work/knowledge/wiki').json()
    return sorted(family['representative']['id'] for family in wiki['families'])


def _stub_propose(candidates: list[dict], model: str = 'stub-model', reason: str = 'ok', truncated: bool = False):
    def _fake(db, settings, user_id, *, organization, department, duties):
        return candidates, model, reason, truncated

    return _fake


def test_anonymous_is_rejected(client) -> None:
    assert client.get('/api/v1/aero-work/taxonomy').status_code == 401
    assert client.post('/api/v1/aero-work/taxonomy/propose', json={}).status_code == 401
    assert client.post('/api/v1/aero-work/taxonomy/apply', json={'categories': []}).status_code == 401
    assert client.delete('/api/v1/aero-work/taxonomy/1').status_code == 401


def test_mutation_requires_csrf(client) -> None:
    login = client.post('/api/v1/auth/login', json={'username': 'admin', 'password': 'password'})
    assert login.status_code == 200  # 로그인은 됐지만 x-csrf-token 헤더는 없음
    resp = client.post(
        '/api/v1/aero-work/taxonomy/apply', json={'categories': []}
    )
    assert resp.status_code == 403


def test_propose_apply_get_delete_round_trip(
    csrf_client, fake_embedder, kb_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    file_ids = _index_kb(csrf_client, kb_dir)
    assert len(file_ids) == 2

    candidates = [
        {'name': '예산업무', 'description': '예산 편성/집행', 'file_ids': [file_ids[0]]},
        {'name': '출장업무', 'description': '출장 여비 정산', 'file_ids': [file_ids[1]]},
    ]
    monkeypatch.setattr(aero_api, 'propose_categories', _stub_propose(candidates, 'stub-model'))

    propose = csrf_client.post(
        '/api/v1/aero-work/taxonomy/propose',
        json={'organization': '국방부', 'department': '예산과', 'duties': '예산 편성 및 집행 관리'},
    )
    assert propose.status_code == 200, propose.text
    body = propose.json()
    assert body['model'] == 'stub-model'
    assert body['reason'] == 'ok'
    assert body['truncated'] is False
    assert [c['name'] for c in body['candidates']] == ['예산업무', '출장업무']

    apply_resp = csrf_client.post('/api/v1/aero-work/taxonomy/apply', json={'categories': body['candidates']})
    assert apply_resp.status_code == 200, apply_resp.text
    assert apply_resp.json() == {'applied': 2}

    listing = csrf_client.get('/api/v1/aero-work/taxonomy')
    assert listing.status_code == 200, listing.text
    categories = listing.json()['categories']
    assert [c['name'] for c in categories] == ['예산업무', '출장업무']
    assert categories[0]['files'][0]['id'] == file_ids[0]
    assert categories[0]['files'][0]['folder_name'] == '규정'

    category_id = categories[0]['id']
    deleted = csrf_client.delete(f'/api/v1/aero-work/taxonomy/{category_id}')
    assert deleted.status_code == 204

    remaining = csrf_client.get('/api/v1/aero-work/taxonomy').json()['categories']
    assert [c['name'] for c in remaining] == ['출장업무']


def test_apply_is_idempotent_and_replaces_previous_categories(csrf_client, fake_embedder, kb_dir: Path) -> None:
    file_ids = _index_kb(csrf_client, kb_dir)
    categories = [{'name': '예산업무', 'description': '', 'file_ids': [file_ids[0]]}]

    first = csrf_client.post('/api/v1/aero-work/taxonomy/apply', json={'categories': categories})
    assert first.status_code == 200
    assert first.json() == {'applied': 1}

    second = csrf_client.post('/api/v1/aero-work/taxonomy/apply', json={'categories': categories})
    assert second.status_code == 200
    assert second.json() == {'applied': 1}

    listing = csrf_client.get('/api/v1/aero-work/taxonomy').json()['categories']
    assert len(listing) == 1  # 재적용해도 중복 생성되지 않는다(멱등).


def test_delete_unknown_category_returns_404(csrf_client) -> None:
    resp = csrf_client.delete('/api/v1/aero-work/taxonomy/999999')
    assert resp.status_code == 404


def test_propose_rejects_blank_duties(csrf_client) -> None:
    resp = csrf_client.post(
        '/api/v1/aero-work/taxonomy/propose',
        json={'organization': '국방부', 'department': '예산과', 'duties': ''},
    )
    assert resp.status_code == 422


def test_propose_reports_non_ok_reason_when_ai_disabled(
    csrf_client, monkeypatch: pytest.MonkeyPatch
) -> None:
    """M1: reason 필드는 'ok' 아닌 구체 사유(예: ai_disabled)를 그대로 노출한다."""

    monkeypatch.setattr(aero_api, 'propose_categories', _stub_propose([], model='', reason='ai_disabled'))
    resp = csrf_client.post(
        '/api/v1/aero-work/taxonomy/propose',
        json={'organization': '국방부', 'department': '예산과', 'duties': '예산 편성'},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body['reason'] == 'ai_disabled'
    assert body['candidates'] == []


def test_propose_reports_truncated_when_indexed_files_exceed_cap(
    csrf_client, monkeypatch: pytest.MonkeyPatch
) -> None:
    """L3: 색인 파일이 200건 상한을 넘으면 truncated=True 를 그대로 노출한다."""

    monkeypatch.setattr(aero_api, 'propose_categories', _stub_propose([], truncated=True))
    resp = csrf_client.post(
        '/api/v1/aero-work/taxonomy/propose',
        json={'organization': '국방부', 'department': '예산과', 'duties': '예산 편성'},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()['truncated'] is True
