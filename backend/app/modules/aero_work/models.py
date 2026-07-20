"""Aero Work 지식폴더 색인 모델 — 폴더/파일/청크 3층.

지정 로컬 폴더를 **복사 없이** in-place 색인한다. 파일별 시그니처(mtime+size)로 증분
동기화하고, 청크 단위 임베딩 벡터를 JSON 텍스트로 저장한다(SQLite 단일 파일 정책 정합,
수천~수만 청크 규모는 순수 Python 코사인으로 충분 — ``docs/dev_plan/aero-work-plan.md`` §2.1).

시각 컬럼은 AiConversation 선례대로 DB-side ``func.now()`` 로 채운다(SQLite naive 이슈 회피).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, false, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class KnowledgeFolder(Base):
    """색인 대상 로컬 폴더 1건."""

    __tablename__ = 'aero_work_knowledge_folders'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default='pending')
    status_detail: Mapped[str] = mapped_column(Text, nullable=False, server_default='')
    file_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default='0')
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default='0')
    last_indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    files: Mapped[list['KnowledgeFile']] = relationship(
        back_populates='folder', cascade='all, delete-orphan'
    )


class KnowledgeFile(Base):
    """폴더 안에서 색인된 파일 1건 — 시그니처로 증분 동기화 판정."""

    __tablename__ = 'aero_work_knowledge_files'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    folder_id: Mapped[int] = mapped_column(
        ForeignKey('aero_work_knowledge_folders.id', ondelete='CASCADE'), index=True, nullable=False
    )
    rel_path: Mapped[str] = mapped_column(Text, nullable=False)
    signature: Mapped[str] = mapped_column(String(80), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, server_default='')
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default='0')
    indexed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    folder: Mapped['KnowledgeFolder'] = relationship(back_populates='files')
    chunks: Mapped[list['KnowledgeChunk']] = relationship(
        back_populates='file', cascade='all, delete-orphan'
    )


class KnowledgeChunk(Base):
    """파일 본문의 청크 1개 + 임베딩 벡터(JSON float 리스트)."""

    __tablename__ = 'aero_work_knowledge_chunks'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    file_id: Mapped[int] = mapped_column(
        ForeignKey('aero_work_knowledge_files.id', ondelete='CASCADE'), index=True, nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, server_default='0')
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[str] = mapped_column(Text, nullable=False)
    embed_model: Mapped[str | None] = mapped_column(String(200), nullable=True)

    file: Mapped['KnowledgeFile'] = relationship(back_populates='chunks')


class AeroWorkEvent(Base):
    """Aero Work 개인 일정 이벤트 — 사용자별 캘린더 항목(월/주/일 조회는 기간 필터로).

    시각은 클라이언트가 준 값을 저장하며, 저장 전 서비스에서 naive(UTC 기준)로 정규화한다
    (SQLite 는 timezone 을 보존하지 못해 aware/naive 혼용 시 비교 오류가 나기 때문).
    """

    __tablename__ = 'aero_work_events'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    all_day: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())
    location: Mapped[str] = mapped_column(String(300), nullable=False, server_default='')
    notes: Mapped[str] = mapped_column(Text, nullable=False, server_default='')
    remind_before_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class AeroWorkActivity(Base):
    """Aero Work 실행기록 1건 — 사용자가 워크스페이스에서 한 행위(입력·결과 요약)를 투명하게 남긴다.

    kind 는 'knowledge.reindex' 처럼 도메인.동작 형식이며, summary/detail 은 쉬운 우리말이다.
    """

    __tablename__ = 'aero_work_activities'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    summary: Mapped[str] = mapped_column(String(400), nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False, server_default='')
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )


class AeroWorkChatMessage(Base):
    """업무대화(오케스트레이션) 교환 1건 — 발화 + 실행 결과(JSON)를 소유자 스코프로 영속화."""

    __tablename__ = 'aero_work_chat_messages'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    utterance: Mapped[str] = mapped_column(Text, nullable=False)
    session_id: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)
    results_json: Mapped[str] = mapped_column(Text, nullable=False, server_default='[]')
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )


class AeroWorkUserPref(Base):
    """사용자별 Aero Work 환경설정(LLM 프로필 등) — user_id 가 PK."""

    __tablename__ = 'aero_work_user_prefs'

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    llm_mode: Mapped[str] = mapped_column(String(20), nullable=False, server_default='default')
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class AeroWorkDocument(Base):
    """문서 최종 저장 요청 1건 — 승인형 정책(pending → approved 후에만 HWPX 다운로드)."""

    __tablename__ = 'aero_work_documents'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    format: Mapped[str] = mapped_column(String(20), nullable=False, server_default='onepage')
    body: Mapped[str] = mapped_column(Text, nullable=False, server_default='')
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default='pending')
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class AeroWorkChatSession(Base):
    """업무대화 세션 1건 — 대화 흐름을 세션 단위로 묶는다(gongmuwon 세션 중심 IA)."""

    __tablename__ = 'aero_work_chat_sessions'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False, server_default='새 세션')
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True, nullable=False
    )


class AeroWorkTaskCategory(Base):
    """마법사(§6.6) ②검토→③적용으로 확정한 업무 분류 1건 — 사용자별 분류 트리의 노드.

    ``sort_order`` 는 사용자가 확정한 순서를 그대로 보존한다(적용 시 매번 순번 재부여).
    """

    __tablename__ = 'aero_work_task_categories'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey('users.id', ondelete='CASCADE'), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default='')
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default='0')
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    files: Mapped[list['AeroWorkTaskCategoryFile']] = relationship(
        back_populates='category', cascade='all, delete-orphan'
    )


class AeroWorkTaskCategoryFile(Base):
    """업무 분류 ↔ 색인 파일 매핑(복합 PK) — 분류·파일 어느 쪽이 삭제돼도 CASCADE 로 정리.

    ``file_id`` 는 복합 PK의 후행 컬럼이라 "이 파일이 속한 분류" 단독 조회에 선두 인덱스를
    못 쓴다 — 별도 단독 인덱스를 둔다(마이그레이션 0030).
    """

    __tablename__ = 'aero_work_task_category_files'

    category_id: Mapped[int] = mapped_column(
        ForeignKey('aero_work_task_categories.id', ondelete='CASCADE'), primary_key=True
    )
    file_id: Mapped[int] = mapped_column(
        ForeignKey('aero_work_knowledge_files.id', ondelete='CASCADE'), primary_key=True, index=True
    )

    category: Mapped['AeroWorkTaskCategory'] = relationship(back_populates='files')
