import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import { AiChatWorkspace } from '@/components/ai/ai-chat-workspace';

import { mockStreamResolves } from './ai-stream-test-utils';

const mocks = vi.hoisted(() => ({
  fetchAiStatus: vi.fn(),
  fetchCollectionSearch: vi.fn(),
  streamAiChat: vi.fn(),
  listAiConversations: vi.fn(),
}));

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return { ...actual, ...mocks };
});

const RESULT = {
  collection: 'document',
  path: '항공/정비.html',
  name: '정비',
  folder: '항공',
  snippet: '정비 절차',
  navigation_url: '/documents?path=x',
  score: -1,
};

beforeEach(() => {
  mocks.fetchAiStatus.mockResolvedValue({
    enabled: true, base_url: '', model: 'gemma4:12b', reachable: true, model_available: true, status: 'ok', detail: null,
  });
  mocks.fetchCollectionSearch.mockResolvedValue({ results: [RESULT], degraded: false, collections: ['document', 'civil'] });
  mockStreamResolves(mocks.streamAiChat, { model: 'gemma4:12b', message: { role: 'assistant', content: '근거 답변' }, citations: [] });
  mocks.listAiConversations.mockResolvedValue({ conversations: [] });
});

afterEach(() => {
  vi.restoreAllMocks();
  Object.values(mocks).forEach((m) => m.mockReset());
});

test('selecting a search result sends it as selected_refs in the next chat', async () => {
  render(<AiChatWorkspace />);

  fireEvent.change(screen.getByTestId('ai-search-input'), { target: { value: '정비' } });
  fireEvent.click(screen.getByRole('button', { name: '검색' }));

  const checkbox = await screen.findByRole('checkbox', { name: '근거로 선택: 정비' });
  fireEvent.click(checkbox);
  expect(await screen.findByText(/선택한 문서 1건/)).toBeInTheDocument();

  fireEvent.change(screen.getByTestId('ai-chat-input'), { target: { value: '이 문서로 답해줘' } });
  fireEvent.click(screen.getByRole('button', { name: '보내기' }));

  await waitFor(() =>
    expect(mocks.streamAiChat).toHaveBeenCalledWith(
      expect.objectContaining({ selected_refs: [{ collection: 'document', path: '항공/정비.html' }] }),
      expect.anything(),
      expect.anything(),
    ),
  );
});

test('with no selection selected_refs is an empty array', async () => {
  render(<AiChatWorkspace />);
  fireEvent.change(screen.getByTestId('ai-chat-input'), { target: { value: '그냥 질문' } });
  fireEvent.click(screen.getByRole('button', { name: '보내기' }));
  await waitFor(() =>
    expect(mocks.streamAiChat).toHaveBeenCalledWith(
      expect.objectContaining({ selected_refs: [] }),
      expect.anything(),
      expect.anything(),
    ),
  );
});
