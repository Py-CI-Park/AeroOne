import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import { WorkChatPanel } from '@/components/aero-work/work-chat-panel';

// G006 — 업무대화 오케스트레이터 첨부(AeroAI 계약 재사용) + routed_by 배지 회귀 고정.

const orchestrateAeroWork = vi.fn();
const fetchAeroWorkChatSessions = vi.fn();
const fetchAeroWorkChatHistory = vi.fn();
const deleteAeroWorkChatSession = vi.fn();
const generateAeroWorkHwpx = vi.fn();
const streamAeroWorkAnswer = vi.fn();

vi.mock('@/lib/cookies', () => ({ getCsrfCookie: () => 'csrf-test-token' }));

vi.mock('@/lib/api', () => ({
  orchestrateAeroWork: (...args: unknown[]) => orchestrateAeroWork(...args),
  fetchAeroWorkChatSessions: (...args: unknown[]) => fetchAeroWorkChatSessions(...args),
  fetchAeroWorkChatHistory: (...args: unknown[]) => fetchAeroWorkChatHistory(...args),
  deleteAeroWorkChatSession: (...args: unknown[]) => deleteAeroWorkChatSession(...args),
  generateAeroWorkHwpx: (...args: unknown[]) => generateAeroWorkHwpx(...args),
  streamAeroWorkAnswer: (...args: unknown[]) => streamAeroWorkAnswer(...args),
}));

function baseResult(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    kind: 'help',
    summary: '도움말입니다.',
    events: [],
    hits: [],
    document: null,
    feature: null,
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  fetchAeroWorkChatSessions.mockResolvedValue({ sessions: [] });
  fetchAeroWorkChatHistory.mockResolvedValue({ items: [] });
  streamAeroWorkAnswer.mockImplementation(() => Promise.resolve());
});

test('클립 버튼으로 파일을 선택하면 첨부 칩이 추가되고 제거 버튼으로 지울 수 있다', async () => {
  render(<WorkChatPanel />);
  await waitFor(() => expect(fetchAeroWorkChatSessions).toHaveBeenCalled());

  const file = new File(['첨부 본문'], 'note.md', { type: 'text/markdown' });
  const input = screen.getByLabelText('첨부 파일 선택') as HTMLInputElement;
  fireEvent.change(input, { target: { files: [file] } });

  expect(await screen.findByText('note.md')).toBeInTheDocument();

  fireEvent.click(screen.getByRole('button', { name: '첨부 제거: note.md' }));
  await waitFor(() => expect(screen.queryByText('note.md')).not.toBeInTheDocument());
});

test('클립보드 붙여넣기로도 첨부 칩이 추가된다', async () => {
  render(<WorkChatPanel />);
  await waitFor(() => expect(fetchAeroWorkChatSessions).toHaveBeenCalled());

  const file = new File(['붙여넣기 내용'], 'pasted.txt', { type: 'text/plain' });
  const input = screen.getByPlaceholderText('예: 내일 오전 10시 회의 등록하고 그 내용으로 보고서 작성해줘');
  fireEvent.paste(input, { clipboardData: { files: [file] } });

  expect(await screen.findByText('pasted.txt')).toBeInTheDocument();
});

test('전송 시 orchestrateAeroWork 인자에 attachments 가 포함되고 성공 후 칩이 비워진다', async () => {
  orchestrateAeroWork.mockResolvedValue({
    utterance: '문의',
    session_id: 1,
    results: [baseResult()],
    routed_by: 'rule',
  });

  render(<WorkChatPanel />);
  await waitFor(() => expect(fetchAeroWorkChatSessions).toHaveBeenCalled());

  const file = new File(['첨부 본문'], 'note.md', { type: 'text/markdown' });
  const fileInput = screen.getByLabelText('첨부 파일 선택') as HTMLInputElement;
  fireEvent.change(fileInput, { target: { files: [file] } });
  expect(await screen.findByText('note.md')).toBeInTheDocument();

  const textInput = screen.getByPlaceholderText('예: 내일 오전 10시 회의 등록하고 그 내용으로 보고서 작성해줘');
  fireEvent.change(textInput, { target: { value: '문의' } });
  fireEvent.click(screen.getByRole('button', { name: '보내기' }));

  await waitFor(() => expect(orchestrateAeroWork).toHaveBeenCalled());
  expect(orchestrateAeroWork).toHaveBeenCalledWith('문의', 'csrf-test-token', null, {
    synthesize: false,
    attachments: [{ name: 'note.md', content: '첨부 본문' }],
  });

  await waitFor(() => expect(screen.queryByText('note.md')).not.toBeInTheDocument());
});

test('첨부 개수 상한을 넘으면 안내 문구를 보여주고 전송하지 않는다', async () => {
  render(<WorkChatPanel />);
  await waitFor(() => expect(fetchAeroWorkChatSessions).toHaveBeenCalled());

  const files = Array.from({ length: 6 }, (_, i) => new File([`내용${i}`], `f${i}.md`, { type: 'text/markdown' }));
  const fileInput = screen.getByLabelText('첨부 파일 선택') as HTMLInputElement;
  fireEvent.change(fileInput, { target: { files } });

  await waitFor(() => expect(screen.getByText('f5.md')).toBeInTheDocument());

  const textInput = screen.getByPlaceholderText('예: 내일 오전 10시 회의 등록하고 그 내용으로 보고서 작성해줘');
  fireEvent.change(textInput, { target: { value: '문의' } });
  fireEvent.click(screen.getByRole('button', { name: '보내기' }));

  expect(await screen.findByText('첨부는 최대 5개까지 가능합니다.')).toBeInTheDocument();
  expect(orchestrateAeroWork).not.toHaveBeenCalled();
});

test('routed_by 가 llm 이면 응답 카드에 AI 보조 분류 배지가 표시된다', async () => {
  orchestrateAeroWork.mockResolvedValue({
    utterance: '지식폴더에서 예산 근거 찾아줘',
    session_id: 2,
    results: [baseResult({ kind: 'knowledge', summary: '지식 검색 결과입니다.' })],
    routed_by: 'llm',
  });

  render(<WorkChatPanel />);
  await waitFor(() => expect(fetchAeroWorkChatSessions).toHaveBeenCalled());

  const textInput = screen.getByPlaceholderText('예: 내일 오전 10시 회의 등록하고 그 내용으로 보고서 작성해줘');
  fireEvent.change(textInput, { target: { value: '지식폴더에서 예산 근거 찾아줘' } });
  fireEvent.click(screen.getByRole('button', { name: '보내기' }));

  expect(await screen.findByText('AI 보조 분류')).toBeInTheDocument();
});
