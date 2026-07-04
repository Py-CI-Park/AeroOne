from __future__ import annotations

from pathlib import Path
from app.core.security import hash_password
from app.modules.admin.models import UserPermission
from app.modules.auth.models import User


def _seed(root: Path, rel: str, body: str) -> None:
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(f'<html><body><h1>{body}</h1><p>{body} 상세 본문</p></body></html>', encoding='utf-8')


def _mock_ollama(monkeypatch) -> None:
    def fake_chat(self, messages, citations=None):
        return '선택 문서 기반 답변'

    monkeypatch.setattr('app.modules.ai.service.OllamaClient.chat', fake_chat)


def test_selected_refs_become_citations(client, test_paths, monkeypatch) -> None:
    _seed(test_paths['document_root'], '항공/정비.html', '정비 절차')
    _mock_ollama(monkeypatch)

    response = client.post(
        '/api/v1/ai/chat',
        json={
            'messages': [{'role': 'user', 'content': '정비 절차 요약'}],
            'selected_refs': [{'collection': 'document', 'path': '항공/정비.html'}],
        },
    )

    assert response.status_code == 200
    citations = response.json()['citations']
    assert len(citations) == 1
    assert citations[0]['collection'] == 'document'
    assert citations[0]['path'] == '항공/정비.html'
    assert citations[0]['navigation_url'].startswith('/documents?path=')


def test_selected_refs_take_precedence_over_search(client, test_paths, monkeypatch) -> None:
    _seed(test_paths['document_root'], 'a.html', 'A 문서')
    _seed(test_paths['civil_aircraft_root'], 'b.html', 'B 문서')
    _mock_ollama(monkeypatch)

    # search 가 호출되면 안 된다(선택 우선). 호출되면 실패하도록 폭파.
    def explode(*args, **kwargs):
        raise AssertionError('search must not run when selected_refs is provided')

    monkeypatch.setattr('app.modules.collections.search_service.HtmlCollectionSearchService.search', explode)

    response = client.post(
        '/api/v1/ai/chat',
        json={
            'messages': [{'role': 'user', 'content': '질문'}],
            'use_search': True,
            'selected_refs': [{'collection': 'civil', 'path': 'b.html'}],
        },
    )

    assert response.status_code == 200
    citations = response.json()['citations']
    assert [c['path'] for c in citations] == ['b.html']
    assert citations[0]['collection'] == 'civil'


def test_traversal_and_unknown_refs_are_silently_dropped(client, test_paths, monkeypatch) -> None:
    _seed(test_paths['document_root'], 'valid.html', '유효 문서')
    _mock_ollama(monkeypatch)

    response = client.post(
        '/api/v1/ai/chat',
        json={
            'messages': [{'role': 'user', 'content': '질문'}],
            'selected_refs': [
                {'collection': 'document', 'path': '../../etc/secret.html'},
                {'collection': 'document', 'path': 'missing.html'},
                {'collection': 'document', 'path': 'valid.html'},
            ],
        },
    )

    assert response.status_code == 200
    citations = response.json()['citations']
    # traversal/없는 파일은 조용히 드롭, 유효 문서만 남는다.
    assert [c['path'] for c in citations] == ['valid.html']


def test_nsa_selected_ref_is_dropped_for_anonymous(client, test_paths, monkeypatch) -> None:
    _seed(test_paths['nsa_root'], 'secret-brief.html', 'NSA 문서')
    _mock_ollama(monkeypatch)

    response = client.post(
        '/api/v1/ai/chat',
        json={
            'messages': [{'role': 'user', 'content': '질문'}],
            'selected_refs': [{'collection': 'nsa', 'path': 'secret-brief.html'}],
        },
    )

    assert response.status_code == 200
    assert response.json()['citations'] == []


def test_nsa_selected_ref_is_allowed_for_authorized_user(client, app, test_paths, monkeypatch) -> None:
    _seed(test_paths['nsa_root'], 'secret-brief.html', 'NSA 문서')
    _mock_ollama(monkeypatch)
    with app.state.db.session() as session:
        user = User(username='nsa-user', password_hash=hash_password('password'), role='user', is_active=True)
        session.add(user)
        session.flush()
        session.add(UserPermission(user_id=user.id, permission_key='collections.nsa.read'))
        session.commit()
    login = client.post('/api/v1/auth/login', json={'username': 'nsa-user', 'password': 'password'})
    assert login.status_code == 200

    response = client.post(
        '/api/v1/ai/chat',
        json={
            'messages': [{'role': 'user', 'content': '질문'}],
            'selected_refs': [{'collection': 'nsa', 'path': 'secret-brief.html'}],
        },
    )

    assert response.status_code == 200
    citations = response.json()['citations']
    assert [c['collection'] for c in citations] == ['nsa']


def test_no_selected_refs_without_search_yields_no_citations(client, monkeypatch) -> None:
    _mock_ollama(monkeypatch)
    response = client.post(
        '/api/v1/ai/chat',
        json={'messages': [{'role': 'user', 'content': '그냥 질문'}]},
    )
    assert response.status_code == 200
    assert response.json()['citations'] == []
