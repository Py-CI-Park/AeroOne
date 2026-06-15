import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import { AiChatWorkspace } from '@/components/ai/ai-chat-workspace';

const mocks = vi.hoisted(() => ({
  fetchAiStatus: vi.fn(),
  fetchCollectionSearch: vi.fn(),
  sendAiChat: vi.fn(),
  listAiConversations: vi.fn(),
  getAiConversation: vi.fn(),
  deleteAiConversation: vi.fn(),
  updateAiConversation: vi.fn(),
}));

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return { ...actual, ...mocks };
});

const SUMMARY = {
  id: 7,
  title: '엔진 정비 절차',
  is_pinned: false,
  is_archived: false,
  created_at: '2026-06-13T00:00:00Z',
  updated_at: '2026-06-13T00:00:00Z',
};

beforeEach(() => {
  mocks.fetchAiStatus.mockResolvedValue({
    enabled: true, base_url: '', model: 'gemma4:12b', reachable: true, model_available: true, status: 'ok', detail: null,
  });
  mocks.fetchCollectionSearch.mockResolvedValue({ results: [], degraded: false, collections: ['document', 'civil'] });
  mocks.sendAiChat.mockResolvedValue({ model: 'gemma4:12b', message: { role: 'assistant', content: 'AI 답변' }, citations: [] });
  mocks.listAiConversations.mockResolvedValue({ conversations: [SUMMARY] });
  mocks.getAiConversation.mockResolvedValue({
    ...SUMMARY,
    messages: [
      { id: 1, role: 'user', content: '정비 질문', seq: 0, created_at: '', citations: [] },
      { id: 2, role: 'assistant', content: '정비 답변', seq: 1, created_at: '', citations: [] },
    ],
  });
  mocks.deleteAiConversation.mockResolvedValue(undefined);
  mocks.updateAiConversation.mockResolvedValue({ ...SUMMARY, is_pinned: true });
});

afterEach(() => {
  vi.restoreAllMocks();
  Object.values(mocks).forEach((m) => m.mockReset());
});

test('renders saved conversations in the left list pane', async () => {
  render(<AiChatWorkspace />);
  const list = await screen.findByTestId('ai-conversation-list');
  expect(await screen.findByText('엔진 정비 절차')).toBeInTheDocument();
  expect(list).toBeInTheDocument();
});

test('selecting a conversation loads its messages', async () => {
  render(<AiChatWorkspace />);
  fireEvent.click(await screen.findByText('엔진 정비 절차'));
  await waitFor(() => expect(mocks.getAiConversation).toHaveBeenCalledWith(7));
  expect(await screen.findByText('정비 답변')).toBeInTheDocument();
});

test('new chat button clears the thread', async () => {
  render(<AiChatWorkspace />);
  fireEvent.click(await screen.findByText('엔진 정비 절차'));
  expect(await screen.findByText('정비 답변')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: '새 대화' }));
  await waitFor(() => expect(screen.queryByText('정비 답변')).not.toBeInTheDocument());
});

test('delete and pin invoke the conversation API', async () => {
  render(<AiChatWorkspace />);
  await screen.findByText('엔진 정비 절차');
  fireEvent.click(screen.getByRole('button', { name: '고정' }));
  await waitFor(() => expect(mocks.updateAiConversation).toHaveBeenCalledWith(7, { is_pinned: true }));
  fireEvent.click(screen.getByRole('button', { name: '삭제' }));
  await waitFor(() => expect(mocks.deleteAiConversation).toHaveBeenCalledWith(7));
});
