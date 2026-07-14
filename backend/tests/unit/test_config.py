from __future__ import annotations

import pytest

from app.core.config import Settings


_STRONG_JWT = 'a' * 64
_STRONG_ADMIN = 'A' * 16
_RETIRED_CREDENTIAL = 'change' + '-me'


def _make(app_env: str, **overrides) -> Settings:
    base = dict(
        app_env=app_env,
        jwt_secret_key=_STRONG_JWT,
        admin_password=_STRONG_ADMIN,
    )
    base.update(overrides)
    return Settings(**base)


@pytest.mark.parametrize(
    'admin_password',
    ['', '   ', _RETIRED_CREDENTIAL, f' {_RETIRED_CREDENTIAL.upper()} '],
    ids=['blank', 'whitespace', 'retired', 'retired-case-variant'],
)
def test_local_bootstrap_refuses_empty_or_sentinel_admin_password(admin_password: str) -> None:
    settings = _make('development', admin_password=admin_password)
    assert settings.admin_bootstrap_password is None
    with pytest.raises(ValueError, match='ADMIN_PASSWORD'):
        settings.require_admin_bootstrap_password()


def test_local_bootstrap_uses_explicit_admin_password() -> None:
    admin_password = 'unique-local-admin-password'
    settings = _make('development', admin_password=admin_password)
    assert settings.admin_bootstrap_password == admin_password
    assert settings.require_admin_bootstrap_password() == admin_password


def test_closed_network_rejects_default_jwt_secret() -> None:
    settings = _make('closed_network', jwt_secret_key=_RETIRED_CREDENTIAL)
    with pytest.raises(ValueError, match='JWT_SECRET_KEY'):
        settings.validate_runtime_security()


def test_closed_network_rejects_short_jwt_secret() -> None:
    settings = _make('closed_network', jwt_secret_key='short')
    with pytest.raises(ValueError, match='JWT_SECRET_KEY'):
        settings.validate_runtime_security()


def test_closed_network_rejects_default_admin_password() -> None:
    settings = _make('closed_network', admin_password=_RETIRED_CREDENTIAL)
    with pytest.raises(ValueError, match='ADMIN_PASSWORD'):
        settings.validate_runtime_security()


def test_closed_network_rejects_short_admin_password() -> None:
    settings = _make('closed_network', admin_password='short')
    with pytest.raises(ValueError, match='ADMIN_PASSWORD'):
        settings.validate_runtime_security()


def test_closed_network_passes_with_strong_secrets() -> None:
    settings = _make('closed_network')
    settings.validate_runtime_security()


def test_closed_network_secure_cookies_off() -> None:
    settings = _make('closed_network')
    assert settings.secure_cookies is False


def test_production_still_enforces_secrets() -> None:
    settings = _make('production', jwt_secret_key=_RETIRED_CREDENTIAL)
    with pytest.raises(ValueError, match='JWT_SECRET_KEY'):
        settings.validate_runtime_security()


def test_production_secure_cookies_on() -> None:
    settings = _make('production')
    assert settings.secure_cookies is True


def test_development_bypasses_validation() -> None:
    settings = _make('development', jwt_secret_key=_RETIRED_CREDENTIAL, admin_password=_RETIRED_CREDENTIAL)
    settings.validate_runtime_security()


def test_test_mode_bypasses_validation() -> None:
    settings = _make('test', jwt_secret_key='test-secret', admin_password='password')
    settings.validate_runtime_security()
    assert settings.admin_bootstrap_password == 'password'


@pytest.mark.parametrize('app_env', ['production', 'closed_network'])
@pytest.mark.parametrize(
    ('jwt_secret_key', 'admin_password', 'error'),
    [
        ('short', _STRONG_ADMIN, 'JWT_SECRET_KEY'),
        (_STRONG_JWT, 'short', 'ADMIN_PASSWORD'),
    ],
)
def test_secure_runtime_uses_canonical_validation_for_weak_credentials(
    app_env: str,
    jwt_secret_key: str,
    admin_password: str,
    error: str,
) -> None:
    settings = _make(
        app_env,
        jwt_secret_key=jwt_secret_key,
        admin_password=admin_password,
    )

    with pytest.raises(ValueError, match=error):
        settings.validate_runtime_security()
@pytest.mark.parametrize('app_env', ['production', 'closed_network'])
@pytest.mark.parametrize(
    'jwt_secret_key',
    [
        f' {_RETIRED_CREDENTIAL.upper()} ',
        f' {"s" * 31} ',
    ],
    ids=['padded-retired-case-variant', 'stripped-short'],
)
def test_secure_runtime_rejects_normalized_weak_jwt_without_changing_mode_semantics(
    app_env: str,
    jwt_secret_key: str,
) -> None:
    settings = _make(app_env, jwt_secret_key=jwt_secret_key)

    assert settings.app_env == app_env
    assert settings.secure_cookies is (app_env == 'production')
    with pytest.raises(ValueError, match='JWT_SECRET_KEY'):
        settings.validate_runtime_security()
    assert settings.app_env == app_env
    assert settings.secure_cookies is (app_env == 'production')
