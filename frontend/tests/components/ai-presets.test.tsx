import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';

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

beforeEach(() => {
  mocks.fetchAiStatus.mockResolvedValue({
    enabled: true, base_url: '', model: 'gemma4:12b', reachable: true, model_available: true, status: 'ok', detail: null,
  });
  mocks.fetchCollectionSearch.mockResolvedValue({ results: [], degraded: false, collections: ['document', 'civil'] });
  mockStreamResolves(mocks.streamAiChat, { model: 'gemma4:12b', message: { role: 'assistant', content: 'ok' }, citations: [] });
  mocks.listAiConversations.mockResolvedValue({ conversations: [] });
});

afterEach(() => {
  vi.restoreAllMocks();
  Object.values(mocks).forEach((m) => m.mockReset());
});

test('renders report-review prompt presets', async () => {
  render(<AiChatWorkspace />);
  const presets = await screen.findByTestId('ai-presets');
  for (const label of ['요약', '보고서 검토', '위험 식별', '비교']) {
    expect(presets.querySelector('button')).not.toBeNull();
    expect(screen.getByRole('button', { name: label })).toBeInTheDocument();
  }
});

test('clicking a preset injects its standard prompt into the input', async () => {
  render(<AiChatWorkspace />);
  await screen.findByTestId('ai-presets');
  fireEvent.click(screen.getByRole('button', { name: '위험 식별' }));
  const input = screen.getByTestId('ai-chat-input') as HTMLTextAreaElement;
  expect(input.value).toContain('위험 요소');
});
