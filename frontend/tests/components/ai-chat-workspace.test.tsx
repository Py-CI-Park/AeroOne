import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';

import { AiChatWorkspace } from '@/components/ai/ai-chat-workspace';

import { mockStreamResolves } from './ai-stream-test-utils';

const {
  fetchAiStatusMock,
  fetchCollectionSearchMock,
  listAiConversationsMock,
  streamAiChatMock,
} = vi.hoisted(() => ({
  fetchAiStatusMock: vi.fn(),
  fetchCollectionSearchMock: vi.fn(),
  listAiConversationsMock: vi.fn(),
  streamAiChatMock: vi.fn(),
}));

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return {
    ...actual,
    fetchAiStatus: fetchAiStatusMock,
    fetchCollectionSearch: fetchCollectionSearchMock,
    streamAiChat: streamAiChatMock,
    listAiConversations: listAiConversationsMock,
  };
});

beforeEach(() => {
  fetchAiStatusMock.mockResolvedValue({
    enabled: true,
    base_url: 'http://127.0.0.1:11434',
    model: 'gemma4:12b',
    reachable: true,
    model_available: true,
    status: 'ok',
    detail: null,
  });
  fetchCollectionSearchMock.mockResolvedValue({ results: [], degraded: false, collections: ['document', 'civil'] });
  listAiConversationsMock.mockResolvedValue({ conversations: [] });
  mockStreamResolves(streamAiChatMock, {
    model: 'gemma4:12b',
    message: { role: 'assistant', content: 'AI 답변' },
    citations: [],
  });
});

afterEach(() => {
  vi.restoreAllMocks();
  fetchAiStatusMock.mockReset();
  fetchCollectionSearchMock.mockReset();
  streamAiChatMock.mockReset();
  listAiConversationsMock.mockReset();
});

test('shows Ollama model status and sends chat with waiting indicator', async () => {
  let capturedHandlers: { onDelta?: (c: string) => void; onDone?: (p: unknown) => void } = {};
  let resolveStream: () => void = () => {};
  streamAiChatMock.mockImplementation((_payload: unknown, _signal: AbortSignal | undefined, handlers: typeof capturedHandlers) => {
    capturedHandlers = handlers;
    return new Promise<void>((resolve) => {
      resolveStream = resolve;
    });
  });

  render(<AiChatWorkspace />);

  expect(await screen.findByTestId('ai-status')).toHaveTextContent('AeroAI 준비됨');
  fireEvent.change(screen.getByTestId('ai-chat-input'), { target: { value: '안녕' } });
  fireEvent.click(screen.getByRole('button', { name: '보내기' }));

  expect(screen.getByTestId('ai-pending')).toHaveTextContent('AeroAI 응답 생성 중');
  expect(screen.getByRole('button', { name: '응답 대기 중' })).toBeDisabled();

  act(() => {
    capturedHandlers.onDelta?.('반갑습니다');
    capturedHandlers.onDone?.({ model: 'gemma4:12b', conversation_id: null, persisted: false });
    resolveStream();
  });
  expect(await screen.findByText('반갑습니다')).toBeInTheDocument();
});

test('renders assistant markdown safely without changing raw copy source', async () => {
  mockStreamResolves(streamAiChatMock, {
    model: 'gemma4:12b',
    message: {
      role: 'assistant',
      content: '# 정비 요약\n\n- **엔진** 점검\n\n```cmd\nrun_all.bat\n```\n\n<img src=x onerror=alert(1)>\n\n[안전](/documents)\n[위험](javascript:alert)\n[프로토콜상대](//evil.example)',
    },
    citations: [],
  });

  render(<AiChatWorkspace />);
  fireEvent.change(screen.getByTestId('ai-chat-input'), { target: { value: '마크다운으로 답해줘' } });
  fireEvent.click(screen.getByRole('button', { name: '보내기' }));

  expect(await screen.findByRole('heading', { name: '정비 요약' })).toBeInTheDocument();
  expect(await screen.findByText('엔진')).toBeInTheDocument();
  expect(await screen.findByText('run_all.bat')).toBeInTheDocument();
  expect(screen.getByRole('link', { name: '안전' })).toHaveAttribute('href', '/documents');
  expect(screen.queryByRole('link', { name: '위험' })).not.toBeInTheDocument();
  expect(screen.getByTestId('ai-markdown-message')).toHaveTextContent('위험 (javascript:alert)');
  expect(screen.queryByRole('link', { name: '프로토콜상대' })).not.toBeInTheDocument();
  expect(screen.getByTestId('ai-markdown-message')).toHaveTextContent('프로토콜상대 (//evil.example)');
  expect(screen.getByTestId('ai-markdown-message')).toHaveTextContent('<img src=x onerror=alert(1)>');
  expect(screen.getByTestId('ai-markdown-message').querySelector('img')).toBeNull();
});

test('keeps AeroAI columns within the visible monitor height with internal HTML scrolling', async () => {
  render(<AiChatWorkspace />);

  await screen.findByTestId('ai-status');
  const htmlSearchPanel = screen.getByRole('heading', { name: 'HTML 본문 검색' }).closest('section');
  const workspaceGrid = htmlSearchPanel?.parentElement;
  const conversationPanel = screen.getByTestId('ai-conversation-list');
  const chatPanel = screen.getByTestId('ai-messages').closest('section');

  expect(workspaceGrid?.className).toContain('min-h-[calc(100dvh-176px)]');
  expect(conversationPanel.className).toContain('max-h-[calc(100dvh-176px)]');
  expect(chatPanel?.className).toContain('max-h-[calc(100dvh-176px)]');
  expect(htmlSearchPanel?.className).toContain('max-h-[calc(100dvh-176px)]');
  expect(htmlSearchPanel?.className).toContain('overflow-y-auto');
  expect(htmlSearchPanel?.className).toContain('overscroll-contain');
});

