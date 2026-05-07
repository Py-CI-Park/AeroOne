from __future__ import annotations

import pytest

from app.core.config import Settings


_STRONG_JWT = 'a' * 64
_STRONG_ADMIN = 'A' * 16


def _make(app_env: str, **overrides) -> Settings:
    base = dict(
        app_env=app_env,
        jwt_secret_key=_STRONG_JWT,
        admin_password=_STRONG_ADMIN,
    )
    base.update(overrides)
    return Settings(**base)


def test_closed_network_rejects_default_jwt_secret() -> None:
    settings = _make('closed_network', jwt_secret_key='change-me')
    with pytest.raises(ValueError, match='JWT_SECRET_KEY'):
        settings.validate_runtime_security()


def test_closed_network_rejects_short_jwt_secret() -> None:
    settings = _make('closed_network', jwt_secret_key='short')
    with pytest.raises(ValueError, match='JWT_SECRET_KEY'):
        settings.validate_runtime_security()


def test_closed_network_rejects_default_admin_password() -> None:
    settings = _make('closed_network', admin_password='change-me')
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
    settings = _make('production', jwt_secret_key='change-me')
    with pytest.raises(ValueError, match='JWT_SECRET_KEY'):
        settings.validate_runtime_security()


def test_production_secure_cookies_on() -> None:
    settings = _make('production')
    assert settings.secure_cookies is True


def test_development_bypasses_validation() -> None:
    settings = _make('development', jwt_secret_key='change-me', admin_password='change-me')
    settings.validate_runtime_security()


def test_test_mode_bypasses_validation() -> None:
    settings = _make('test', jwt_secret_key='test-secret', admin_password='password')
    settings.validate_runtime_security()
