from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, false, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AiConversation(Base):
    """AI 대화 1건의 메타데이터.

    조회 권위는 ``owner_session_id`` 단독이다. ``owner_ip`` 는 감사/2단계 계정
    claim 을 위한 보조 메타 컬럼이며 조회 WHERE 에 참여하지 않는다(공용 PC/NAT
    환경에서 IP 매칭으로 남의 대화가 노출되는 것을 막기 위함). ``user_id`` 는
    2단계 계정 도입 시 claim 대상으로 미리 확보해 둔 nullable 컬럼이다.

    시각 컬럼은 read_event 선례대로 DB-side ``func.now()`` 로만 채운다. SQLite 는
    timezone 을 저장하지 못해 재로딩 시 naive 가 되므로 애플리케이션에서 aware
    datetime 을 넣으면 비교 오류가 난다.
    """

    __tablename__ = 'ai_conversations'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    owner_session_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    owner_ip: Mapped[str | None] = mapped_column(String(45), index=True, nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False, server_default='')
    is_pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    messages: Mapped[list['AiMessage']] = relationship(
        back_populates='conversation',
        cascade='all, delete-orphan',
        order_by='AiMessage.seq',
    )


class AiMessage(Base):
    __tablename__ = 'ai_messages'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey('ai_conversations.id', ondelete='CASCADE'), index=True, nullable=False
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False, server_default='0')
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    conversation: Mapped['AiConversation'] = relationship(back_populates='messages')
    citations: Mapped[list['AiMessageCitation']] = relationship(
        back_populates='message',
        cascade='all, delete-orphan',
    )


class AiMessageCitation(Base):
    __tablename__ = 'ai_message_citations'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    message_id: Mapped[int] = mapped_column(
        ForeignKey('ai_messages.id', ondelete='CASCADE'), index=True, nullable=False
    )
    collection: Mapped[str] = mapped_column(String(16), nullable=False)
    folder: Mapped[str] = mapped_column(String(500), nullable=False, server_default='')
    name: Mapped[str] = mapped_column(String(500), nullable=False, server_default='')
    path: Mapped[str] = mapped_column(String(1000), nullable=False)
    snippet: Mapped[str] = mapped_column(Text, nullable=False, server_default='')
    navigation_url: Mapped[str] = mapped_column(String(1000), nullable=False, server_default='')

    message: Mapped['AiMessage'] = relationship(back_populates='citations')
