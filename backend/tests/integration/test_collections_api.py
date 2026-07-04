from __future__ import annotations

import pytest

from app.core.security import hash_password
from app.modules.admin.models import ResourceGrant, UserPermission
from app.modules.auth.models import User


def _login(client, username: str, password: str = 'password') -> None:
    response = client.post('/api/v1/auth/login', json={'username': username, 'password': password})
    assert response.status_code == 200
    client.headers.update({'x-csrf-token': response.json()['csrf_token']})


def _create_user(app, username: str, *, role: str = 'user', permission: str | None = None, grant: bool = False) -> None:
    with app.state.db.session() as session:
        user = User(username=username, password_hash=hash_password('password'), role=role, is_active=True)
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


def test_collection_list_includes_subfolders_and_skips_debug(client, test_paths) -> None:
    root = test_paths['document_root']
    (root / '회사소개.html').write_text('<html><body>intro</body></html>', encoding='utf-8')
    (root / '항공').mkdir(parents=True)
    (root / '항공' / '상용기_스펙.html').write_text('<html><body>spec</body></html>', encoding='utf-8')
    (root / '항공' / 'draft_debug.html').write_text('<html>debug</html>', encoding='utf-8')

    response = client.get('/api/v1/collections/document/list')

    assert response.status_code == 200
    assert response.json()['documents'] == [
        {'path': '회사소개.html', 'name': '회사소개', 'folder': ''},
        {'path': '항공/상용기_스펙.html', 'name': '상용기_스펙', 'folder': '항공'},
    ]


@pytest.mark.parametrize('collection', ['document', 'civil'])
def test_collection_list_empty_when_no_files(client, collection) -> None:
    response = client.get(f'/api/v1/collections/{collection}/list')

    assert response.status_code == 200
    assert response.json() == {'documents': []}


def test_nsa_collection_list_forbidden_for_anonymous_and_plain_user(client, app) -> None:
    assert client.get('/api/v1/collections/nsa/list').status_code == 403

    _create_user(app, 'plain')
    _login(client, 'plain')
    assert client.get('/api/v1/collections/nsa/list').status_code == 403


@pytest.mark.parametrize(
    ('username', 'kwargs'),
    [
        ('admin', {}),
        ('nsa-perm', {'permission': 'collections.nsa.read'}),
        ('nsa-grant', {'grant': True}),
    ],
)
def test_nsa_collection_list_allowed_for_authorized_users(client, app, username, kwargs) -> None:
    if username != 'admin':
        _create_user(app, username, **kwargs)
    _login(client, username)

    response = client.get('/api/v1/collections/nsa/list')

    assert response.status_code == 200
    assert response.json() == {'documents': []}


