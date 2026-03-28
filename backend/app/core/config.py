from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    app_name: str = 'AeroOne Newsletter Platform'
    app_env: Literal['development', 'test', 'production'] = 'development'
    backend_port: int = 8000
    frontend_port: int = 3000
    database_url: str = 'sqlite:///./backend/data/aeroone.db'
    jwt_secret_key: str = 'change-me'
    access_token_ttl_minutes: int = 30
    admin_session_cookie_name: str = 'admin_session'
    admin_username: str = 'admin'
    admin_password: str = 'change-me'
    newsletter_import_root_container: str = './Newsletter/output'
    storage_root: str = './storage'
    thumbnails_dir_name: str = 'thumbnails'
    attachments_dir_name: str = 'attachments'
    markdown_dir_name: str = 'markdown'
    csrf_cookie_name: str = 'csrf_token'
    cors_origins: str = 'http://localhost:3000'

    @property
    def import_root(self) -> Path:
        return Path(self.newsletter_import_root_container).resolve()

    @property
    def managed_storage_root(self) -> Path:
        return Path(self.storage_root).resolve()

    @property
    def storage_root_path(self) -> Path:
        return self.managed_storage_root

    @property
    def thumbnails_root(self) -> Path:
        return (self.managed_storage_root / self.thumbnails_dir_name).resolve()

    @property
    def markdown_root(self) -> Path:
        return (self.managed_storage_root / self.markdown_dir_name / 'newsletters').resolve()

    @property
    def attachments_root(self) -> Path:
        return (self.managed_storage_root / self.attachments_dir_name).resolve()

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(',') if origin.strip()]

    @property
    def sqlite_path(self) -> Path | None:
        prefix = 'sqlite:///'
        if self.database_url.startswith(prefix):
            raw = self.database_url[len(prefix):]
            return Path(raw).resolve()
        return None

    def ensure_directories(self) -> None:
        for path in [self.managed_storage_root, self.thumbnails_root, self.markdown_root, self.attachments_root]:
            path.mkdir(parents=True, exist_ok=True)
        if self.sqlite_path is not None:
            self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def reset_settings_cache() -> None:
    get_settings.cache_clear()


def ensure_runtime_directories(settings: Settings | None = None) -> None:
    (settings or get_settings()).ensure_directories()
