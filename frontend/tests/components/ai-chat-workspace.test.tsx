import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import { AiChatWorkspace } from '@/components/ai/ai-chat-workspace';

const { fetchAiStatusMock, fetchCollectionSearchMock, sendAiChatMock } = vi.hoisted(() => ({
  fetchAiStatusMock: vi.fn(),
  fetchCollectionSearchMock: vi.fn(),
  sendAiChatMock: vi.fn(),
}));

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return {
    ...actual,
    fetchAiStatus: fetchAiStatusMock,
    fetchCollectionSearch: fetchCollectionSearchMock,
    sendAiChat: sendAiChatMock,
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
  sendAiChatMock.mockResolvedValue({
    model: 'gemma4:12b',
    message: { role: 'assistant', content: 'AI 답변' },
    citations: [],
  });
});

afterEach(() => {
  vi.restoreAllMocks();
  fetchAiStatusMock.mockReset();
  fetchCollectionSearchMock.mockReset();
  sendAiChatMock.mockReset();
});

test('shows Ollama model status and sends chat with waiting indicator', async () => {
  let resolveChat: (value: unknown) => void = () => {};
  sendAiChatMock.mockReturnValue(new Promise((resolve) => { resolveChat = resolve; }));

  render(<AiChatWorkspace />);

  expect(await screen.findByTestId('ai-status')).toHaveTextContent('gemma4:12b 준비됨');
  fireEvent.change(screen.getByTestId('ai-chat-input'), { target: { value: '안녕' } });
  fireEvent.click(screen.getByRole('button', { name: '보내기' }));

  expect(screen.getByTestId('ai-pending')).toHaveTextContent('gemma4:12b 응답 생성 중');
  expect(screen.getByRole('button', { name: '응답 대기 중' })).toBeDisabled();

  resolveChat({ model: 'gemma4:12b', message: { role: 'assistant', content: '반갑습니다' }, citations: [] });
  expect(await screen.findByText('반갑습니다')).toBeInTheDocument();
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
});

test('chat with document context shows citation links', async () => {
  render(<AiChatWorkspace />);

  fireEvent.click(screen.getByLabelText('문서 검색 결과를 답변 근거로 사용(document/civil)'));
  sendAiChatMock.mockResolvedValue({
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
  await waitFor(() => expect(sendAiChatMock).toHaveBeenCalledWith(expect.objectContaining({ use_search: true, collections: ['document', 'civil'] }), expect.anything()));
  expect(citation).toHaveAttribute('href', '/reports/civil-aircraft?path=catalog.html');
});
