"""OpenAI 호환 지식폴더 임베딩 경로와 모델 공간 분리를 검증한다."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import sqlalchemy as sa
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.ai.egress_transport import EgressOutcome
from app.modules.ai.provider_config_service import ActiveCompatibleBinding
from app.modules.aero_work import embedding_client
from app.modules.aero_work.embedding_client import CompatibleEmbedder, OllamaEmbedder, build_embedder
from app.modules.aero_work.knowledge_service import KnowledgeService
from app.modules.aero_work.models import KnowledgeChunk, KnowledgeFile, KnowledgeFolder


class _ProviderService:
    def __init__(self, _db, _settings) -> None:
        pass

    def get_state(self):
        return SimpleNamespace(selected_kind='openai_compatible')

    def load_active_compatible_binding(self):
        return ActiveCompatibleBinding('http://127.0.0.1:8080/', '채팅모델', '비밀키'.encode('utf-8'))


class _VectorEmbedder:
    model = '현재-모델'
    base_url = 'http://example.invalid'

    def embed_one(self, _text: str) -> list[float]:
        return [1.0, 0.0]

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_one(text) for text in texts]


class _TrackedBytearray(bytearray):
    instances: list['_TrackedBytearray'] = []

    def __new__(cls, value=b''):
        instance = super().__new__(cls, value)
        cls.instances.append(instance)
        return instance

def test_compatible_embedder_uses_pinned_transport(monkeypatch) -> None:
    monkeypatch.setattr(embedding_client, 'ProviderConfigService', _ProviderService)
    _TrackedBytearray.instances.clear()
    monkeypatch.setattr(embedding_client, 'bytearray', _TrackedBytearray, raising=False)
    captured = {}

    def fake_embeddings(raw_url, **kwargs):
        captured['raw_url'] = raw_url
        captured.update(kwargs)
        return EgressOutcome(True, None, 200, 1, {'data': [{'embedding': [1, 2.5]}]})

    monkeypatch.setattr(embedding_client.egress_transport, 'embeddings', fake_embeddings)
    embedder = CompatibleEmbedder(Settings(app_env='test'), object())

    assert embedder.base_url == 'http://127.0.0.1:8080/'
    assert embedder.model == 'text-embedding-3-small'
    assert embedder.embed_one('문서') == [1.0, 2.5]
    assert captured['raw_url'] == embedder.base_url
    assert captured['model'] == embedder.model
    assert captured['api_key'] == '비밀키'
    assert _TrackedBytearray.instances
    assert all(not any(secret) for secret in _TrackedBytearray.instances)


def test_build_embedder_respects_admin_selection_and_default(monkeypatch) -> None:
    monkeypatch.setattr(embedding_client, 'ProviderConfigService', _ProviderService)
    settings = Settings(app_env='test')
    assert isinstance(build_embedder(settings, object()), CompatibleEmbedder)
    assert isinstance(build_embedder(settings, None), OllamaEmbedder)

    class _OllamaProvider(_ProviderService):
        def get_state(self):
            return SimpleNamespace(selected_kind='ollama')

    monkeypatch.setattr(embedding_client, 'ProviderConfigService', _OllamaProvider)
    assert isinstance(build_embedder(settings, object()), OllamaEmbedder)


def test_semantic_search_excludes_other_embedding_models() -> None:
    engine = sa.create_engine('sqlite://')
    from app.db.base import Base

    Base.metadata.create_all(bind=engine, tables=[
        Base.metadata.tables['aero_work_knowledge_folders'],
        Base.metadata.tables['aero_work_knowledge_files'],
        Base.metadata.tables['aero_work_knowledge_chunks'],
    ])
    with Session(engine) as db:
        folder = KnowledgeFolder(name='지식', path='/tmp/knowledge', status='ready')
        db.add(folder)
        db.flush()
        file_row = KnowledgeFile(folder_id=folder.id, rel_path='문서.txt', signature='1')
        db.add(file_row)
        db.flush()
        db.add_all([
            KnowledgeChunk(file_id=file_row.id, chunk_index=0, content='현재 모델', embedding='[1, 0]', embed_model='현재-모델'),
            KnowledgeChunk(file_id=file_row.id, chunk_index=1, content='다른 모델', embedding='[1, 0, 0]', embed_model='다른-모델'),
        ])
        db.commit()
        hits = KnowledgeService(db, _VectorEmbedder()).search('질의')
    assert [hit['content'] for hit in hits] == ['현재 모델']


def test_0033_migration_is_single_step_and_reversible(tmp_path: Path) -> None:
    path = Path(__file__).resolve().parents[3] / 'alembic' / 'versions' / '20260720_0033_aero_work_knowledge_embed_model.py'
    spec = importlib.util.spec_from_file_location('migration_0033', path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert (module.down_revision, module.revision) == ('20260720_0032', '20260720_0033')
    engine = sa.create_engine(f'sqlite:///{tmp_path / "migration.db"}')
    with engine.begin() as connection:
        connection.execute(sa.text('CREATE TABLE aero_work_knowledge_chunks (id INTEGER PRIMARY KEY)'))
        module.op = Operations(MigrationContext.configure(connection))
        module.upgrade()
        assert 'embed_model' in sa.inspect(connection).get_columns('aero_work_knowledge_chunks')[1]['name']
        module.downgrade()
        assert [column['name'] for column in sa.inspect(connection).get_columns('aero_work_knowledge_chunks')] == ['id']
