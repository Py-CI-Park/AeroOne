import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import { AiChatWorkspace } from '@/components/ai/ai-chat-workspace';

const mocks = vi.hoisted(() => ({
  fetchAiStatus: vi.fn(),
  fetchCollectionSearch: vi.fn(),
  sendAiChat: vi.fn(),
  listAiConversations: vi.fn(),
  fetchClientSession: vi.fn(),
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
  // Default: authenticated non-admin with NO nsa permission -> NSA scope stays locked.
  mocks.fetchClientSession.mockResolvedValue({
    authenticated: true, role: 'user', isAdmin: false, permissions: [], resources: [],
  });
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

test('scope toggles do not silently fall back after the last active scope is clicked', async () => {
  render(<AiChatWorkspace />);
  await screen.findByTestId('ai-scope');

  fireEvent.click(screen.getByLabelText('Civil'));
  fireEvent.click(screen.getByLabelText('Document'));

  expect(screen.getByLabelText('Document')).toBeChecked();
  await send();
  expect(mocks.sendAiChat).toHaveBeenCalledWith(
    expect.objectContaining({ collections: ['document'] }),
    expect.anything(),
  );
});

test('nsa scope is disabled without permission and enabled once the session grants nsa access', async () => {
  // No nsa permission (beforeEach default) -> NSA scope disabled.
  const { unmount } = render(<AiChatWorkspace />);
  await screen.findByTestId('ai-scope');
  await waitFor(() => expect((screen.getByLabelText(/NSA/) as HTMLInputElement).disabled).toBe(true));
  unmount();

  // Session hint grants nsa read -> NSA scope enabled and selectable.
  mocks.fetchClientSession.mockResolvedValue({
    authenticated: true, role: 'user', isAdmin: false, permissions: ['collections.nsa.read'], resources: [],
  });
  render(<AiChatWorkspace />);
  await screen.findByTestId('ai-scope');
  await waitFor(() => expect((screen.getByLabelText('NSA') as HTMLInputElement).disabled).toBe(false));
  fireEvent.click(screen.getByLabelText('NSA'));
  await send();
  expect(mocks.sendAiChat).toHaveBeenCalledWith(
    expect.objectContaining({ collections: ['document', 'civil', 'nsa'] }),
    expect.anything(),
  );
});
