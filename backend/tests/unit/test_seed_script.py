from __future__ import annotations

import pytest
from sqlalchemy import select
from app.core.security import hash_password
from app.db.base import Base
from app.core.config import reset_settings_cache
from app.db.session import Database, reset_db_caches
from app.modules.newsletter.repositories.newsletter_repository import NewsletterRepository
from app.modules.auth.models import User
from app.modules.auth.repositories import UserRepository
from app.modules.auth.services import requires_password_change
from scripts.seed import main
_RETIRED_CREDENTIAL = 'change' + '-me'



def test_seed_imports_external_newsletters(test_paths, monkeypatch) -> None:
    monkeypatch.setenv('APP_ENV', 'test')
    monkeypatch.setenv('DATABASE_URL', f"sqlite:///{test_paths['db_path']}")
    monkeypatch.setenv('NEWSLETTER_IMPORT_ROOT_CONTAINER', str(test_paths['import_root']))
    monkeypatch.setenv('STORAGE_ROOT', str(test_paths['storage_root']))
    monkeypatch.setenv('JWT_SECRET_KEY', 'test-secret')
    monkeypatch.setenv('ADMIN_USERNAME', 'admin')
    monkeypatch.setenv('ADMIN_PASSWORD', 'password')
    monkeypatch.setenv('CORS_ORIGINS', 'http://localhost:3000')
    reset_settings_cache()
    reset_db_caches()

    main()

    db = Database(f"sqlite:///{test_paths['db_path']}")
    with db.session() as session:
        repository = NewsletterRepository(session)
        imported = repository.get_by_source_identifier('20260206')
        markdown = repository.get_by_source_identifier('markdown-sample-welcome')
        admin = UserRepository(session).get_by_username('admin')

    assert imported is not None
    assert markdown is not None
    assert imported.source_file_path == 'newsletter_20260206.html'
    assert {asset.asset_type.value for asset in imported.assets} == {'html', 'pdf'}
    assert admin is not None
    assert requires_password_change(admin)


@pytest.mark.parametrize(
    'admin_password',
    ['', _RETIRED_CREDENTIAL, f' {_RETIRED_CREDENTIAL.upper()} '],
    ids=['blank-bootstrap', 'retired-bootstrap', 'retired-case-variant-bootstrap'],
)
def test_seed_refuses_invalid_bootstrap_credentials_at_script_boundary(test_paths, monkeypatch, admin_password) -> None:
    monkeypatch.setenv('APP_ENV', 'test')
    monkeypatch.setenv('DATABASE_URL', f"sqlite:///{test_paths['db_path']}")
    monkeypatch.setenv('ADMIN_PASSWORD', admin_password)
    reset_settings_cache()
    reset_db_caches()

    with pytest.raises(SystemExit, match='ADMIN_PASSWORD must be set'):
        main()

    assert not test_paths['db_path'].exists()


@pytest.mark.parametrize(
    'initial_password',
    [_RETIRED_CREDENTIAL, 'current-bootstrap-password'],
    ids=['retired-predecessor', 'configured-bootstrap-predecessor'],
)
def test_seed_migrates_legacy_or_bootstrap_admin_before_any_login(test_paths, monkeypatch, initial_password) -> None:
    bootstrap_password = 'current-bootstrap-password'
    monkeypatch.setenv('APP_ENV', 'test')
    monkeypatch.setenv('DATABASE_URL', f"sqlite:///{test_paths['db_path']}")
    monkeypatch.setenv('NEWSLETTER_IMPORT_ROOT_CONTAINER', str(test_paths['import_root']))
    monkeypatch.setenv('STORAGE_ROOT', str(test_paths['storage_root']))
    monkeypatch.setenv('JWT_SECRET_KEY', 'test-secret')
    monkeypatch.setenv('ADMIN_USERNAME', 'admin')
    monkeypatch.setenv('ADMIN_PASSWORD', bootstrap_password)
    monkeypatch.setenv('CORS_ORIGINS', 'http://localhost:3000')
    reset_settings_cache()
    reset_db_caches()

    db = Database(f"sqlite:///{test_paths['db_path']}")
    Base.metadata.create_all(bind=db.engine)
    with db.session() as session:
        session.add(User(username='admin', password_hash=hash_password(initial_password), session_version=4))

    main()

    with db.session() as session:
        admin = UserRepository(session).get_by_username('admin')
    assert admin is not None
    assert admin.session_version == 5
    assert requires_password_change(admin)


