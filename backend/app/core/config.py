from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from app.core.security import PasswordCandidateError, is_retired_password, validate_password_candidate

_RETIRED_CREDENTIAL_SENTINEL = 'change' + '-me'


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    app_name: str = 'AeroOne Newsletter Platform'
    app_version: str = '1.18.0'
    app_env: Literal['development', 'test', 'production', 'closed_network'] = 'development'
    backend_port: int = 18437
    frontend_port: int = 29501
    open_notebook_port: int = 8502
    open_webui_port: int = 8080
    database_url: str = 'sqlite:///./_database/db/aeroone.db'
    jwt_secret_key: str = _RETIRED_CREDENTIAL_SENTINEL
    access_token_ttl_minutes: int = 30
    session_activity_debounce_seconds: int = 60
    connected_user_retention_days: int = 30
    office_job_retention_days: int = Field(default=30, ge=0, le=3650)
    office_job_max_jobs_per_owner: int = Field(default=100, ge=0, le=100_000)
    office_job_max_bytes_per_owner: int = Field(default=1024 * 1024 * 1024, ge=0, le=1024**4)
    office_job_min_free_disk_bytes: int = Field(default=512 * 1024 * 1024, ge=0, le=1024**4)
    office_job_quarantine_retention_days: int = Field(default=30, ge=0, le=3650)
    office_job_max_temporary_bundles: int = Field(default=10, ge=0, le=10_000)
    office_job_temporary_bundle_retention_seconds: int = Field(default=3600, ge=1, le=604_800)
    admin_session_cookie_name: str = 'admin_session'
    admin_username: str = 'admin'
    admin_password: str = ''
    newsletter_import_root_container: str = './_database/newsletter'
    civil_aircraft_root: str = './_database/civil_aircraft'
    document_root: str = './_database/document'
    nsa_root: str = './_database/nsa'
    storage_root: str = './storage'
    thumbnails_dir_name: str = 'thumbnails'
    attachments_dir_name: str = 'attachments'
    markdown_dir_name: str = 'markdown'
    backup_dir_name: str = 'admin_backups'
    csrf_cookie_name: str = 'csrf_token'
    cors_origins: str = 'http://localhost:29501'
    ai_features_enabled: bool = True
    ollama_base_url: str = 'http://127.0.0.1:11434'
    ollama_default_model: str = 'gemma4:12b'
    ollama_embed_model: str = 'nomic-embed-text'
    ai_compatible_embed_model: str = 'text-embedding-3-small'
    ollama_connect_timeout_seconds: float = 5.0
    ollama_read_timeout_seconds: float = 120.0
    ai_max_context_chars: int = 12000
    ai_persistence_enabled: bool = False
    ai_compatible_connect_timeout_seconds: float = 5.0
    ai_compatible_read_timeout_seconds: float = 60.0
    ai_compatible_max_request_bytes: int = 200_000
    ai_compatible_max_response_bytes: int = 2_000_000
    ai_compatible_max_tokens: int = 1200
    ai_compatible_allowed_hostnames: str = ''
    ai_compatible_allowed_cidrs: str = '127.0.0.1/32,::1/128'
    ai_compatible_allowed_ports: str = '443,80,8080,8000,11434,1234'

    @property
    def project_root(self) -> Path:
        return Path(__file__).resolve().parents[3]

    def _resolve_path(self, raw: str) -> Path:
        path = Path(raw)
        return path if path.is_absolute() else (self.project_root / path).resolve()

    @property
    def import_root(self) -> Path:
        return self._resolve_path(self.newsletter_import_root_container)

    @property
    def civil_aircraft_root_path(self) -> Path:
        return self._resolve_path(self.civil_aircraft_root)

    @property
    def document_root_path(self) -> Path:
        return self._resolve_path(self.document_root)

    @property
    def nsa_root_path(self) -> Path:
        return self._resolve_path(self.nsa_root)

    @property
    def managed_storage_root(self) -> Path:
        return self._resolve_path(self.storage_root)

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
    def backup_root(self) -> Path:
        return (self.managed_storage_root / self.backup_dir_name).resolve()

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(',') if origin.strip()]

    @property
    def admin_bootstrap_password(self) -> str | None:
        if not self.admin_password.strip() or is_retired_password(self.admin_password):
            return None
        return validate_password_candidate(self.admin_password, field_name='ADMIN_PASSWORD')

    def require_admin_bootstrap_password(self) -> str:
        self.validate_runtime_security(require_admin_bootstrap=True)
        password = self.admin_bootstrap_password
        assert password is not None
        return password

    @property
    def ai_compatible_egress_policy(self) -> 'EgressPolicy':
        from app.modules.ai.egress_transport import EgressPolicy

        return EgressPolicy(
            connect_timeout_seconds=self.ai_compatible_connect_timeout_seconds,
            read_timeout_seconds=self.ai_compatible_read_timeout_seconds,
            max_request_bytes=self.ai_compatible_max_request_bytes,
            max_response_bytes=self.ai_compatible_max_response_bytes,
            allow_insecure_http=self.app_env in ('development', 'test'),
        )

    @property
    def ai_compatible_peer_policy(self) -> 'PeerPolicy':
        from app.modules.ai.egress_transport import PeerPolicy

        hostnames = frozenset(item.strip().lower() for item in self.ai_compatible_allowed_hostnames.split(',') if item.strip())
        cidrs = tuple(item.strip() for item in self.ai_compatible_allowed_cidrs.split(',') if item.strip())
        try:
            ports = frozenset(int(item.strip()) for item in self.ai_compatible_allowed_ports.split(',') if item.strip())
        except ValueError:
            ports = frozenset()
        return PeerPolicy(allowed_hostnames=hostnames or None, allowed_cidrs=cidrs, allowed_ports=ports)

    @property
    def sqlite_path(self) -> Path | None:
        prefix = 'sqlite:///'
        if self.database_url.startswith(prefix):
            raw = self.database_url[len(prefix):]
            return self._resolve_path(raw)
        return None

    def ensure_directories(self) -> None:
        for path in [
            self.managed_storage_root,
            self.thumbnails_root,
            self.markdown_root,
            self.attachments_root,
            self.backup_root,
        ]:
            path.mkdir(parents=True, exist_ok=True)
        if self.sqlite_path is not None:
            self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def secure_cookies(self) -> bool:
        return self.app_env == 'production'

    def validate_runtime_security(self, *, require_admin_bootstrap: bool = False) -> None:
        secure_runtime = self.app_env in {'production', 'closed_network'}
        errors: list[str] = []
        normalized_jwt_secret = self.jwt_secret_key.strip()
        if secure_runtime and (
            not normalized_jwt_secret
            or is_retired_password(normalized_jwt_secret)
            or len(normalized_jwt_secret) < 32
        ):
            errors.append('JWT_SECRET_KEY must be set to a non-default value with at least 32 characters')
        if secure_runtime or require_admin_bootstrap:
            try:
                password = self.admin_bootstrap_password
            except PasswordCandidateError:
                password = None
            if password is None:
                if secure_runtime:
                    errors.append('ADMIN_PASSWORD must be set to a non-default value with at least 12 characters')
                else:
                    errors.append(
                        'ADMIN_PASSWORD must be set to a unique non-default value before bootstrapping the administrator'
                    )
            elif secure_runtime and len(password) < 12:
                errors.append('ADMIN_PASSWORD must be set to a non-default value with at least 12 characters')
        if errors:
            raise ValueError('; '.join(errors))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def reset_settings_cache() -> None:
    get_settings.cache_clear()


def ensure_runtime_directories(settings: Settings | None = None) -> None:
    (settings or get_settings()).ensure_directories()
