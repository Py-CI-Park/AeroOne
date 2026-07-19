"""오케스트레이터 지식 인텐트 — 최신본 표시 + 근거 합성(주입) 단위 검증(실 LLM 없이)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.base import Base
from app.modules.aero_work import models as aero_work_models  # noqa: F401  (register tables)
from app.modules.aero_work.knowledge_service import KnowledgeService
from app.modules.aero_work.orchestrator_service import OrchestratorService

_TABLES = (
    'aero_work_knowledge_folders',
    'aero_work_knowledge_files',
    'aero_work_knowledge_chunks',
    'aero_work_events',
    'aero_work_activities',
)


class FakeEmbedder:
    model = 'fake'
    VOCAB = ('예산', '성과', '보고')

    def embed_one(self, text: str) -> list[float]:
        return [float(text.count(term)) for term in self.VOCAB]

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_one(text) for text in texts]


@pytest.fixture()
def session() -> Session:
    engine = sa.create_engine('sqlite://')
    Base.metadata.create_all(bind=engine, tables=[Base.metadata.tables[name] for name in _TABLES])
    with Session(engine) as db:
        yield db


def _settings() -> Settings:
    return Settings(app_env='test', ollama_base_url='http://127.0.0.1:11434', jwt_secret_key='x')


def test_knowledge_intent_marks_latest_and_synthesizes(session: Session, tmp_path: Path) -> None:
    root = tmp_path / 'kb'
    root.mkdir()
    (root / '예산_20260101.md').write_text('예산 편성 기준 예산 예산', encoding='utf-8')
    (root / '예산_20260715.md').write_text('예산 편성 최신 기준 예산 예산', encoding='utf-8')
    embedder = FakeEmbedder()
    knowledge = KnowledgeService(session, embedder)
    folder = knowledge.register_folder('규정', str(root))
    session.commit()
    knowledge.reindex(folder.id)
    session.commit()

    captured: dict = {}

    def fake_synth(settings, query, hits):
        captured['query'] = query
        captured['hits'] = hits
        return '예산 편성 기준은 근거에 있습니다 [근거 1]'

    orchestrator = OrchestratorService(session, _settings(), user_id=1, embedder=embedder, synthesizer=fake_synth)
    results = orchestrator.run('예산 편성 기준 찾아줘', now=datetime(2026, 7, 19, 10, 0))

    assert results[0]['kind'] == 'knowledge'
    hits = results[0]['hits']
    assert hits, '근거가 검색되어야 한다'
    latest = [hit['rel_path'] for hit in hits if hit.get('is_latest')]
    assert latest == ['예산_20260715.md']  # 최신 날짜 판본 표시
    assert results[0]['answer'] == '예산 편성 기준은 근거에 있습니다 [근거 1]'
    assert captured['hits'], '합성기에 근거가 전달되어야 한다'


def test_knowledge_no_folder_returns_gracefully(session: Session) -> None:
    orchestrator = OrchestratorService(
        session, _settings(), user_id=1, embedder=FakeEmbedder(), synthesizer=lambda s, q, h: 'x'
    )
    results = orchestrator.run('예산 편성 기준 찾아줘', now=datetime(2026, 7, 19, 10, 0))
    assert results[0]['kind'] == 'knowledge'
    assert results[0]['hits'] == []
    assert results[0]['answer'] == ''  # 근거 없으면 합성 안 함
