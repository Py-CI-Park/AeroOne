'use client';

import React from 'react';

import type { AiConversationSummary } from '@/lib/types';

interface AiConversationListProps {
  conversations: AiConversationSummary[];
  activeConversationId: number | null;
  includeArchived: boolean;
  onIncludeArchivedChange: (value: boolean) => void;
  listError: string;
  onNewConversation: () => void;
  onSelectConversation: (id: number) => void;
  onTogglePin: (conversation: AiConversationSummary) => void;
  onToggleArchive: (conversation: AiConversationSummary) => void;
  onDeleteConversation: (id: number) => void;
}

export function AiConversationList({
  conversations,
  activeConversationId,
  includeArchived,
  onIncludeArchivedChange,
  listError,
  onNewConversation,
  onSelectConversation,
  onTogglePin,
  onToggleArchive,
  onDeleteConversation,
}: AiConversationListProps) {
  return (
    <section
      data-testid="ai-conversation-list"
      className="flex max-h-[calc(100dvh-176px)] min-h-0 flex-col rounded-2xl border border-line-subtle bg-surface-raised p-4 shadow-sm"
    >
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 className="text-lg font-semibold text-ink-1">대화</h2>
        <button
          type="button"
          onClick={onNewConversation}
          className="rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-accent-on transition-colors hover:bg-accent-hover"
        >
          새 대화
        </button>
      </div>
      <label className="mb-3 inline-flex items-center gap-2 text-xs text-ink-2">
        <input type="checkbox" checked={includeArchived} onChange={(event) => onIncludeArchivedChange(event.target.checked)} />
        보관함 포함
      </label>
      {listError ? <p role="alert" className="mb-2 rounded bg-warn-soft px-2 py-1 text-xs text-warn">{listError}</p> : null}
      <div className="min-h-0 flex-1 overflow-y-auto pr-1">
        <div className="flex flex-col gap-1">
          {conversations.length === 0 ? (
            <p className="text-sm text-ink-3">저장된 대화가 없습니다. 영속화가 켜져 있으면 대화가 여기에 쌓입니다.</p>
          ) : null}
          {conversations.map((conversation) => (
            <div
              key={conversation.id}
              className={`group flex items-center gap-1 rounded-lg border px-2 py-1.5 text-sm ${
                conversation.id === activeConversationId
                  ? 'border-accent bg-accent-soft'
                  : 'border-line-subtle bg-surface-elevated'
              }`}
            >
              <button
                type="button"
                onClick={() => onSelectConversation(conversation.id)}
                className="min-w-0 flex-1 truncate text-left text-ink-1"
                title={conversation.title}
              >
                {conversation.is_pinned ? '📌 ' : ''}
                {conversation.title || '제목 없는 대화'}
              </button>
              <button
                type="button"
                aria-label={conversation.is_pinned ? '고정 해제' : '고정'}
                onClick={() => onTogglePin(conversation)}
                className="shrink-0 rounded px-1 text-xs text-ink-3 hover:text-ink-1"
              >
                {conversation.is_pinned ? '핀해제' : '핀'}
              </button>
              <button
                type="button"
                aria-label={conversation.is_archived ? '보관 해제' : '보관'}
                onClick={() => onToggleArchive(conversation)}
                className="shrink-0 rounded px-1 text-xs text-ink-3 hover:text-ink-1"
              >
                {conversation.is_archived ? '복원' : '보관'}
              </button>
              <button
                type="button"
                aria-label="삭제"
                onClick={() => onDeleteConversation(conversation.id)}
                className="shrink-0 rounded px-1 text-xs text-danger hover:underline"
              >
                삭제
              </button>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
