import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { DiagramForm } from '@/components/office-tools/diagram-form';
import { OfficeWorkspaceProvider } from '@/components/office-tools/workspace-context';
import type { DiagramGenerateResponse, OfficeJobDetail } from '@/lib/types';

const { generateDiagramMock, getOfficeArtifactProxyPathMock } = vi.hoisted(() => ({
  generateDiagramMock: vi.fn(),
  getOfficeArtifactProxyPathMock: vi.fn(),
}));

vi.mock('@/lib/api', () => ({
  generateDiagram: generateDiagramMock,
  getOfficeArtifactProxyPath: getOfficeArtifactProxyPathMock,
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

const JOB_ID = 'a'.repeat(32);
const ARTIFACT_PATH = `/api/v1/office-tools/jobs/${JOB_ID}/artifacts/diagram.mmd`;
const BUNDLE_PATH = `/api/v1/office-tools/jobs/${JOB_ID}/bundle`;

const RESPONSE: DiagramGenerateResponse = {
  job_id: JOB_ID,
  status: 'completed',
  title: '업무 다이어그램',
  diagram_type: 'flowchart',
  mermaid: 'flowchart TD\n    N1["수집"] --> N2["발행"]',
  llm_used: false,
  warnings: ['AI 생성을 요청했지만 활성 LLM 연결이 없어 규칙 기반 생성을 사용했습니다.'],
  artifacts: [],
  preview_url: ARTIFACT_PATH,
  bundle_url: BUNDLE_PATH,
};

function response(overrides: Partial<DiagramGenerateResponse> = {}): DiagramGenerateResponse {
  return { ...RESPONSE, ...overrides };
}

function deferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((nextResolve, nextReject) => {
    resolve = nextResolve;
    reject = nextReject;
  });
  return { promise, resolve, reject };
}

function workspaceDiagramJob(overrides: Record<string, unknown> = {}): OfficeJobDetail {
  return {
    job_id: JOB_ID,
    service: 'diagram',
    owner_id: 1,
    status: 'completed',
    created_at: '2026-07-14T00:00:00Z',
    updated_at: '2026-07-14T00:01:00Z',
    request_summary: { diagram_type: 'sequence', ai_assist: false },
    warnings: [],
    artifacts: [],
    error: null,
    title: '저장된 시퀀스',
    diagram_type: 'sequence',
    mermaid: 'sequenceDiagram\n  사용자->>서버: 요청',
    llm_used: true,
    preview_url: ARTIFACT_PATH,
    bundle_url: BUNDLE_PATH,
    ...overrides,
  } as OfficeJobDetail;
}

beforeEach(() => {
  getOfficeArtifactProxyPathMock.mockImplementation((path: string) => (
    path.replace('/api/v1/office-tools/', '/api/frontend/office-tools/')
  ));
});

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
    expect.any(AbortSignal),
  );

  const preview = await screen.findByTestId('preview-stub');
  expect(preview).toHaveTextContent('flowchart TD');
  expect(screen.getByText('규칙 기반')).toBeInTheDocument();
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

test.each([
  { aiAssist: false, llmUsed: true, warnings: ['규칙 기반으로 생성했다는 오래된 경고'], expectedLabel: 'AI 제안 사용' },
  { aiAssist: true, llmUsed: false, warnings: [], expectedLabel: '규칙 기반' },
])('uses llm_used=$llmUsed as the exact process provenance label', async ({ aiAssist, llmUsed, warnings, expectedLabel }) => {
  generateDiagramMock.mockResolvedValue(response({ llm_used: llmUsed, warnings }));
  const user = userEvent.setup();
  render(<DiagramForm />);

  if (!aiAssist) {
    await user.click(screen.getByRole('checkbox'));
  }
  await user.type(screen.getByPlaceholderText('수집 -> 정제 -> 발행'), 'A -> B');
  await user.click(screen.getByRole('button', { name: '다이어그램 생성' }));

  await screen.findByTestId('preview-stub');
  expect(screen.getByText(expectedLabel)).toBeInTheDocument();
});

test('silently ignores an aborted generation request', async () => {
  let signal: AbortSignal | undefined;
  generateDiagramMock.mockImplementation((_payload: unknown, _csrf: string, nextSignal: AbortSignal) => {
    signal = nextSignal;
    return new Promise((_, reject) => {
      nextSignal.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')));
    });
  });
  const user = userEvent.setup();
  render(<DiagramForm />);

  const description = screen.getByPlaceholderText('수집 -> 정제 -> 발행');
  await user.type(description, 'A -> B');
  await user.click(screen.getByRole('button', { name: '다이어그램 생성' }));
  await user.type(description, ' C');

  await waitFor(() => expect(signal?.aborted).toBe(true));
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  expect(screen.queryByTestId('diagram-result')).not.toBeInTheDocument();
});

test('keeps the newer request busy and ignores the older response after an input change', async () => {
  const first = deferred<DiagramGenerateResponse>();
  const second = deferred<DiagramGenerateResponse>();
  generateDiagramMock.mockImplementationOnce(() => first.promise).mockImplementationOnce(() => second.promise);
  const user = userEvent.setup();
  render(<DiagramForm />);

  const description = screen.getByPlaceholderText('수집 -> 정제 -> 발행');
  await user.type(description, 'A -> B');
  await user.click(screen.getByRole('button', { name: '다이어그램 생성' }));
  await waitFor(() => expect(generateDiagramMock).toHaveBeenCalledTimes(1));

  const firstSignal = generateDiagramMock.mock.calls[0][2] as AbortSignal;
  await user.clear(description);
  await user.type(description, 'C -> D');
  expect(firstSignal.aborted).toBe(true);

  await user.click(screen.getByRole('button', { name: '다이어그램 생성' }));
  await waitFor(() => expect(generateDiagramMock).toHaveBeenCalledTimes(2));

  first.resolve(response({ title: '오래된 결과', mermaid: 'flowchart TD\n  OLD' }));
  await waitFor(() => {
    expect(screen.getByRole('button', { name: '생성 중…' })).toBeDisabled();
    expect(screen.queryByText(/OLD/)).not.toBeInTheDocument();
  });

  second.resolve(response({ title: '새 결과', mermaid: 'flowchart TD\n  NEW' }));
  expect(await screen.findByTestId('preview-stub')).toHaveAttribute('data-title', '새 결과');
});

test('renders only valid returned artifact and bundle paths', async () => {
  const malformedArtifactPath = 'https://example.com/diagram.mmd';
  const traversalArtifactPath = `/api/v1/office-tools/jobs/${JOB_ID}/artifacts/../private.mmd`;
  generateDiagramMock.mockResolvedValue(response({
    artifacts: [
      { filename: 'diagram.mmd', media_type: 'text/plain', size_bytes: 10, sha256: 'b'.repeat(64), download_url: ARTIFACT_PATH },
      { filename: 'outside.mmd', media_type: 'text/plain', size_bytes: 10, sha256: 'c'.repeat(64), download_url: malformedArtifactPath },
      { filename: 'private.mmd', media_type: 'text/plain', size_bytes: 10, sha256: 'd'.repeat(64), download_url: traversalArtifactPath },
    ],
  }));
  const user = userEvent.setup();
  render(<DiagramForm />);

  await user.type(screen.getByPlaceholderText('수집 -> 정제 -> 발행'), 'A -> B');
  await user.click(screen.getByRole('button', { name: '다이어그램 생성' }));

  expect(await screen.findByRole('link', { name: 'diagram.mmd' })).toHaveAttribute(
    'href',
    '/api/frontend/office-tools/jobs/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/artifacts/diagram.mmd',
  );
  expect(screen.getByRole('link', { name: '번들 다운로드' })).toHaveAttribute(
    'href',
    '/api/frontend/office-tools/jobs/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/bundle',
  );
  expect(screen.queryByRole('link', { name: 'outside.mmd' })).not.toBeInTheDocument();
  expect(screen.queryByRole('link', { name: 'private.mmd' })).not.toBeInTheDocument();
  expect(getOfficeArtifactProxyPathMock).toHaveBeenCalledWith(ARTIFACT_PATH);
  expect(getOfficeArtifactProxyPathMock).toHaveBeenCalledWith(BUNDLE_PATH);
  expect(getOfficeArtifactProxyPathMock).not.toHaveBeenCalledWith(malformedArtifactPath);
  expect(getOfficeArtifactProxyPathMock).not.toHaveBeenCalledWith(traversalArtifactPath);
});

test('omits a malformed returned bundle path', async () => {
  const malformedBundlePath = 'https://example.com/diagram-bundle.zip';
  generateDiagramMock.mockResolvedValue(response({ bundle_url: malformedBundlePath }));
  const user = userEvent.setup();
  render(<DiagramForm />);

  await user.type(screen.getByPlaceholderText('수집 -> 정제 -> 발행'), 'A -> B');
  await user.click(screen.getByRole('button', { name: '다이어그램 생성' }));

  await screen.findByTestId('preview-stub');
  expect(screen.queryByRole('link', { name: '번들 다운로드' })).not.toBeInTheDocument();
  expect(getOfficeArtifactProxyPathMock).not.toHaveBeenCalledWith(malformedBundlePath);
});

test('reopens a valid stored diagram and invalidates an in-flight request on selection', async () => {
  const pending = deferred<DiagramGenerateResponse>();
  generateDiagramMock.mockReturnValue(pending.promise);
  const user = userEvent.setup();
  const view = render(
    <OfficeWorkspaceProvider selection={null}>
      <DiagramForm />
    </OfficeWorkspaceProvider>,
  );

  await user.type(screen.getByPlaceholderText('수집 -> 정제 -> 발행'), 'A -> B');
  await user.click(screen.getByRole('button', { name: '다이어그램 생성' }));
  await waitFor(() => expect(generateDiagramMock).toHaveBeenCalledTimes(1));
  const pendingSignal = generateDiagramMock.mock.calls[0][2] as AbortSignal;

  view.rerender(
    <OfficeWorkspaceProvider selection={{ sequence: 1, mode: 'reopen', job: workspaceDiagramJob() }}>
      <DiagramForm />
    </OfficeWorkspaceProvider>,
  );

  expect(await screen.findByTestId('preview-stub')).toHaveTextContent('sequenceDiagram');
  expect(screen.getByText('AI 제안 사용')).toBeInTheDocument();
  expect(screen.getByPlaceholderText('수집 -> 정제 -> 발행')).toHaveValue('');
  expect(pendingSignal.aborted).toBe(true);

  pending.resolve(response({ title: '오래된 결과', mermaid: 'flowchart TD\n  OLD' }));
  await waitFor(() => expect(screen.getByTestId('preview-stub')).toHaveTextContent('sequenceDiagram'));
});

test('duplicates only safe diagram configuration and requires a new description', async () => {
  render(
    <OfficeWorkspaceProvider selection={{ sequence: 1, mode: 'duplicate', job: workspaceDiagramJob() }}>
      <DiagramForm />
    </OfficeWorkspaceProvider>,
  );

  expect(await screen.findByText('설정만 복제했습니다. 설명을 다시 입력하세요.')).toBeInTheDocument();
  expect(screen.getByPlaceholderText('업무 다이어그램')).toHaveValue('저장된 시퀀스');
  expect(screen.getByRole('combobox')).toHaveValue('sequence');
  expect(screen.getByRole('checkbox')).not.toBeChecked();
  expect(screen.getByPlaceholderText('수집 -> 정제 -> 발행')).toHaveValue('');
  expect(screen.getByRole('button', { name: '다이어그램 생성' })).toBeDisabled();
  expect(screen.queryByTestId('diagram-result')).not.toBeInTheDocument();
  expect(generateDiagramMock).not.toHaveBeenCalled();
});

test('aborts an in-flight request when unmounted', async () => {
  const pending = deferred<DiagramGenerateResponse>();
  generateDiagramMock.mockReturnValue(pending.promise);
  const user = userEvent.setup();
  const view = render(<DiagramForm />);

  await user.type(screen.getByPlaceholderText('수집 -> 정제 -> 발행'), 'A -> B');
  await user.click(screen.getByRole('button', { name: '다이어그램 생성' }));
  await waitFor(() => expect(generateDiagramMock).toHaveBeenCalledTimes(1));

  const signal = generateDiagramMock.mock.calls[0][2] as AbortSignal;
  view.unmount();

  expect(signal.aborted).toBe(true);
});
