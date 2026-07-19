"""업무 분류체계 마법사 서비스 — 주입 chat·JSON 파싱·file_id 필터링·멱등 재적용 단위 검증."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.base import Base
from app.modules.aero_work import models as aero_work_models  # noqa: F401
from app.modules.aero_work.knowledge_service import KnowledgeService
from app.modules.aero_work import taxonomy_service
from app.modules.aero_work.taxonomy_service import (
    apply_categories,
    delete_category,
    list_categories,
    propose_categories,
)

_TABLES = (
    'aero_work_knowledge_folders',
    'aero_work_knowledge_files',
    'aero_work_knowledge_chunks',
    'aero_work_task_categories',
    'aero_work_task_category_files',
    'aero_work_activities',
)


class FakeEmbedder:
    model = 'fake'

    def embed_one(self, text: str) -> list[float]:
        return [1.0]

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0] for _ in texts]


@pytest.fixture()
def session() -> Session:
    engine = sa.create_engine('sqlite://')
    Base.metadata.create_all(bind=engine, tables=[Base.metadata.tables[t] for t in _TABLES])
    with Session(engine) as db:
        yield db


def _settings(**overrides) -> Settings:
    return Settings(app_env='test', jwt_secret_key='x', **overrides)


def _indexed_file_ids(session: Session, tmp_path: Path) -> list[int]:
    root = tmp_path / 'kb'
    root.mkdir()
    (root / '예산지침.md').write_text('예산 편성 기준', encoding='utf-8')
    (root / '출장규정.md').write_text('출장 여비 규정', encoding='utf-8')
    service = KnowledgeService(session, FakeEmbedder())
    folder = service.register_folder('kb', str(root))
    session.commit()
    service.reindex(folder.id)
    session.commit()
    return sorted(f.id for f in folder.files)


def test_propose_parses_valid_json_and_filters_unknown_file_ids(session: Session, tmp_path: Path) -> None:
    file_ids = _indexed_file_ids(session, tmp_path)
    real_id = file_ids[0]
    fake_id = max(file_ids) + 999

    def fake_chat(settings, db, messages):
        payload = json.dumps(
            [{'name': '예산업무', 'description': '예산 편성/집행', 'file_ids': [real_id, fake_id]}],
            ensure_ascii=False,
        )
        return payload, 'stub-model'

    candidates, model, reason, truncated = propose_categories(
        session,
        _settings(),
        user_id=1,
        organization='국방부',
        department='예산과',
        duties='예산 편성',
        chat=fake_chat,
    )
    assert model == 'stub-model'
    assert reason == 'ok'
    assert truncated is False
    assert len(candidates) == 1
    assert candidates[0]['name'] == '예산업무'
    # 실재하지 않는 file_id 는 조용히 걸러진다.
    assert candidates[0]['file_ids'] == [real_id]


def test_propose_handles_markdown_fenced_response(session: Session, tmp_path: Path) -> None:
    file_ids = _indexed_file_ids(session, tmp_path)

    def fake_chat(settings, db, messages):
        body = json.dumps([{'name': '출장업무', 'description': '출장 여비', 'file_ids': file_ids}], ensure_ascii=False)
        return f'```json\n{body}\n```', 'stub-model'

    candidates, _, reason, _ = propose_categories(
        session, _settings(), user_id=1, organization='국방부', department='총무과', duties='출장 관리', chat=fake_chat
    )
    assert reason == 'ok'
    assert candidates[0]['name'] == '출장업무'
    assert sorted(candidates[0]['file_ids']) == sorted(file_ids)


def test_propose_corrupted_response_yields_empty_candidates(session: Session, tmp_path: Path) -> None:
    _indexed_file_ids(session, tmp_path)

    def fake_chat(settings, db, messages):
        return '이건 JSON 이 아니라 그냥 산문입니다.', 'stub-model'

    candidates, model, reason, _ = propose_categories(
        session, _settings(), user_id=1, organization='국방부', department='총무과', duties='아무거나', chat=fake_chat
    )
    assert candidates == []
    assert model == 'stub-model'
    assert reason == 'parse_error'


def test_propose_non_array_json_yields_empty_candidates(session: Session, tmp_path: Path) -> None:
    _indexed_file_ids(session, tmp_path)

    def fake_chat(settings, db, messages):
        return json.dumps({'name': '이건 배열이 아님'}, ensure_ascii=False), 'stub-model'

    candidates, _, reason, _ = propose_categories(
        session, _settings(), user_id=1, organization='국방부', department='총무과', duties='아무거나', chat=fake_chat
    )
    assert candidates == []
    assert reason == 'parse_error'


def test_propose_ai_disabled_returns_empty_without_calling_chat(session: Session, tmp_path: Path) -> None:
    _indexed_file_ids(session, tmp_path)
    called = {'hit': False}

    def fake_chat(settings, db, messages):
        called['hit'] = True
        return '[]', 'stub-model'

    candidates, model, reason, _ = propose_categories(
        session, _settings(ai_features_enabled=False), user_id=1,
        organization='국방부', department='총무과', duties='아무거나', chat=fake_chat,
    )
    assert candidates == []
    assert model == ''
    assert reason == 'ai_disabled'
    assert called['hit'] is False


def test_apply_creates_categories_and_is_idempotent(session: Session, tmp_path: Path) -> None:
    file_ids = _indexed_file_ids(session, tmp_path)
    categories = [
        {'name': '예산업무', 'description': '예산 편성', 'file_ids': [file_ids[0]]},
        {'name': '출장업무', 'description': '출장 여비', 'file_ids': [file_ids[1]]},
    ]

    applied = apply_categories(session, user_id=7, categories=categories)
    session.commit()
    assert applied == 2

    rows = list_categories(session, user_id=7)
    assert [row['name'] for row in rows] == ['예산업무', '출장업무']
    assert rows[0]['files'][0]['id'] == file_ids[0]
    assert rows[0]['files'][0]['folder_name'] == 'kb'

    # 재적용해도 결과가 같다(멱등) — 기존 분류는 전량 교체된다.
    applied_again = apply_categories(session, user_id=7, categories=categories)
    session.commit()
    assert applied_again == 2
    rows_again = list_categories(session, user_id=7)
    assert [row['name'] for row in rows_again] == ['예산업무', '출장업무']
    assert len(rows_again) == 2


def test_apply_skips_blank_names_and_unknown_file_ids(session: Session, tmp_path: Path) -> None:
    file_ids = _indexed_file_ids(session, tmp_path)
    fake_id = max(file_ids) + 999
    categories = [
        {'name': '  ', 'description': '이름 없음', 'file_ids': []},
        {'name': '정상업무', 'description': '정상', 'file_ids': [file_ids[0], fake_id]},
    ]

    applied = apply_categories(session, user_id=3, categories=categories)
    session.commit()
    assert applied == 1

    rows = list_categories(session, user_id=3)
    assert len(rows) == 1
    assert rows[0]['name'] == '정상업무'
    assert rows[0]['files'] == [
        {'id': file_ids[0], 'rel_path': rows[0]['files'][0]['rel_path'], 'folder_name': 'kb', 'summary': ''}
    ]


def test_apply_replaces_other_users_categories_are_untouched(session: Session, tmp_path: Path) -> None:
    file_ids = _indexed_file_ids(session, tmp_path)
    apply_categories(session, user_id=1, categories=[{'name': 'A', 'description': '', 'file_ids': [file_ids[0]]}])
    apply_categories(session, user_id=2, categories=[{'name': 'B', 'description': '', 'file_ids': [file_ids[1]]}])
    session.commit()

    # user=1 재적용은 user=2 를 건드리지 않는다.
    apply_categories(session, user_id=1, categories=[{'name': 'A2', 'description': '', 'file_ids': []}])
    session.commit()

    assert [row['name'] for row in list_categories(session, user_id=1)] == ['A2']
    assert [row['name'] for row in list_categories(session, user_id=2)] == ['B']


def test_delete_category_is_owner_scoped(session: Session, tmp_path: Path) -> None:
    file_ids = _indexed_file_ids(session, tmp_path)
    apply_categories(session, user_id=1, categories=[{'name': 'A', 'description': '', 'file_ids': [file_ids[0]]}])
    session.commit()
    category_id = list_categories(session, user_id=1)[0]['id']

    assert delete_category(session, user_id=2, category_id=category_id) is False
    assert delete_category(session, user_id=1, category_id=category_id) is True
    session.commit()
    assert list_categories(session, user_id=1) == []
    assert delete_category(session, user_id=1, category_id=category_id) is False


def test_propose_recovers_via_bracket_span_when_answer_has_prose_wrapper(
    session: Session, tmp_path: Path
) -> None:
    """L1: 1차 JSON 파싱 실패 시 첫 '[' ~ 마지막 ']' 구간만 잘라 2차로 재시도한다."""

    file_ids = _indexed_file_ids(session, tmp_path)

    def fake_chat(settings, db, messages):
        payload = json.dumps(
            [{'name': '예산업무', 'description': '예산 편성', 'file_ids': [file_ids[0]]}], ensure_ascii=False
        )
        # 배열 앞뒤에 설명 문구가 섞여 1차 json.loads 는 실패하지만, 2차 대괄호 추출로는 살아난다.
        return f'다음과 같습니다:\n{payload}\n이상입니다.', 'stub-model'

    candidates, model, reason, _ = propose_categories(
        session, _settings(), user_id=1, organization='국방부', department='예산과', duties='예산 편성', chat=fake_chat
    )
    assert reason == 'ok'
    assert model == 'stub-model'
    assert candidates[0]['name'] == '예산업무'
    assert candidates[0]['file_ids'] == [file_ids[0]]


def test_propose_bracket_span_extraction_still_invalid_yields_parse_error(
    session: Session, tmp_path: Path
) -> None:
    _indexed_file_ids(session, tmp_path)

    def fake_chat(settings, db, messages):
        # 대괄호는 있지만 안쪽도 깨진 JSON — 2차 추출도 실패해야 한다.
        return '설명: [이건, 배열이지만, 문법이, 깨졌다 이상.', 'stub-model'

    candidates, _, reason, _ = propose_categories(
        session, _settings(), user_id=1, organization='국방부', department='예산과', duties='예산 편성', chat=fake_chat
    )
    assert candidates == []
    assert reason == 'parse_error'


def test_propose_marks_truncated_when_indexed_files_exceed_cap(
    session: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """L3: 색인 파일이 상한을 넘으면 truncated=True 를 반환한다."""

    file_ids = _indexed_file_ids(session, tmp_path)
    assert len(file_ids) == 2
    monkeypatch.setattr(taxonomy_service, '_MAX_INDEXED_FILES', 1)

    def fake_chat(settings, db, messages):
        return '[]', 'stub-model'

    _, _, _, truncated = propose_categories(
        session, _settings(), user_id=1, organization='국방부', department='예산과', duties='예산 편성', chat=fake_chat
    )
    assert truncated is True


def test_propose_not_truncated_when_indexed_files_within_cap(session: Session, tmp_path: Path) -> None:
    _indexed_file_ids(session, tmp_path)

    def fake_chat(settings, db, messages):
        return '[]', 'stub-model'

    _, _, _, truncated = propose_categories(
        session, _settings(), user_id=1, organization='국방부', department='예산과', duties='예산 편성', chat=fake_chat
    )
    assert truncated is False
