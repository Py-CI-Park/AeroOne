"""Leantime 연결 레지스트리 서비스 — CRUD + 활성 연결 해석 + 키 암·복호화.

키는 저장 시 ``llm_crypto.encrypt`` 로 암호화하고, 응답에는 ``mask`` 값만 노출한다.
활성 연결은 최대 1개이며, 한 연결을 활성화하면 서비스 계층이 다른 모든 연결을 비활성화해
유일성을 보장한다(LlmConnectionService.set_default 와 동일한 계약).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.ai import llm_crypto
from app.modules.leantime.models import LeantimeConnection
from app.modules.leantime.schemas import LeantimeConnectionCreate, LeantimeConnectionUpdate


class LeantimeConnectionService:
    def __init__(self, db: Session, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    def list(self) -> list[LeantimeConnection]:
        return list(self.db.execute(select(LeantimeConnection).order_by(LeantimeConnection.id)).scalars().all())

    def get(self, connection_id: int) -> LeantimeConnection | None:
        return self.db.get(LeantimeConnection, connection_id)

    def create(self, payload: LeantimeConnectionCreate) -> LeantimeConnection:
        connection = LeantimeConnection(
            name=payload.name,
            base_url=payload.base_url,
            api_key_encrypted=self._encrypt_key(payload.api_key),
            is_enabled=False,
            verify_tls=payload.verify_tls,
        )
        self.db.add(connection)
        self.db.flush()
        if payload.is_enabled:
            self._enable_exclusive(connection.id)
        return connection

    def update(self, connection_id: int, payload: LeantimeConnectionUpdate) -> LeantimeConnection | None:
        connection = self.get(connection_id)
        if connection is None:
            return None
        fields = payload.model_dump(exclude_unset=True)
        make_enabled = fields.pop('is_enabled', None)
        if 'api_key' in fields:
            # api_key 필드가 오면 재암호화, 안 오면 기존 키 유지(exclude_unset).
            connection.api_key_encrypted = self._encrypt_key(fields.pop('api_key') or '')
        for field, value in fields.items():
            setattr(connection, field, value)
        self.db.flush()
        if make_enabled is True:
            self._enable_exclusive(connection.id)
        elif make_enabled is False:
            connection.is_enabled = False
            self.db.flush()
        return connection

    def delete(self, connection_id: int) -> None:
        connection = self.get(connection_id)
        if connection is None:
            return
        self.db.delete(connection)
        self.db.flush()

    def rotate_key(self, connection_id: int, new_api_key: str) -> LeantimeConnection | None:
        connection = self.get(connection_id)
        if connection is None:
            return None
        connection.api_key_encrypted = self._encrypt_key(new_api_key)
        self.db.flush()
        return connection

    def resolve_active(self) -> LeantimeConnection | None:
        """활성 연결을 돌려준다. 여러 개가 동시에 활성이면 가장 최근에 갱신된 것을 우선한다."""

        enabled = [row for row in self.list() if row.is_enabled]
        if not enabled:
            return None
        return max(enabled, key=lambda row: (row.updated_at, row.id))

    def _enable_exclusive(self, connection_id: int) -> LeantimeConnection | None:
        """대상만 활성으로 지정하고 다른 모든 행을 비활성화한다(활성 연결 1개 유일)."""

        connection = self.get(connection_id)
        if connection is None:
            return None
        for row in self.list():
            if row.id != connection.id and row.is_enabled:
                row.is_enabled = False
        connection.is_enabled = True
        self.db.flush()
        return connection

    def decrypted_key(self, connection: LeantimeConnection) -> str:
        if not connection.api_key_encrypted:
            return ''
        return llm_crypto.decrypt(connection.api_key_encrypted, self.settings.jwt_secret_key)

    def masked_key(self, connection: LeantimeConnection) -> str:
        if not connection.api_key_encrypted:
            return ''
        try:
            return llm_crypto.mask(self.decrypted_key(connection))
        except ValueError:
            # 시크릿 회전 등으로 복호 불가한 레거시 토큰 — 평문을 만들 수 없으므로 완전 마스킹.
            return '****'

    def _encrypt_key(self, plaintext: str) -> str:
        if not plaintext:
            return ''
        return llm_crypto.encrypt(plaintext, self.settings.jwt_secret_key)