@pytest.mark.parametrize(
    ('collection', 'root_key'),
    [('document', 'document_root'), ('civil', 'civil_aircraft_root')],
)
def test_collection_content_returns_sanitized_html(client, test_paths, collection, root_key) -> None:
    (test_paths[root_key] / '항공').mkdir(parents=True)
    (test_paths[root_key] / '항공' / '상용기_스펙.html').write_text(
        '<html><head><title>문서</title>'
        '<link rel="stylesheet" href="https://cdn.example.com/x.css"></head>'
        '<body><script>window.__doc=1</script>'
        '<img src="https://cdn.example.com/a.png"/>'
        '<img src="local.png"/></body></html>',
        encoding='utf-8',
    )

    response = client.get(
        f'/api/v1/collections/{collection}/content/html',
        params={'path': '항공/상용기_스펙.html'},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['asset_type'] == 'html'
    html = payload['content_html']
    assert 'window.__doc=1' in html
    assert 'cdn.example.com/x.css' not in html
    assert 'https://cdn.example.com/a.png' not in html
    assert 'local.png' in html
    assert response.headers.get('content-security-policy')


def test_nsa_collection_content_forbidden_for_anonymous_and_plain_user(client, app, test_paths) -> None:
    (test_paths['nsa_root'] / 'secret.html').write_text('<html><body>secret</body></html>', encoding='utf-8')
    params = {'path': 'secret.html'}

    assert client.get('/api/v1/collections/nsa/content/html', params=params).status_code == 403

    _create_user(app, 'plain')
    _login(client, 'plain')
    assert client.get('/api/v1/collections/nsa/content/html', params=params).status_code == 403


@pytest.mark.parametrize(
    ('username', 'kwargs'),
    [
        ('admin', {}),
        ('nsa-perm', {'permission': 'collections.nsa.read'}),
        ('nsa-grant', {'grant': True}),
    ],
)
def test_nsa_collection_content_allowed_for_authorized_users(client, app, test_paths, username, kwargs) -> None:
    (test_paths['nsa_root'] / 'secret.html').write_text('<html><body>NSA_SECRET</body></html>', encoding='utf-8')
    if username != 'admin':
        _create_user(app, username, **kwargs)
    _login(client, username)

    response = client.get('/api/v1/collections/nsa/content/html', params={'path': 'secret.html'})

    assert response.status_code == 200
    assert 'NSA_SECRET' in response.json()['content_html']


@pytest.mark.parametrize('collection', ['document', 'civil'])
def test_collection_content_404_when_missing(client, collection) -> None:
    response = client.get(
        f'/api/v1/collections/{collection}/content/html',
        params={'path': '없는문서.html'},
    )

    assert response.status_code == 404


def test_collection_unknown_returns_404_before_filesystem_access(client) -> None:
    list_response = client.get('/api/v1/collections/secrets/list')
    content_response = client.get('/api/v1/collections/secrets/content/html', params={'path': 'x.html'})

    assert list_response.status_code == 404
    assert content_response.status_code == 404


@pytest.mark.parametrize('collection', ['document', 'civil'])
def test_collection_content_rejects_path_traversal(client, collection) -> None:
    response = client.get(
        f'/api/v1/collections/{collection}/content/html',
        params={'path': '../../secret.html'},
    )

    assert response.status_code == 400


@pytest.mark.parametrize('path', ['notes.txt', 'draft_debug.html'])
def test_collection_content_404_for_non_html_or_debug(client, test_paths, path) -> None:
    (test_paths['document_root'] / 'notes.txt').write_text('plain', encoding='utf-8')
    (test_paths['document_root'] / 'draft_debug.html').write_text('<html>debug</html>', encoding='utf-8')

    response = client.get('/api/v1/collections/document/content/html', params={'path': path})

    assert response.status_code == 404


@pytest.mark.parametrize(
    ('collection', 'root_key'),
    [('document', 'document_root'), ('civil', 'civil_aircraft_root')],
)
def test_collection_download_returns_original_html_attachment(client, test_paths, collection, root_key) -> None:
    (test_paths[root_key] / '항공').mkdir(parents=True)
    (test_paths[root_key] / '항공' / '상용기_스펙.html').write_text(
        '<html><body><script>window.__raw=1</script><p>원본</p></body></html>',
        encoding='utf-8',
    )

    response = client.get(
        f'/api/v1/collections/{collection}/download/html',
        params={'path': '항공/상용기_스펙.html'},
    )

    assert response.status_code == 200
    assert response.headers['content-type'].startswith('text/html')
    assert 'attachment' in response.headers['content-disposition']
    assert 'filename*=' in response.headers['content-disposition']
    assert 'window.__raw=1' in response.text


def test_nsa_collection_download_forbidden_for_anonymous_and_plain_user(client, app, test_paths) -> None:
    (test_paths['nsa_root'] / 'secret.html').write_text('<html><body>raw secret</body></html>', encoding='utf-8')
    params = {'path': 'secret.html'}

    assert client.get('/api/v1/collections/nsa/download/html', params=params).status_code == 403

    _create_user(app, 'plain')
    _login(client, 'plain')
    assert client.get('/api/v1/collections/nsa/download/html', params=params).status_code == 403


@pytest.mark.parametrize(
    ('username', 'kwargs'),
    [
        ('admin', {}),
        ('nsa-perm', {'permission': 'collections.nsa.read'}),
        ('nsa-grant', {'grant': True}),
    ],
)
def test_nsa_collection_download_allowed_for_authorized_users(client, app, test_paths, username, kwargs) -> None:
    (test_paths['nsa_root'] / 'secret.html').write_text('<html><body>NSA_RAW</body></html>', encoding='utf-8')
    if username != 'admin':
        _create_user(app, username, **kwargs)
    _login(client, username)

    response = client.get('/api/v1/collections/nsa/download/html', params={'path': 'secret.html'})

    assert response.status_code == 200
    assert 'NSA_RAW' in response.text


@pytest.mark.parametrize('collection', ['document', 'civil'])
def test_collection_download_rejects_path_traversal(client, collection) -> None:
    response = client.get(
        f'/api/v1/collections/{collection}/download/html',
        params={'path': '../../secret.html'},
    )

    assert response.status_code == 400


@pytest.mark.parametrize('path', ['notes.txt', 'draft_debug.html'])
def test_collection_download_404_for_non_html_or_debug(client, test_paths, path) -> None:
    (test_paths['document_root'] / 'notes.txt').write_text('plain', encoding='utf-8')
    (test_paths['document_root'] / 'draft_debug.html').write_text('<html>debug</html>', encoding='utf-8')

    response = client.get('/api/v1/collections/document/download/html', params={'path': path})

    assert response.status_code == 404


def test_collection_search_defaults_to_document_and_civil_and_returns_navigation(client, test_paths) -> None:
    (test_paths['document_root'] / '항공').mkdir(parents=True)
    (test_paths['document_root'] / '항공' / '정비.html').write_text(
        '<html><body><h1>정비 문서</h1><p>UNIQUEAIRFRAME 점검 절차</p></body></html>',
        encoding='utf-8',
    )
    (test_paths['civil_aircraft_root'] / '민항.html').write_text(
        '<html><body>UNIQUEAIRFRAME 민항 카탈로그</body></html>',
        encoding='utf-8',
    )
    (test_paths['nsa_root'] / '기밀.html').write_text(
        '<html><body>UNIQUEAIRFRAME NSA 문서</body></html>',
        encoding='utf-8',
    )

    response = client.get('/api/v1/collections/search', params={'q': 'UNIQUEAIRFRAME'})

    assert response.status_code == 200
    payload = response.json()
    assert payload['degraded'] is False
    assert payload['collections'] == ['document', 'civil']
    result_paths = {(item['collection'], item['path']) for item in payload['results']}
    assert ('document', '항공/정비.html') in result_paths
    assert ('civil', '민항.html') in result_paths
    assert not any(item['collection'] == 'nsa' for item in payload['results'])
    document_result = next(item for item in payload['results'] if item['collection'] == 'document')
    assert document_result['navigation_url'] == '/documents?path=%ED%95%AD%EA%B3%B5%2F%EC%A0%95%EB%B9%84.html'
    assert 'UNIQUEAIRFRAME' in document_result['snippet']


def test_collection_search_explicit_nsa_scope_filters_nsa_for_anonymous(client, test_paths) -> None:
    (test_paths['nsa_root'] / '분석.html').write_text(
        '<html><body>NsaOnlyToken 분석 내용</body></html>',
        encoding='utf-8',
    )

    response = client.get('/api/v1/collections/search', params={'q': 'NsaOnlyToken', 'collections': 'nsa'})

    assert response.status_code == 200
    payload = response.json()
    assert payload['collections'] == []
    assert payload['results'] == []


def test_collection_search_explicit_nsa_scope_filters_nsa_for_plain_user(client, app, test_paths) -> None:
    (test_paths['nsa_root'] / '분석.html').write_text(
        '<html><body>NsaOnlyToken 분석 내용</body></html>',
        encoding='utf-8',
    )
    _create_user(app, 'plain')
    _login(client, 'plain')

    response = client.get('/api/v1/collections/search', params={'q': 'NsaOnlyToken', 'collections': 'nsa'})

    assert response.status_code == 200
    payload = response.json()
    assert payload['collections'] == []
    assert payload['results'] == []


@pytest.mark.parametrize(
    ('username', 'kwargs'),
    [
        ('admin', {}),
        ('nsa-perm', {'permission': 'collections.nsa.read'}),
        ('nsa-grant', {'grant': True}),
    ],
)
def test_collection_search_explicit_nsa_scope_returns_nsa_navigation_for_authorized_users(client, app, test_paths, username, kwargs) -> None:
    (test_paths['nsa_root'] / '분석.html').write_text(
        '<html><body>NsaOnlyToken 분석 내용</body></html>',
        encoding='utf-8',
    )
    if username != 'admin':
        _create_user(app, username, **kwargs)
    _login(client, username)

    response = client.get('/api/v1/collections/search', params={'q': 'NsaOnlyToken', 'collections': 'nsa'})

    assert response.status_code == 200
    payload = response.json()
    assert payload['collections'] == ['nsa']
    assert payload['results'][0]['collection'] == 'nsa'
    assert payload['results'][0]['navigation_url'] == '/nsa?path=%EB%B6%84%EC%84%9D.html'


def test_collection_search_preserves_collection_policy(client, test_paths) -> None:
    (test_paths['document_root'] / 'shown.html').write_text(
        '<html><body>PolicyVisibleToken</body></html>',
        encoding='utf-8',
    )
    (test_paths['document_root'] / 'hidden_debug.html').write_text(
        '<html><body>PolicyHiddenToken</body></html>',
        encoding='utf-8',
    )
    (test_paths['document_root'] / 'plain.txt').write_text('PolicyHiddenToken', encoding='utf-8')

    visible = client.get('/api/v1/collections/search', params={'q': 'PolicyVisibleToken'})
    hidden = client.get('/api/v1/collections/search', params={'q': 'PolicyHiddenToken'})

    assert visible.status_code == 200
    assert visible.json()['results'][0]['path'] == 'shown.html'
    assert hidden.status_code == 200
    assert hidden.json()['results'] == []


def test_collection_search_rejects_unknown_collection(client) -> None:
    response = client.get('/api/v1/collections/search', params={'q': 'anything', 'collections': 'document,secrets'})

    assert response.status_code == 404
