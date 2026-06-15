from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, selectinload

from app.modules.ai.models import AiConversation, AiMessage, AiMessageCitation


class AiConversationRepository:
    """AI 대화 영속화 저장소.

    모든 조회/수정/삭제는 ``owner_session_id`` 단독 권위로 스코프한다. ``owner_ip``
    는 저장만 하고 WHERE 절에 절대 참여시키지 않는다(공용 PC/NAT 환경에서 IP
    매칭으로 남의 대화가 노출되는 것을 막기 위함). 쿠키가 없는 요청은 호출부에서
    빈 세션으로 처리되어 빈 이력만 보게 된다.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_conversations(self, session_id: str, *, include_archived: bool = False) -> list[AiConversation]:
        stmt = select(AiConversation).where(AiConversation.owner_session_id == session_id)
        if not include_archived:
            stmt = stmt.where(AiConversation.is_archived.is_(False))
        stmt = stmt.order_by(
            AiConversation.is_pinned.desc(),
            AiConversation.updated_at.desc(),
            AiConversation.id.desc(),
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_conversation(self, session_id: str, conversation_id: int) -> AiConversation | None:
        stmt = (
            select(AiConversation)
            .where(
                AiConversation.owner_session_id == session_id,
                AiConversation.id == conversation_id,
            )
            .options(selectinload(AiConversation.messages).selectinload(AiMessage.citations))
        )
        return self.db.execute(stmt).scalars().first()

    def create_conversation(self, session_id: str, owner_ip: str | None, title: str) -> AiConversation:
        conversation = AiConversation(owner_session_id=session_id, owner_ip=owner_ip, title=title[:200])
        self.db.add(conversation)
        self.db.flush()
        return conversation

    def update_conversation(
        self,
        session_id: str,
        conversation_id: int,
        *,
        title: str | None = None,
        is_pinned: bool | None = None,
        is_archived: bool | None = None,
    ) -> AiConversation | None:
        conversation = self.db.execute(
            select(AiConversation).where(
                AiConversation.owner_session_id == session_id,
                AiConversation.id == conversation_id,
            )
        ).scalars().first()
        if conversation is None:
            return None
        if title is not None:
            conversation.title = title[:200]
        if is_pinned is not None:
            conversation.is_pinned = is_pinned
        if is_archived is not None:
            conversation.is_archived = is_archived
        self.db.flush()
        return conversation

    def delete_conversation(self, session_id: str, conversation_id: int) -> bool:
        # ORM 삭제로 cascade='all, delete-orphan' 가 파이썬에서 실행되도록 한다(SQLite
        # FK 강제 여부와 무관하게 자식 메시지/citation 이 함께 삭제됨). 운영 엔진의
        # PRAGMA foreign_keys=ON 과 함께 이중 안전.
        conversation = self.db.execute(
            select(AiConversation).where(
                AiConversation.owner_session_id == session_id,
                AiConversation.id == conversation_id,
            ).options(selectinload(AiConversation.messages))
        ).scalars().first()
        if conversation is None:
            return False
        self.db.delete(conversation)
        self.db.flush()
        return True

    def append_turn(
        self,
        conversation: AiConversation,
        *,
        user_content: str,
        assistant_content: str,
        citations: list[dict[str, object]],
    ) -> None:
        """사용자 1턴(질문)과 AI 응답(인용 포함)을 같은 대화에 추가하고 갱신 시각을 올린다."""

        base_seq = self.db.execute(
            select(func.coalesce(func.max(AiMessage.seq), -1)).where(
                AiMessage.conversation_id == conversation.id
            )
        ).scalar_one()
        user_message = AiMessage(
            conversation_id=conversation.id,
            role='user',
            content=user_content,
            seq=int(base_seq) + 1,
        )
        self.db.add(user_message)
        assistant_message = AiMessage(
            conversation_id=conversation.id,
            role='assistant',
            content=assistant_content,
            seq=int(base_seq) + 2,
        )
        self.db.add(assistant_message)
        self.db.flush()
        for citation in citations:
            self.db.add(
                AiMessageCitation(
                    message_id=assistant_message.id,
                    collection=str(citation.get('collection', '')),
                    folder=str(citation.get('folder', '') or ''),
                    name=str(citation.get('name', '') or ''),
                    path=str(citation.get('path', '')),
                    snippet=str(citation.get('snippet', '') or ''),
                    navigation_url=str(citation.get('navigation_url', '') or ''),
                )
            )
        # 자식 추가만으로는 부모 row 가 UPDATE 되지 않아 updated_at onupdate 가 안 걸린다.
        # 목록 정렬(updated_at desc)을 위해 부모 갱신 시각을 명시적으로 올린다.
        self.db.execute(
            update(AiConversation)
            .where(AiConversation.id == conversation.id)
            .values(updated_at=func.now())
        )
        self.db.flush()
