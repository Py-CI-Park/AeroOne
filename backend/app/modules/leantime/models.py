from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func, true
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LeantimeConnection(Base):
    """Leantime JSON-RPC 어댑터가 사용할 연결 등록 정보(base_url + 암호화된 api_key).

    관리자가 UI 로 등록하고, ``api_key_encrypted`` 는 ``app.modules.ai.llm_crypto`` 대칭
    암호화로만 저장한다(평문 저장·응답 반환 금지). 활성 연결은 최대 1개이며 서비스 계층의
    ``LeantimeConnectionService`` 가 유일성을 보장한다.

    시각 컬럼은 LlmConnection 선례대로 DB-side ``func.now()`` 로만 채운다(SQLite 는
    timezone 을 저장하지 못해 애플리케이션 aware datetime 을 넣으면 비교 오류가 난다).
    """

    __tablename__ = 'leantime_connections'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    api_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False, server_default='')
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=true())
    verify_tls: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=true())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
