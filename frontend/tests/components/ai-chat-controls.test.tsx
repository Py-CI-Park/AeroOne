import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';

import { AiChatWorkspace } from '@/components/ai/ai-chat-workspace';

import { mockStreamResolves } from './ai-stream-test-utils';

const mocks = vi.hoisted(() => ({
  fetchAiStatus: vi.fn(),
  fetchCollectionSearch: vi.fn(),
  streamAiChat: vi.fn(),
  listAiConversations: vi.fn(),
  getAiConversation: vi.fn(),
  deleteAiConversation: vi.fn(),
  updateAiConversation: vi.fn(),
}));

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return { ...actual, ...mocks };
});

const writeText = vi.fn().mockResolvedValue(undefined);

beforeEach(() => {
  Object.assign(navigator, { clipboard: { writeText } });
  mocks.fetchAiStatus.mockResolvedValue({
    enabled: true, base_url: '', model: 'gemma4:12b', reachable: true, model_available: true, status: 'ok', detail: null,
  });
  mocks.fetchCollectionSearch.mockResolvedValue({ results: [], degraded: false, collections: ['document', 'civil'] });
  mockStreamResolves(mocks.streamAiChat, { model: 'gemma4:12b', message: { role: 'assistant', content: '첫 답변' }, citations: [] });
  mocks.listAiConversations.mockResolvedValue({ conversations: [] });
});

afterEach(() => {
  vi.restoreAllMocks();
  Object.values(mocks).forEach((m) => m.mockReset());
  writeText.mockClear();
});

async function sendOnce() {
  fireEvent.change(screen.getByTestId('ai-chat-input'), { target: { value: '엔진 질문' } });
  fireEvent.click(screen.getByRole('button', { name: '보내기' }));
  await screen.findByText('첫 답변');
}

test('copy button writes the message content to the clipboard', async () => {
  render(<AiChatWorkspace />);
  await sendOnce();
  const copyButtons = await screen.findAllByRole('button', { name: '메시지 복사' });
  fireEvent.click(copyButtons[copyButtons.length - 1]);
  await waitFor(() => expect(writeText).toHaveBeenCalledWith('첫 답변'));
});

test('copy button writes raw markdown instead of rendered text', async () => {
  const markdown = '# 제목\n\n- **굵게**';
  mockStreamResolves(mocks.streamAiChat, { model: 'gemma4:12b', message: { role: 'assistant', content: markdown }, citations: [] });
  render(<AiChatWorkspace />);
  fireEvent.change(screen.getByTestId('ai-chat-input'), { target: { value: '마크다운 질문' } });
  fireEvent.click(screen.getByRole('button', { name: '보내기' }));

  expect(await screen.findByRole('heading', { name: '제목' })).toBeInTheDocument();
  const copyButtons = await screen.findAllByRole('button', { name: '메시지 복사' });
  fireEvent.click(copyButtons[copyButtons.length - 1]);
  await waitFor(() => expect(writeText).toHaveBeenCalledWith(markdown));
});

test('regenerate resends the last user message without the prior assistant turn', async () => {
  render(<AiChatWorkspace />);
  await sendOnce();
  mocks.streamAiChat.mockClear();
  mockStreamResolves(mocks.streamAiChat, { model: 'gemma4:12b', message: { role: 'assistant', content: '재생성 답변' }, citations: [] });

  fireEvent.click(screen.getByRole('button', { name: '재생성' }));

  await waitFor(() => expect(mocks.streamAiChat).toHaveBeenCalledTimes(1));
  const [payload] = mocks.streamAiChat.mock.calls[0];
  expect(payload.messages).toEqual([{ role: 'user', content: '엔진 질문' }]);
  expect(await screen.findByText('재생성 답변')).toBeInTheDocument();
});

test('stop aborts the in-flight request and shows the cancel notice', async () => {
  mocks.streamAiChat.mockImplementation(
    (_payload: unknown, signal: AbortSignal | undefined) =>
      new Promise((_resolve, reject) => {
        signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')));
      }),
  );
  render(<AiChatWorkspace />);
  fireEvent.change(screen.getByTestId('ai-chat-input'), { target: { value: '긴 질문' } });
  fireEvent.click(screen.getByRole('button', { name: '보내기' }));

  const stop = await screen.findByRole('button', { name: '중지' });
  fireEvent.click(stop);

  expect(await screen.findByText(/응답을 중지했습니다/)).toBeInTheDocument();
  // 중지 후 다시 입력 가능 상태로 복귀.
  expect(await screen.findByRole('button', { name: '보내기' })).toBeInTheDocument();
});

test('stop after partial content marks the streamed message with the interrupted badge', async () => {
  let capturedHandlers: { onDelta?: (c: string) => void } = {};
  mocks.streamAiChat.mockImplementation(
    (_payload: unknown, signal: AbortSignal | undefined, handlers: typeof capturedHandlers) => {
      capturedHandlers = handlers;
      return new Promise((_resolve, reject) => {
        signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')));
      });
    },
  );
  render(<AiChatWorkspace />);
  fireEvent.change(screen.getByTestId('ai-chat-input'), { target: { value: '긴 질문' } });
  fireEvent.click(screen.getByRole('button', { name: '보내기' }));

  await waitFor(() => expect(mocks.streamAiChat).toHaveBeenCalled());
  act(() => {
    capturedHandlers.onDelta?.('부분 응답');
  });
  await screen.findByText('부분 응답');
  fireEvent.click(screen.getByRole('button', { name: '중지' }));
  await screen.findByText(/응답을 중지했습니다/);

  expect(screen.getByTestId('ai-interrupted-badge')).toHaveTextContent('중단됨');
});
