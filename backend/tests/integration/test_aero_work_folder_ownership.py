"""Aero Work 지식폴더가 사용자별로 완전히 격리되는지 검증한다."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.modules.aero_work.api as aero_api
from app.core.security import hash_password
from app.modules.aero_work.taxonomy_service import _indexed_files
from app.modules.auth.repositories import UserRepository
from app.modules.aero_work.models import AeroWorkTaskCategory, AeroWorkTaskCategoryFile, KnowledgeFile


class _FakeEmbedder:
    model = 'fake-embed'

    def embed_one(self, text: str) -> list[float]:
        return [float(text.lower().count('secret'))]

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_one(text) for text in texts]


@pytest.fixture()
def fake_embedder(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(aero_api, 'build_embedder', lambda _settings, _db: _FakeEmbedder())


@pytest.fixture()
def second_user_client(app) -> TestClient:
    with app.state.db.session() as session:
        UserRepository(session).create(
            username='second-user', password_hash=hash_password('password'), role='user'
        )
    client = TestClient(app)
    response = client.post('/api/v1/auth/login', json={'username': 'second-user', 'password': 'password'})
    assert response.status_code == 200
    client.headers.update({'x-csrf-token': response.json()['csrf_token']})
    return client


def test_knowledge_folder_ownership_isolation(
    app, csrf_client, second_user_client: TestClient, fake_embedder, tmp_path: Path
) -> None:
    root = tmp_path / 'shared-kb'
    root.mkdir()
    (root / 'admin-only.md').write_text('secret admin-only knowledge', encoding='utf-8')

    created = csrf_client.post(
        '/api/v1/aero-work/knowledge/folders', json={'name': '관리자', 'path': str(root)}
    )
    assert created.status_code == 201, created.text
    folder_id = created.json()['id']
    assert csrf_client.post(
        f'/api/v1/aero-work/knowledge/folders/{folder_id}/reindex?inline=true'
    ).status_code == 200

    assert second_user_client.get('/api/v1/aero-work/knowledge/folders').json()['folders'] == []
    assert second_user_client.post(
        f'/api/v1/aero-work/knowledge/folders/{folder_id}/reindex?inline=true'
    ).status_code == 404
    assert second_user_client.delete(f'/api/v1/aero-work/knowledge/folders/{folder_id}').status_code == 404
    assert second_user_client.post(
        '/api/v1/aero-work/knowledge/search', json={'query': 'secret', 'folder_id': folder_id}
    ).json()['hits'] == []
    assert second_user_client.get(f'/api/v1/aero-work/knowledge/wiki?folder_id={folder_id}').json()['families'] == []

    same_path = second_user_client.post(
        '/api/v1/aero-work/knowledge/folders', json={'name': '두번째 사용자', 'path': str(root)}
    )
    assert same_path.status_code in (400, 409), same_path.text
    assert same_path.json()['detail'] == '이 경로는 이미 등록되어 있습니다(다른 사용자 포함).'

    with app.state.db.session() as session:
        admin_files, _ = _indexed_files(session, 1)
        second_files, _ = _indexed_files(session, 2)
    assert [file_row['rel_path'] for file_row in admin_files] == ['admin-only.md']
    assert second_files == []


def test_taxonomy_listing_excludes_other_owners_mapped_file(
    app, csrf_client, second_user_client: TestClient, fake_embedder, tmp_path: Path
) -> None:
    root = tmp_path / 'admin-kb'
    root.mkdir()
    (root / 'admin-only.md').write_text('secret admin-only knowledge', encoding='utf-8')

    created = csrf_client.post(
        '/api/v1/aero-work/knowledge/folders', json={'name': '관리자', 'path': str(root)}
    )
    assert created.status_code == 201, created.text
    folder_id = created.json()['id']
    assert csrf_client.post(
        f'/api/v1/aero-work/knowledge/folders/{folder_id}/reindex?inline=true'
    ).status_code == 200

    with app.state.db.session() as session:
        file_row = session.query(KnowledgeFile).filter_by(folder_id=folder_id).one()
        category = AeroWorkTaskCategory(user_id=2, name='두번째 사용자 분류', description='', sort_order=0)
        session.add(category)
        session.flush()
        session.add(AeroWorkTaskCategoryFile(category_id=category.id, file_id=file_row.id))

    listing = second_user_client.get('/api/v1/aero-work/taxonomy')
    assert listing.status_code == 200, listing.text
    categories = listing.json()['categories']
    assert len(categories) == 1
    assert categories[0] == {
        'id': categories[0]['id'],
        'name': '두번째 사용자 분류',
        'description': '',
        'sort_order': 0,
        'files': [],
    }
