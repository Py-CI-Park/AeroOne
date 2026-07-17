'use client';

import React from 'react';

import type { AiChatMessage } from '@/lib/types';

import { MarkdownMessage } from '@/components/ai/ai-markdown';

// 스트리밍 중 표시용 로컬 확장 — 서버 계약(AiChatMessage)에는 없는 UI 전용 플래그다.
// interrupted: 중단(AbortController) 되어 미완결 상태로 로컬에만 남은 답변임을 표시한다.
export type AiLocalMessage = AiChatMessage & { interrupted?: boolean };

interface AiMessageListProps {
  messages: AiLocalMessage[];
  pending: boolean;
  onCopy: (content: string) => void;
}

export function AiMessageList({ messages, pending, onCopy }: AiMessageListProps) {
  const lastMessage = messages[messages.length - 1];
  const isStreamingAssistant = pending && lastMessage?.role === 'assistant';
  const showWaitingIndicator = pending && !isStreamingAssistant;

  return (
    <div data-testid="ai-messages" className="mb-3 flex min-h-[320px] flex-1 flex-col gap-3 overflow-y-auto overscroll-contain rounded-xl border border-line-subtle bg-surface-elevated p-3">
      {messages.length === 0 ? (
        <div className="text-sm text-ink-3">질문을 입력하면 AI 답변이 여기에 표시됩니다.</div>
      ) : null}
      {messages.map((message, index) => {
        const isLast = index === messages.length - 1;
        return (
          <div
            key={`${message.role}-${index}`}
            className={`group rounded-lg px-3 py-2 text-sm leading-7 ${message.role === 'user' ? 'ml-8 bg-accent text-accent-on' : 'mr-8 bg-surface-sunken text-ink-1'}`}
          >
            <div className="mb-1 flex items-center justify-between gap-2 text-xs opacity-70">
              <span>
                {message.role === 'user' ? '사용자' : 'AI'}
                {message.interrupted ? (
                  <span data-testid="ai-interrupted-badge" className="ml-2 rounded-full bg-warn-soft px-2 py-0.5 text-[10px] font-medium text-warn">
                    중단됨
                  </span>
                ) : null}
              </span>
              <button
                type="button"
                aria-label="메시지 복사"
                onClick={() => onCopy(message.content)}
                className="rounded px-1 text-[11px] underline-offset-2 hover:underline"
              >
                복사
              </button>
            </div>
            {message.role === 'assistant' ? (
              <>
                <MarkdownMessage content={message.content} />
                {isLast && isStreamingAssistant ? (
                  <span data-testid="ai-stream-cursor" aria-hidden className="ml-0.5 inline-block animate-pulse text-ink-2">
                    ▍
                  </span>
                ) : null}
              </>
            ) : (
              <div className="whitespace-pre-wrap">{message.content}</div>
            )}
          </div>
        );
      })}
      {showWaitingIndicator ? (
        <div data-testid="ai-pending" className="mr-8 rounded-lg bg-surface-sunken px-3 py-2 text-sm text-ink-2">
          AeroAI 응답 생성 중… 잠시 기다려 주세요.
        </div>
      ) : null}
    </div>
  );
}
