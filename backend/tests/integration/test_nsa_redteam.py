from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.modules.admin.models import ResourceGrant, UserPermission
from app.modules.auth.models import User
from app.modules.collections.search_service import CollectionSearchResult


def _seed_html(root: Path, rel: str, token: str) -> None:
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(f'<html><body><h1>{token}</h1><p>{token} body</p></body></html>', encoding='utf-8')


def _create_user(app, username: str, *, permission: str | None = None, grant: bool = False) -> None:
    with app.state.db.session() as session:
        user = User(username=username, password_hash=hash_password('password'), role='user', is_active=True)
        session.add(user)
        session.flush()
        if permission is not None:
            session.add(UserPermission(user_id=user.id, permission_key=permission))
        if grant:
            session.add(
                ResourceGrant(
                    subject_type='user',
                    subject_id=user.id,
                    resource_type='collection',
                    resource_id='nsa',
                    permission_key='collections.nsa.read',
                )
            )
        session.commit()


def _client_for(app, username: str | None = None) -> TestClient:
    client = TestClient(app)
    if username is not None:
        response = client.post('/api/v1/auth/login', json={'username': username, 'password': 'password'})
        assert response.status_code == 200
        client.headers.update({'x-csrf-token': response.json()['csrf_token']})
    return client


def _result_collections(payload: dict[str, object], key: str = 'collection') -> set[str]:
    return {item[key] for item in payload['results']}  # type: ignore[index]


def test_nsa_collection_direct_surfaces_block_unauthorized_and_allow_authorized(app, test_paths) -> None:
    _seed_html(test_paths['nsa_root'], 'secret.html', 'NSA_DIRECT_SECRET')
    _create_user(app, 'plain')
    _create_user(app, 'perm-user', permission='collections.nsa.read')
    _create_user(app, 'grant-user', grant=True)

    unauthorized = [_client_for(app), _client_for(app, 'plain')]
    direct_requests = [
        ('get', '/api/v1/collections/nsa/list', None),
        ('get', '/api/v1/collections/nsa/content/html', {'path': 'secret.html'}),
        ('get', '/api/v1/collections/nsa/download/html', {'path': 'secret.html'}),
    ]
    for actor in unauthorized:
        for method, url, params in direct_requests:
            response = getattr(actor, method)(url, params=params)
            assert response.status_code in {401, 403}, (url, response.status_code, response.text)
            assert 'NSA_DIRECT_SECRET' not in response.text

    for username in ['admin', 'perm-user', 'grant-user']:
        actor = _client_for(app, username)
        assert actor.get('/api/v1/collections/nsa/list').status_code == 200
        html = actor.get('/api/v1/collections/nsa/content/html', params={'path': 'secret.html'})
        assert html.status_code == 200
        assert 'NSA_DIRECT_SECRET' in html.text
        download = actor.get('/api/v1/collections/nsa/download/html', params={'path': 'secret.html'})
        assert download.status_code == 200
        assert 'NSA_DIRECT_SECRET' in download.text


def test_collection_search_with_nsa_scope_filters_unauthorized_and_returns_for_authorized(app, test_paths) -> None:
    _seed_html(test_paths['document_root'], 'public.html', 'RedTeamSearchToken')
    _seed_html(test_paths['nsa_root'], 'secret.html', 'RedTeamSearchToken NSA_ONLY')
    _create_user(app, 'plain')
    _create_user(app, 'perm-user', permission='collections.nsa.read')
    _create_user(app, 'grant-user', grant=True)

    for actor in [_client_for(app), _client_for(app, 'plain')]:
        response = actor.get('/api/v1/collections/search', params={'q': 'RedTeamSearchToken', 'collections': 'document,nsa'})
        assert response.status_code == 200
        payload = response.json()
        assert 'nsa' not in payload['collections']
        assert 'nsa' not in _result_collections(payload)
        assert all('NSA_ONLY' not in item.get('snippet', '') for item in payload['results'])

    for username in ['admin', 'perm-user', 'grant-user']:
        response = _client_for(app, username).get(
            '/api/v1/collections/search', params={'q': 'RedTeamSearchToken', 'collections': 'document,nsa'}
        )
        assert response.status_code == 200
        payload = response.json()
        assert 'nsa' in payload['collections']
        assert 'nsa' in _result_collections(payload)


def test_admin_unified_search_include_nsa_filters_unauthorized_and_returns_for_authorized(app, test_paths) -> None:
    _seed_html(test_paths['document_root'], 'public.html', 'UnifiedRedTeamToken')
    _seed_html(test_paths['nsa_root'], 'secret.html', 'UnifiedRedTeamToken NSA_UNIFIED')
    _create_user(app, 'plain')
    _create_user(app, 'perm-user', permission='collections.nsa.read')
    _create_user(app, 'grant-user', grant=True)

    anonymous = _client_for(app).get('/api/v1/admin/search', params={'q': 'UnifiedRedTeamToken', 'include_nsa': 'true'})
    assert anonymous.status_code in {401, 403}
    assert 'NSA_UNIFIED' not in anonymous.text

    plain = _client_for(app, 'plain').get('/api/v1/admin/search', params={'q': 'UnifiedRedTeamToken', 'include_nsa': 'true'})
    assert plain.status_code == 200
    plain_payload = plain.json()
    assert 'nsa' not in _result_collections(plain_payload, key='source')
    assert all('NSA_UNIFIED' not in item.get('snippet', '') for item in plain_payload['results'])

    for username in ['admin', 'perm-user', 'grant-user']:
        response = _client_for(app, username).get(
            '/api/v1/admin/search', params={'q': 'UnifiedRedTeamToken', 'include_nsa': 'true'}
        )
        assert response.status_code == 200
        assert 'nsa' in _result_collections(response.json(), key='source')


