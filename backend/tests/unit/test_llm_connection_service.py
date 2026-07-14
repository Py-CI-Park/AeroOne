from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.base import Base
from app.modules.ai import models as ai_models  # noqa: F401 (register tables)
from app.modules.ai.llm_connection_service import LlmConnectionService
from app.modules.ai.models import LlmConnection
from app.modules.ai.schemas import LlmConnectionCreate, LlmConnectionUpdate

_SECRET = 'service-test-secret-key-0123456789ab'


@pytest.fixture()
def session():
    engine = create_engine('sqlite://')
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db:
        yield db
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def settings() -> Settings:
    return Settings(app_env='test', jwt_secret_key=_SECRET)


@pytest.fixture()
def service(session: Session, settings: Settings) -> LlmConnectionService:
    return LlmConnectionService(session, settings)


def _create(service: LlmConnectionService, **overrides) -> LlmConnection:
    payload = {
        'name': 'test conn',
        'base_url': 'https://gpt-oss.intra/v1',
        'api_key': 'sk-supersecret-01234',
        'default_model': 'gpt-oss-20b',
        'is_enabled': True,
        'is_default': False,
        'verify_tls': True,
    }
    payload.update(overrides)
    return service.create(LlmConnectionCreate(**payload))


def test_create_stores_encrypted_key_not_plaintext(service: LlmConnectionService) -> None:
    connection = _create(service)
    assert connection.api_key_encrypted != 'sk-supersecret-01234'
    assert connection.api_key_encrypted.startswith('v1:')
    assert service.decrypt_key(connection) == 'sk-supersecret-01234'


def test_create_without_key_stores_empty(service: LlmConnectionService) -> None:
    connection = _create(service, api_key='')
    assert connection.api_key_encrypted == ''
    assert service.decrypt_key(connection) == ''
    assert service.masked_key(connection) == ''


def test_masked_key_never_returns_plaintext(service: LlmConnectionService) -> None:
    connection = _create(service, api_key='sk-abcdefgh12345678')
    masked = service.masked_key(connection)
    assert masked == 'sk-...5678'
    assert 'abcdefgh' not in masked


def test_set_default_is_unique(service: LlmConnectionService) -> None:
    first = _create(service, name='a')
    second = _create(service, name='b')
    service.set_default(first.id)
    service.set_default(second.id)
    rows = service.list()
    defaults = [row for row in rows if row.is_default]
    assert len(defaults) == 1
    assert defaults[0].id == second.id


def test_get_active_priority(service: LlmConnectionService) -> None:
    assert service.get_active() is None
    first = _create(service, name='a')
    second = _create(service, name='b')
    # 기본 지정 없으면 활성 중 최소 id.
    assert service.get_active().id == first.id
    # 기본 지정되면 그 연결.
    service.set_default(second.id)
    assert service.get_active().id == second.id
    # 활성 연결이 없으면 None.
    for row in service.list():
        service.update(row.id, LlmConnectionUpdate(is_enabled=False))
    assert service.get_active() is None


def test_update_partial_keeps_key(service: LlmConnectionService) -> None:
    connection = _create(service, api_key='sk-keepme-99999999')
    encrypted_before = connection.api_key_encrypted
    updated = service.update(connection.id, LlmConnectionUpdate(name='renamed'))
    assert updated.name == 'renamed'
    assert updated.api_key_encrypted == encrypted_before  # 키 미포함 수정은 기존 키 유지.
    assert service.decrypt_key(updated) == 'sk-keepme-99999999'


def test_update_with_new_key_reencrypts(service: LlmConnectionService) -> None:
    connection = _create(service, api_key='sk-old-0000000000')
    updated = service.update(connection.id, LlmConnectionUpdate(api_key='sk-new-1111111111'))
    assert service.decrypt_key(updated) == 'sk-new-1111111111'


def test_create_with_is_default_true_sets_default(service: LlmConnectionService) -> None:
    connection = _create(service, is_default=True)
    assert service.get(connection.id).is_default is True


def test_delete_removes_connection(service: LlmConnectionService) -> None:
    connection = _create(service)
    assert service.delete(connection.id) is True
    assert service.get(connection.id) is None
    assert service.delete(9999) is False
