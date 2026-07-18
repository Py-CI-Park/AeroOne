import { vi } from 'vitest';

import type { AiChatResponse } from '@/lib/types';

// AeroAI 스트리밍 클라이언트(streamAiChat)를 테스트에서 손쉽게 흉내 내기 위한 헬퍼.
// 과거 sendAiChat(단일 응답 Promise) 테스트와 동일한 관찰 가능한 결과(assistant 텍스트,
// citations, conversation_id)를 만들어 내도록 하나의 delta 프레임 + done 프레임으로 재현한다.
export type StreamAiChatHandlers = {
  onCitations?: (citations: AiChatResponse['citations']) => void;
  onDelta?: (content: string) => void;
  onDone?: (payload: { model: string; conversation_id?: number | null; persisted?: boolean }) => void;
  onError?: (detail: string, status?: number) => void;
};

export type StreamAiChatMock = ReturnType<typeof vi.fn<
  (payload: unknown, signal: AbortSignal | undefined, handlers: StreamAiChatHandlers) => Promise<void>
>>;

export function autoStreamImplementation(response: AiChatResponse) {
  return async (
    _payload: unknown,
    _signal: AbortSignal | undefined,
    handlers: StreamAiChatHandlers,
  ) => {
    if (response.citations && response.citations.length > 0) {
      handlers.onCitations?.(response.citations);
    }
    handlers.onDelta?.(response.message.content);
    handlers.onDone?.({
      model: response.model,
      conversation_id: response.conversation_id ?? null,
      persisted: response.persisted ?? true,
    });
  };
}

/** streamAiChat 목을 sendAiChat 스타일 응답 하나로 완료되도록 설정한다. */
export function mockStreamResolves(mockFn: StreamAiChatMock, response: AiChatResponse) {
  mockFn.mockImplementation(autoStreamImplementation(response));
}