def test_ai_chat_drops_nsa_scope_and_selected_refs_for_unauthorized_but_allows_authorized(app, test_paths, monkeypatch) -> None:
    _seed_html(test_paths['nsa_root'], 'secret-brief.html', 'AI_NSA_SECRET')
    _seed_html(test_paths['document_root'], 'public.html', 'AI_PUBLIC')
    _create_user(app, 'plain')
    _create_user(app, 'perm-user', permission='collections.nsa.read')
    _create_user(app, 'grant-user', grant=True)
    captured_calls: list[dict[str, object]] = []

    def fake_chat(self, messages, roots, use_search, limit, **kwargs):
        selected_refs = list(kwargs.get('selected_refs') or [])
        collections = [root.collection for root in roots]
        captured_calls.append({'collections': collections, 'selected_refs': selected_refs})
        citations = []
        if ('nsa', 'secret-brief.html') in selected_refs:
            citations.append(
                CollectionSearchResult(
                    collection='nsa',
                    path='secret-brief.html',
                    name='secret-brief',
                    folder='',
                    snippet='AI_NSA_SECRET',
                    navigation_url='/nsa?path=secret-brief.html',
                    score=1.0,
                )
            )
        return 'redteam answer', citations

    monkeypatch.setattr('app.modules.ai.api.public.AiChatService.chat', fake_chat)

    body = {
        'messages': [{'role': 'user', 'content': 'summarize nsa and public'}],
        'use_search': True,
        'collections': ['document', 'nsa'],
        'selected_refs': [
            {'collection': 'nsa', 'path': 'secret-brief.html'},
            {'collection': 'document', 'path': 'public.html'},
        ],
        'temporary': True,
    }
    for actor in [_client_for(app), _client_for(app, 'plain')]:
        response = actor.post('/api/v1/ai/chat', json=body)
        assert response.status_code == 200
        call = captured_calls[-1]
        assert call['collections'] == ['document']
        assert ('nsa', 'secret-brief.html') not in call['selected_refs']
        assert all(citation['collection'] != 'nsa' for citation in response.json()['citations'])

    for username in ['admin', 'perm-user', 'grant-user']:
        response = _client_for(app, username).post('/api/v1/ai/chat', json=body)
        assert response.status_code == 200
        call = captured_calls[-1]
        assert call['collections'] == ['document', 'nsa']
        assert ('nsa', 'secret-brief.html') in call['selected_refs']
        assert any(citation['collection'] == 'nsa' for citation in response.json()['citations'])


@pytest.mark.parametrize('bad_collection', ['NSA', '../nsa', 'nsa/'])
def test_nsa_collection_name_bypass_attempts_are_denied_or_ineffective(app, test_paths, bad_collection) -> None:
    _seed_html(test_paths['nsa_root'], 'secret.html', 'CASE_PATH_NSA_SECRET')
    _create_user(app, 'plain')

    for actor in [_client_for(app), _client_for(app, 'plain')]:
        list_response = actor.get(f'/api/v1/collections/{bad_collection}/list')
        assert list_response.status_code in {400, 404, 405}
        assert 'CASE_PATH_NSA_SECRET' not in list_response.text

        html_response = actor.get(f'/api/v1/collections/{bad_collection}/content/html', params={'path': 'secret.html'})
        assert html_response.status_code in {400, 404, 405}
        assert 'CASE_PATH_NSA_SECRET' not in html_response.text

        download_response = actor.get(f'/api/v1/collections/{bad_collection}/download/html', params={'path': 'secret.html'})
        assert download_response.status_code in {400, 404, 405}
        assert 'CASE_PATH_NSA_SECRET' not in download_response.text


def test_requesting_nsa_via_public_collection_route_params_is_ineffective(app, test_paths) -> None:
    _seed_html(test_paths['nsa_root'], 'secret.html', 'ROUTE_PARAM_NSA_SECRET')
    _seed_html(test_paths['document_root'], 'secret.html', 'PUBLIC_DOCUMENT_SECRET_NAME')
    _seed_html(test_paths['civil_aircraft_root'], 'secret.html', 'PUBLIC_CIVIL_SECRET_NAME')
    _create_user(app, 'plain')

    for actor in [_client_for(app), _client_for(app, 'plain')]:
        for collection, expected in [('document', 'PUBLIC_DOCUMENT_SECRET_NAME'), ('civil', 'PUBLIC_CIVIL_SECRET_NAME')]:
            response = actor.get(f'/api/v1/collections/{collection}/content/html', params={'path': 'secret.html'})
            assert response.status_code == 200
            assert expected in response.text
            assert 'ROUTE_PARAM_NSA_SECRET' not in response.text

        for collection in ['document', 'civil']:
            traversal = actor.get(f'/api/v1/collections/{collection}/content/html', params={'path': '../nsa/secret.html'})
            assert traversal.status_code in {400, 404}
            assert 'ROUTE_PARAM_NSA_SECRET' not in traversal.text


def test_dashboard_public_modules_gates_nsa_card(app) -> None:
    _create_user(app, 'plain')
    _create_user(app, 'perm-user', permission='collections.nsa.read')

    for actor in [_client_for(app), _client_for(app, 'plain')]:
        response = actor.get('/api/v1/admin/service-modules/public')
        assert response.status_code == 200
        keys = {module['key'] for module in response.json()}
        assert 'nsa' not in keys
        assert {'document', 'civil-aircraft'} <= keys

    for username in ['admin', 'perm-user']:
        response = _client_for(app, username).get('/api/v1/admin/service-modules/public')
        assert response.status_code == 200
        assert 'nsa' in {module['key'] for module in response.json()}
