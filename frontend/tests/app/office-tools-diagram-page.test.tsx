import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { DiagramForm } from '@/components/office-tools/diagram-form';
import type { DiagramGenerateResponse } from '@/lib/types';

const { generateDiagramMock } = vi.hoisted(() => ({
  generateDiagramMock: vi.fn(),
}));

vi.mock('@/lib/api', () => ({
  generateDiagram: generateDiagramMock,
  fetchOfficeSamples: () => Promise.resolve([]),
}));

vi.mock('@/lib/cookies', () => ({
  getCsrfCookie: () => 'csrf-test-token',
}));

// mermaid 미리보기는 소스만 확인하도록 대체(실제 mermaid 렌더 회피).
vi.mock('@/components/office-tools/diagram-preview', () => ({
  DiagramPreview: ({ source, title }: { source: string; title: string }) => (
    <div data-testid="preview-stub" data-title={title}>
      {source}
    </div>
  ),
}));

const RESPONSE: DiagramGenerateResponse = {
  job_id: 'a'.repeat(32),
  status: 'completed',
  title: '업무 다이어그램',
  diagram_type: 'flowchart',
  mermaid: 'flowchart TD\n    N1["수집"] --> N2["발행"]',
  warnings: ['AI 생성을 요청했지만 활성 LLM 연결이 없어 규칙 기반 생성을 사용했습니다.'],
  artifacts: [],
  preview_url: '/api/v1/office-tools/jobs/aaaa/artifacts/diagram.mmd',
  bundle_url: '/api/v1/office-tools/jobs/aaaa/bundle',
};

afterEach(() => {
  vi.clearAllMocks();
});

test('submitting the form calls generateDiagram with typed payload and renders the preview', async () => {
  generateDiagramMock.mockResolvedValue(RESPONSE);
  const user = userEvent.setup();
  render(<DiagramForm />);

  await user.type(screen.getByPlaceholderText('수집 -> 정제 -> 발행'), '수집 -> 발행');
  await user.click(screen.getByRole('button', { name: '다이어그램 생성' }));

  await waitFor(() => expect(generateDiagramMock).toHaveBeenCalledTimes(1));
  expect(generateDiagramMock).toHaveBeenCalledWith(
    { description: '수집 -> 발행', diagram_type: 'flowchart', title: '', ai_assist: true },
    'csrf-test-token',
  );

  const preview = await screen.findByTestId('preview-stub');
  expect(preview).toHaveTextContent('flowchart TD');
  // 폴백 경고가 노출된다.
  expect(screen.getByText(/규칙 기반 생성을 사용했습니다/)).toBeInTheDocument();
});

test('shows an error message when generation fails', async () => {
  generateDiagramMock.mockRejectedValue(new Error('생성 실패'));
  const user = userEvent.setup();
  render(<DiagramForm />);

  await user.type(screen.getByPlaceholderText('수집 -> 정제 -> 발행'), 'A -> B');
  await user.click(screen.getByRole('button', { name: '다이어그램 생성' }));

  expect(await screen.findByRole('alert')).toHaveTextContent('생성 실패');
  expect(screen.queryByTestId('preview-stub')).not.toBeInTheDocument();
});