test('document search returns result links to viewer URLs', async () => {
  fetchCollectionSearchMock.mockResolvedValue({
    degraded: false,
    collections: ['document', 'civil'],
    results: [
      {
        collection: 'document',
        path: '항공/정비.html',
        name: '정비',
        folder: '항공',
        snippet: '정비 절차',
        navigation_url: '/documents?path=%ED%95%AD%EA%B3%B5%2F%EC%A0%95%EB%B9%84.html',
        score: -1,
      },
    ],
  });

  render(<AiChatWorkspace />);

  fireEvent.change(screen.getByTestId('ai-search-input'), { target: { value: '정비' } });
  fireEvent.click(screen.getByRole('button', { name: '검색' }));

  const link = await screen.findByRole('link', { name: /document · 항공\/정비/ });
  expect(fetchCollectionSearchMock).toHaveBeenCalledWith({ q: '정비', collections: ['document', 'civil'], limit: 20 });
  expect(link).toHaveAttribute('href', '/documents?path=%ED%95%AD%EA%B3%B5%2F%EC%A0%95%EB%B9%84.html');
  expect(link).toHaveAttribute('target', '_blank');
  expect(link).toHaveAttribute('rel', expect.stringContaining('noopener'));
});

test('document search rejects unsafe navigation URLs from API payloads', async () => {
  fetchCollectionSearchMock.mockResolvedValue({
    degraded: false,
    collections: ['document', 'civil'],
    results: [
      {
        collection: 'document',
        path: '위험.html',
        name: '위험',
        folder: '',
        snippet: 'javascript url',
        navigation_url: 'javascript:alert(1)',
        score: -1,
      },
      {
        collection: 'document',
        path: 'api.html',
        name: 'API 경로',
        folder: '',
        snippet: 'same-origin non-viewer path',
        navigation_url: '/api/frontend/collections/search',
        score: -1,
      },
      {
        collection: 'document',
        path: 'external.html',
        name: '외부 경로',
        folder: '',
        snippet: 'absolute external path',
        navigation_url: 'https://evil.example/doc.html',
        score: -1,
      },
    ],
  });

  render(<AiChatWorkspace />);

  fireEvent.change(screen.getByTestId('ai-search-input'), { target: { value: '위험' } });
  fireEvent.click(screen.getByRole('button', { name: '검색' }));

  expect(await screen.findByText(/document · 위험/)).toBeInTheDocument();
  expect(screen.queryByRole('link', { name: /document · 위험/ })).not.toBeInTheDocument();
  expect(screen.getByText(/document · API 경로/)).toBeInTheDocument();
  expect(screen.queryByRole('link', { name: /document · API 경로/ })).not.toBeInTheDocument();
  expect(screen.getByText(/document · 외부 경로/)).toBeInTheDocument();
  expect(screen.queryByRole('link', { name: /document · 외부 경로/ })).not.toBeInTheDocument();
});

test('chat with document context shows citation links', async () => {
  render(<AiChatWorkspace />);

  fireEvent.click(screen.getByLabelText('문서 검색 결과를 답변 근거로 사용(document/civil)'));
  mockStreamResolves(streamAiChatMock, {
    model: 'gemma4:12b',
    message: { role: 'assistant', content: '근거 기반 답변' },
    citations: [
      {
        collection: 'civil',
        path: 'catalog.html',
        name: 'catalog',
        folder: '',
        snippet: 'catalog snippet',
        navigation_url: '/reports/civil-aircraft?path=catalog.html',
        score: -1,
      },
    ],
  });
  fireEvent.change(screen.getByTestId('ai-chat-input'), { target: { value: '문서로 답해줘' } });
  fireEvent.click(screen.getByRole('button', { name: '보내기' }));

  const citation = await screen.findByRole('link', { name: /civil · catalog/ });
  await waitFor(() =>
    expect(streamAiChatMock).toHaveBeenCalledWith(
      expect.objectContaining({ use_search: true, collections: ['document', 'civil'] }),
      expect.anything(),
      expect.anything(),
    ),
  );
  expect(citation).toHaveAttribute('href', '/reports/civil-aircraft?path=catalog.html');
});


test('done with persist_error keeps the answer and shows a save-failure warning', async () => {
  streamAiChatMock.mockImplementation((_payload: unknown, _signal: AbortSignal | undefined, handlers: { onDelta?: (c: string) => void; onDone?: (p: unknown) => void }) => {
    handlers.onDelta?.('답변 본문');
    handlers.onDone?.({ model: 'gemma4:12b', conversation_id: null, persisted: false, persist_error: 'PersistFailed' });
    return Promise.resolve();
  });
  render(<AiChatWorkspace />);
  fireEvent.change(screen.getByTestId('ai-chat-input'), { target: { value: '질문' } });
  fireEvent.click(screen.getByRole('button', { name: '보내기' }));

  // 답변은 유지되고 저장 실패 경고만 뜬다.
  expect(await screen.findByText('답변 본문')).toBeInTheDocument();
  expect(await screen.findByRole('alert')).toHaveTextContent('대화 저장에 실패했습니다');
});