@pytest.mark.parametrize('app_env', ['production', 'closed_network'])
@pytest.mark.parametrize(
    ('credential_name', 'credential_value', 'error'),
    [
        ('JWT_SECRET_KEY', 'short', 'JWT_SECRET_KEY'),
        ('ADMIN_PASSWORD', 'short', 'ADMIN_PASSWORD'),
    ],
)
def test_seed_secure_runtime_rejects_weak_credentials_before_side_effects(
    tmp_path,
    monkeypatch,
    app_env: str,
    credential_name: str,
    credential_value: str,
    error: str,
) -> None:
    db_path = tmp_path / 'existing-empty.db'
    storage_root = tmp_path / 'must-not-be-created'
    database = Database(f'sqlite:///{db_path}')
    Base.metadata.create_all(bind=database.engine)
    monkeypatch.setenv('APP_ENV', app_env)
    monkeypatch.setenv('DATABASE_URL', f'sqlite:///{db_path}')
    monkeypatch.setenv('STORAGE_ROOT', str(storage_root))
    monkeypatch.setenv('JWT_SECRET_KEY', 'j' * 64)
    monkeypatch.setenv('ADMIN_USERNAME', 'admin')
    monkeypatch.setenv('ADMIN_PASSWORD', 'A' * 16)
    monkeypatch.setenv('CORS_ORIGINS', 'https://aeroone.example')
    monkeypatch.setenv(credential_name, credential_value)
    reset_settings_cache()
    reset_db_caches()

    try:
        with pytest.raises(SystemExit, match=error):
            main()

        assert not storage_root.exists()
        with database.session() as session:
            assert session.scalar(select(User).where(User.username == 'admin')) is None
    finally:
        reset_settings_cache()
        reset_db_caches()
@pytest.mark.parametrize('app_env', ['production', 'closed_network'])
@pytest.mark.parametrize(
    'jwt_secret_key',
    [
        f' {_RETIRED_CREDENTIAL.upper()} ',
        f' {"s" * 31} ',
    ],
    ids=['padded-retired-case-variant', 'stripped-short'],
)
def test_seed_rejects_normalized_weak_jwt_before_side_effects(
    tmp_path,
    monkeypatch,
    app_env: str,
    jwt_secret_key: str,
) -> None:
    db_path = tmp_path / 'existing-empty.db'
    storage_root = tmp_path / 'must-not-be-created'
    database = Database(f'sqlite:///{db_path}')
    Base.metadata.create_all(bind=database.engine)
    monkeypatch.setenv('APP_ENV', app_env)
    monkeypatch.setenv('DATABASE_URL', f'sqlite:///{db_path}')
    monkeypatch.setenv('STORAGE_ROOT', str(storage_root))
    monkeypatch.setenv('JWT_SECRET_KEY', jwt_secret_key)
    monkeypatch.setenv('ADMIN_USERNAME', 'admin')
    monkeypatch.setenv('ADMIN_PASSWORD', 'A' * 16)
    monkeypatch.setenv('CORS_ORIGINS', 'https://aeroone.example')
    reset_settings_cache()
    reset_db_caches()

    try:
        with pytest.raises(SystemExit, match='JWT_SECRET_KEY'):
            main()

        assert not storage_root.exists()
        with database.session() as session:
            assert session.scalar(select(User).where(User.username == 'admin')) is None
    finally:
        reset_settings_cache()
        reset_db_caches()
