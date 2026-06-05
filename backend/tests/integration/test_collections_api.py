from __future__ import annotations

import pytest


def test_collection_list_includes_subfolders_and_skips_debug(client, test_paths) -> None:
    root = test_paths['document_root']
    # 루트 문서 1개 + 하위 폴더(항공) 문서 1개 + _debug 1개를 떨군다.
    (root / '회사소개.html').write_text('<html><body>intro</body></html>', encoding='utf-8')
    (root / '항공').mkdir(parents=True)
    (root / '항공' / '상용기_스펙.html').write_text('<html><body>spec</body></html>', encoding='utf-8')
    (root / '항공' / 'draft_debug.html').write_text('<html>debug</html>', encoding='utf-8')

    response = client.get('/api/v1/collections/document/list')

    assert response.status_code == 200
    documents = response.json()['documents']
    # _debug.html 은 제외 → 2건. 폴더 → 이름 순 정렬(빈 폴더가 먼저).
    assert documents == [
        {'path': '회사소개.html', 'name': '회사소개', 'folder': ''},
        {'path': '항공/상용기_스펙.html', 'name': '상용기_스펙', 'folder': '항공'},
    ]


@pytest.mark.parametrize('collection', ['document', 'civil', 'nsa'])
def test_collection_list_empty_when_no_files(client, collection) -> None:
    # conftest 기본은 빈 컬렉션 루트 디렉토리 → 빈 목록(세 컬렉션 모두).
    response = client.get(f'/api/v1/collections/{collection}/list')

    assert response.status_code == 200
    assert response.json() == {'documents': []}


@pytest.mark.parametrize(
    ('collection', 'root_key'),
    [('document', 'document_root'), ('civil', 'civil_aircraft_root'), ('nsa', 'nsa_root')],
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
    # 인라인 스크립트는 보존(문서 본문 주입 JS 가 그대로 동작해야 함).
    assert 'window.__doc=1' in html
    # 외부 <link>(폰트/스타일)와 외부 절대 src 는 차단(폐쇄망 외부 요청 방지).
    assert 'cdn.example.com/x.css' not in html
    assert 'https://cdn.example.com/a.png' not in html
    # 상대 경로 리소스는 보존.
    assert 'local.png' in html
    # 뉴스레터/보고서 HTML 과 동일한 CSP 헤더.
    assert response.headers.get('content-security-policy')


@pytest.mark.parametrize('collection', ['document', 'civil', 'nsa'])
def test_collection_content_404_when_missing(client, collection) -> None:
    response = client.get(
        f'/api/v1/collections/{collection}/content/html',
        params={'path': '없는문서.html'},
    )

    assert response.status_code == 404


def test_collection_unknown_returns_404_before_filesystem_access(client) -> None:
    # 화이트리스트(document/civil/nsa) 밖 collection 은 파일시스템 접근 전에 404.
    list_response = client.get('/api/v1/collections/secrets/list')
    content_response = client.get(
        '/api/v1/collections/secrets/content/html',
        params={'path': 'x.html'},
    )

    assert list_response.status_code == 404
    assert content_response.status_code == 404


@pytest.mark.parametrize('collection', ['document', 'civil', 'nsa'])
def test_collection_content_rejects_path_traversal(client, collection) -> None:
    # 컬렉션 루트 밖(../..)을 가리키면 path-guard 가 400 으로 막는다(세 컬렉션 모두).
    response = client.get(
        f'/api/v1/collections/{collection}/content/html',
        params={'path': '../../secret.html'},
    )

    assert response.status_code == 400


@pytest.mark.parametrize('path', ['notes.txt', 'draft_debug.html'])
def test_collection_content_404_for_non_html_or_debug(client, test_paths, path) -> None:
    # .html 이 아니거나 _debug.html 이면 404(렌더 대상 아님).
    (test_paths['document_root'] / 'notes.txt').write_text('plain', encoding='utf-8')
    (test_paths['document_root'] / 'draft_debug.html').write_text('<html>debug</html>', encoding='utf-8')

    response = client.get(
        '/api/v1/collections/document/content/html',
        params={'path': path},
    )

    assert response.status_code == 404
