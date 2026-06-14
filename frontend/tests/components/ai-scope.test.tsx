import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import { AiChatWorkspace } from '@/components/ai/ai-chat-workspace';

const mocks = vi.hoisted(() => ({
  fetchAiStatus: vi.fn(),
  fetchCollectionSearch: vi.fn(),
  sendAiChat: vi.fn(),
  listAiConversations: vi.fn(),
}));

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return { ...actual, ...mocks };
});

beforeEach(() => {
  window.localStorage.clear();
  mocks.fetchAiStatus.mockResolvedValue({
    enabled: true, base_url: '', model: 'gemma4:12b', reachable: true, model_available: true, status: 'ok', detail: null,
  });
  mocks.fetchCollectionSearch.mockResolvedValue({ results: [], degraded: false, collections: ['document', 'civil'] });
  mocks.sendAiChat.mockResolvedValue({ model: 'gemma4:12b', message: { role: 'assistant', content: 'ok' }, citations: [] });
  mocks.listAiConversations.mockResolvedValue({ conversations: [] });
});

afterEach(() => {
  vi.restoreAllMocks();
  Object.values(mocks).forEach((m) => m.mockReset());
  window.localStorage.clear();
});

async function send() {
  fireEvent.change(screen.getByTestId('ai-chat-input'), { target: { value: '질문' } });
  fireEvent.click(screen.getByRole('button', { name: '보내기' }));
  await waitFor(() => expect(mocks.sendAiChat).toHaveBeenCalled());
}

test('default scope sends document and civil collections', async () => {
  render(<AiChatWorkspace />);
  await send();
  expect(mocks.sendAiChat).toHaveBeenCalledWith(
    expect.objectContaining({ collections: ['document', 'civil'] }),
    expect.anything(),
  );
});

test('unchecking civil narrows the chat scope to document only', async () => {
  render(<AiChatWorkspace />);
  await screen.findByTestId('ai-scope');
  // Civil is toggled via its label text
  fireEvent.click(screen.getByLabelText('Civil'));
  await send();
  expect(mocks.sendAiChat).toHaveBeenCalledWith(
    expect.objectContaining({ collections: ['document'] }),
    expect.anything(),
  );
});

test('nsa option is disabled until unlocked, enabled and selectable once unlocked', async () => {
  const { unmount } = render(<AiChatWorkspace />);
  expect((screen.getByLabelText(/NSA/) as HTMLInputElement).disabled).toBe(true);
  unmount();

  window.localStorage.setItem('aeroone.collection.nsa.unlocked', '1');
  render(<AiChatWorkspace />);
  const nsa = screen.getByLabelText('NSA') as HTMLInputElement;
  expect(nsa.disabled).toBe(false);
  fireEvent.click(nsa);
  await send();
  expect(mocks.sendAiChat).toHaveBeenCalledWith(
    expect.objectContaining({ collections: ['document', 'civil', 'nsa'] }),
    expect.anything(),
  );
});
