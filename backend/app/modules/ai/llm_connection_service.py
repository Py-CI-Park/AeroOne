"""LLM 연결 레지스트리 서비스 — CRUD + 활성 연결 해석 + 키 암·복호화.

키는 저장 시 ``llm_crypto.encrypt`` 로 암호화하고, 응답에는 ``mask`` 값만 노출한다.
활성 연결(``get_active``)은 office-tools 등 신규 OpenAI 호환 경로가 우선 사용하며,
없으면 호출부가 기존 Ollama env 폴백으로 내려간다(기존 AeroAI 경로는 미변경).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.ai import llm_crypto
from app.modules.ai.models import LlmConnection
from app.modules.ai.openai_client import OpenAiCompatibleClient
from app.modules.ai.schemas import LlmConnectionCreate, LlmConnectionUpdate


class LlmConnectionService:
    def __init__(self, db: Session, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    def list(self) -> list[LlmConnection]:
        return list(self.db.execute(select(LlmConnection).order_by(LlmConnection.id)).scalars().all())

    def get(self, connection_id: int) -> LlmConnection | None:
        return self.db.get(LlmConnection, connection_id)

    def create(self, payload: LlmConnectionCreate) -> LlmConnection:
        connection = LlmConnection(
            name=payload.name,
            base_url=payload.base_url,
            api_key_encrypted=self._encrypt_key(payload.api_key),
            default_model=payload.default_model,
            is_enabled=payload.is_enabled,
            is_default=False,
            verify_tls=payload.verify_tls,
        )
        self.db.add(connection)
        self.db.flush()
        if payload.is_default:
            self.set_default(connection.id)
        return connection

    def update(self, connection_id: int, payload: LlmConnectionUpdate) -> LlmConnection | None:
        connection = self.get(connection_id)
        if connection is None:
            return None
        fields = payload.model_dump(exclude_unset=True)
        make_default = fields.pop('is_default', None)
        if 'api_key' in fields:
            # api_key 필드가 오면 재암호화, 안 오면 기존 키 유지(exclude_unset).
            connection.api_key_encrypted = self._encrypt_key(fields.pop('api_key') or '')
        for field, value in fields.items():
            setattr(connection, field, value)
        self.db.flush()
        if make_default is True:
            self.set_default(connection.id)
        elif make_default is False:
            connection.is_default = False
            self.db.flush()
        return connection

    def delete(self, connection_id: int) -> bool:
        connection = self.get(connection_id)
        if connection is None:
            return False
        self.db.delete(connection)
        self.db.flush()
        return True

    def set_default(self, connection_id: int) -> LlmConnection | None:
        """대상만 기본으로 지정하고 다른 모든 행의 기본 플래그를 내린다(활성 기본 1개 유일)."""

        connection = self.get(connection_id)
        if connection is None:
            return None
        for row in self.list():
            if row.id != connection.id and row.is_default:
                row.is_default = False
        connection.is_default = True
        self.db.flush()
        return connection

    def get_active(self) -> LlmConnection | None:
        """``is_enabled AND is_default`` 우선, 없으면 활성 중 최소 id, 없으면 None."""

        enabled = [row for row in self.list() if row.is_enabled]
        for row in enabled:
            if row.is_default:
                return row
        if enabled:
            return min(enabled, key=lambda row: row.id)
        return None

    def decrypt_key(self, connection: LlmConnection) -> str:
        if not connection.api_key_encrypted:
            return ''
        return llm_crypto.decrypt(connection.api_key_encrypted, self.settings.jwt_secret_key)

    def masked_key(self, connection: LlmConnection) -> str:
        if not connection.api_key_encrypted:
            return ''
        try:
            return llm_crypto.mask(self.decrypt_key(connection))
        except ValueError:
            # 시크릿 회전 등으로 복호 불가한 레거시 토큰 — 평문을 만들 수 없으므로 완전 마스킹.
            return '****'

    def client_for(self, connection: LlmConnection) -> OpenAiCompatibleClient:
        return OpenAiCompatibleClient(
            base_url=connection.base_url,
            api_key=self.decrypt_key(connection),
            model=connection.default_model,
            verify_tls=connection.verify_tls,
            settings=self.settings,
        )

    def _encrypt_key(self, plaintext: str) -> str:
        if not plaintext:
            return ''
        return llm_crypto.encrypt(plaintext, self.settings.jwt_secret_key)
