from __future__ import annotations

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.base import Base
from app.modules.leantime import models as leantime_models  # noqa: F401 (register tables)
from app.modules.leantime.connection_service import LeantimeConnectionService
from app.modules.leantime.models import LeantimeConnection
from app.modules.leantime.schemas import LeantimeConnectionCreate, LeantimeConnectionUpdate

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
def service(session: Session, settings: Settings) -> LeantimeConnectionService:
    return LeantimeConnectionService(session, settings)


def _create(service: LeantimeConnectionService, **overrides) -> LeantimeConnection:
    payload = {
        'name': 'primary',
        'base_url': 'https://leantime.internal',
        'api_key': 'lt-supersecret-01234',
        'is_enabled': False,
        'verify_tls': True,
    }
    payload.update(overrides)
    return service.create(LeantimeConnectionCreate(**payload))


def test_create_stores_encrypted_key_not_plaintext(service: LeantimeConnectionService) -> None:
    connection = _create(service)
    assert connection.api_key_encrypted != 'lt-supersecret-01234'
    assert connection.api_key_encrypted != ''
    assert service.decrypted_key(connection) == 'lt-supersecret-01234'


def test_masked_key_never_returns_plaintext(service: LeantimeConnectionService) -> None:
    connection = _create(service, api_key='lt-abcdefgh12345678')
    masked = service.masked_key(connection)
    assert masked != 'lt-abcdefgh12345678'
    assert 'abcdefgh' not in masked


def test_masked_key_empty_when_no_key_stored(service: LeantimeConnectionService) -> None:
    connection = _create(service, api_key='')
    assert connection.api_key_encrypted == ''
    assert service.masked_key(connection) == ''


def test_update_without_api_key_preserves_stored_key(service: LeantimeConnectionService) -> None:
    connection = _create(service, api_key='lt-keepme-99999999')
    updated = service.update(connection.id, LeantimeConnectionUpdate(name='renamed'))
    assert updated is not None
    assert updated.name == 'renamed'
    assert service.decrypted_key(updated) == 'lt-keepme-99999999'


def test_rotate_key_replaces_stored_key(service: LeantimeConnectionService) -> None:
    connection = _create(service, api_key='lt-old-0000000000')
    old_encrypted = connection.api_key_encrypted
    assert service.decrypted_key(connection) == 'lt-old-0000000000'
    rotated = service.rotate_key(connection.id, 'lt-new-1111111111')
    assert rotated is not None
    assert service.decrypted_key(rotated) == 'lt-new-1111111111'
    # rotate 는 저장된 암호문을 새 키로 교체한다(같은 ORM 인스턴스라 old 스냅샷과 비교).
    assert rotated.api_key_encrypted != old_encrypted


def test_rotate_key_missing_connection_returns_none(service: LeantimeConnectionService) -> None:
    assert service.rotate_key(9999, 'lt-whatever') is None


def test_delete_removes_connection(service: LeantimeConnectionService) -> None:
    connection = _create(service)
    service.delete(connection.id)
    assert service.get(connection.id) is None


def test_delete_missing_connection_is_noop(service: LeantimeConnectionService) -> None:
    service.delete(9999)  # should not raise


def test_resolve_active_returns_single_enabled(service: LeantimeConnectionService) -> None:
    assert service.resolve_active() is None
    connection = _create(service, is_enabled=True)
    active = service.resolve_active()
    assert active is not None
    assert active.id == connection.id


def test_enabling_second_connection_disables_first(service: LeantimeConnectionService) -> None:
    first = _create(service, name='first', is_enabled=True)
    second = _create(service, name='second', is_enabled=True)

    assert service.get(first.id).is_enabled is False
    assert service.get(second.id).is_enabled is True
    active = service.resolve_active()
    assert active is not None
    assert active.id == second.id


def test_enabling_via_update_disables_others(service: LeantimeConnectionService) -> None:
    first = _create(service, name='first', is_enabled=True)
    second = _create(service, name='second', is_enabled=False)

    service.update(second.id, LeantimeConnectionUpdate(is_enabled=True))

    assert service.get(first.id).is_enabled is False
    assert service.get(second.id).is_enabled is True


def test_base_url_rejects_blank(service: LeantimeConnectionService) -> None:
    with pytest.raises(ValidationError):
        LeantimeConnectionCreate(name='x', base_url='', api_key='lt-key')


def test_base_url_rejects_non_http_scheme(service: LeantimeConnectionService) -> None:
    with pytest.raises(ValidationError):
        LeantimeConnectionCreate(name='x', base_url='ftp://leantime.internal', api_key='lt-key')


def test_base_url_update_rejects_non_http_scheme(service: LeantimeConnectionService) -> None:
    connection = _create(service)
    with pytest.raises(ValidationError):
        LeantimeConnectionUpdate(base_url='file:///etc/passwd')
    # existing stored value untouched
    assert service.get(connection.id).base_url == 'https://leantime.internal'
