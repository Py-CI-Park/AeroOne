import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import { AiChatWorkspace } from '@/components/ai/ai-chat-workspace';

const mocks = vi.hoisted(() => ({
  fetchAiStatus: vi.fn(),
  fetchCollectionSearch: vi.fn(),
  fetchCollectionContent: vi.fn(),
  sendAiChat: vi.fn(),
  listAiConversations: vi.fn(),
}));

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return { ...actual, ...mocks };
});

const CITATION = {
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
  mocks.fetchCollectionSearch.mockResolvedValue({ results: [], degraded: false, collections: ['document', 'civil'] });
  mocks.listAiConversations.mockResolvedValue({ conversations: [] });
  mocks.fetchCollectionContent.mockResolvedValue({ asset_type: 'html', content_html: '<h1>정비 본문</h1>' });
  mocks.sendAiChat.mockResolvedValue({
    model: 'gemma4:12b',
    message: { role: 'assistant', content: '근거 답변' },
    citations: [CITATION],
  });
});

afterEach(() => {
  vi.restoreAllMocks();
  Object.values(mocks).forEach((m) => m.mockReset());
});

async function chatWithCitation() {
  fireEvent.change(screen.getByTestId('ai-chat-input'), { target: { value: '문서로 답해줘' } });
  fireEvent.click(screen.getByRole('button', { name: '보내기' }));
  await screen.findByTestId('ai-citations');
}

test('citation link opens the viewer in a new tab', async () => {
  render(<AiChatWorkspace />);
  await chatWithCitation();
  const link = screen.getByRole('link', { name: /document · 항공\/정비/ });
  expect(link).toHaveAttribute('href', '/documents?path=x');
  expect(link).toHaveAttribute('target', '_blank');
  expect(link).toHaveAttribute('rel', expect.stringContaining('noopener'));
});

test('citation panel rejects unsafe navigation URLs from persisted citations', async () => {
  mocks.sendAiChat.mockResolvedValue({
    model: 'gemma4:12b',
    message: { role: 'assistant', content: '근거 답변' },
    citations: [{ ...CITATION, navigation_url: '//evil.example/path' }],
  });

  render(<AiChatWorkspace />);
  await chatWithCitation();

  expect(screen.getByText(/document · 항공\/정비/)).toBeInTheDocument();
  expect(screen.queryByRole('link', { name: /document · 항공\/정비/ })).not.toBeInTheDocument();

  fireEvent.click(screen.getByRole('button', { name: '미리보기' }));
  await screen.findByTestId('ai-citation-preview');
  expect(screen.queryByRole('link', { name: '새 탭에서 열기' })).not.toBeInTheDocument();
  expect(screen.getByText('새 탭에서 열기')).toHaveAttribute('aria-disabled', 'true');
});

test('preview loads sanitized content into the right panel', async () => {
  render(<AiChatWorkspace />);
  await chatWithCitation();
  fireEvent.click(screen.getByRole('button', { name: '미리보기' }));

  await waitFor(() => expect(mocks.fetchCollectionContent).toHaveBeenCalledWith('document', '항공/정비.html'));
  const preview = await screen.findByTestId('ai-citation-preview');
  expect(preview).toBeInTheDocument();
  const iframe = preview.querySelector('iframe');
  expect(iframe).not.toBeNull();
  expect(iframe).toHaveAttribute('sandbox', '');
  expect(iframe?.getAttribute('srcDoc') ?? iframe?.getAttribute('srcdoc')).toContain('정비 본문');
});

test('preview supports enlarged full-view mode while keeping sandbox', async () => {
  render(<AiChatWorkspace />);
  await chatWithCitation();
  fireEvent.click(screen.getByRole('button', { name: '미리보기' }));

  const preview = await screen.findByTestId('ai-citation-preview');
  const iframe = preview.querySelector('iframe');
  expect(iframe).toHaveAttribute('sandbox', '');
  expect(iframe?.className).toContain('h-[64dvh]');

  fireEvent.click(screen.getByRole('button', { name: '전체 보기' }));
  expect(screen.getByRole('button', { name: '패널로 보기' })).toBeInTheDocument();
  expect(preview.className).toContain('fixed');
  const expandedIframe = preview.querySelector('iframe');
  expect(expandedIframe).toHaveAttribute('sandbox', '');
  expect(expandedIframe?.className).toContain('flex-1');
});

test('preview can be closed', async () => {
  render(<AiChatWorkspace />);
  await chatWithCitation();
  fireEvent.click(screen.getByRole('button', { name: '미리보기' }));
  await screen.findByTestId('ai-citation-preview');
  fireEvent.click(screen.getByRole('button', { name: '닫기' }));
  await waitFor(() => expect(screen.queryByTestId('ai-citation-preview')).not.toBeInTheDocument());
});
