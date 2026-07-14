import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { ReportForm } from '@/components/office-tools/report-form';
import { OfficeWorkspaceProvider } from '@/components/office-tools/workspace-context';
import type { OfficeArtifact, OfficeJobDetail, ReportGenerateResponse } from '@/lib/types';

const { generateReportMock, getOfficeArtifactProxyPathMock } = vi.hoisted(() => ({
  generateReportMock: vi.fn(),
  getOfficeArtifactProxyPathMock: vi.fn((path: string) => path.replace('/api/v1/office-tools/', '/api/frontend/office-tools/')),
}));

vi.mock('@/lib/api', () => ({
  generateReport: generateReportMock,
  getOfficeArtifactProxyPath: getOfficeArtifactProxyPathMock,
  fetchOfficeSamples: () => Promise.resolve([]),
}));

vi.mock('@/lib/cookies', () => ({
  getCsrfCookie: () => 'csrf-test-token',
}));

const JOB_ID = 'a'.repeat(32);
const PREVIEW_PATH = `/api/v1/office-tools/jobs/${JOB_ID}/artifacts/report.html`;
const BUNDLE_PATH = `/api/v1/office-tools/jobs/${JOB_ID}/bundle`;

const RESPONSE: ReportGenerateResponse = {
  job_id: JOB_ID,
  status: 'completed',
  title: '분기 보고',
  ai_mode: 'none',
  llm_used: false,
  html: '<!doctype html><html><body><h1>분기 보고</h1></body></html>',
  warnings: [],
  artifacts: [],
  preview_url: PREVIEW_PATH,
  bundle_url: BUNDLE_PATH,
};

const REPORT_ARTIFACT: OfficeArtifact = {
  filename: 'report.html',
  media_type: 'text/html',
  size_bytes: 123,
  sha256: 'a'.repeat(64),
  download_url: PREVIEW_PATH,
};

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

function reportJob(overrides: Record<string, unknown> = {}) {
  return {
    job_id: JOB_ID,
    service: 'report',
    owner_id: 1,
    status: 'completed',
    created_at: '2026-07-14T00:00:00Z',
    updated_at: '2026-07-14T00:00:00Z',
    request_summary: {},
    warnings: [],
    artifacts: [],
    error: null,
    ...overrides,
  } as OfficeJobDetail;
}

function uploadMarkdown(name = 'report.md') {
  const file = new File(['# 분기 보고\n\n본문'], name, { type: 'text/markdown' });
  fireEvent.change(screen.getByLabelText(/Markdown 파일/), { target: { files: [file] } });
  return file;
}

afterEach(() => {
  vi.clearAllMocks();
});

test('submitting the form uploads the markdown file and renders the sandboxed inline preview', async () => {
  generateReportMock.mockResolvedValue(RESPONSE);
  const user = userEvent.setup();
  render(<ReportForm />);

  const file = uploadMarkdown();
  await user.click(screen.getByRole('button', { name: '보고서 생성' }));

  await waitFor(() => expect(generateReportMock).toHaveBeenCalledTimes(1));
  const [input, token, signal] = generateReportMock.mock.calls[0];
  expect(input.markdownFile).toBe(file);
  expect(input.aiMode).toBe('none');
  expect(token).toBe('csrf-test-token');
  expect(signal).toBeInstanceOf(AbortSignal);

  const result = await screen.findByTestId('report-result');
  expect(result).toBeInTheDocument();
  const iframe = screen.getByTitle('보고서 미리보기') as HTMLIFrameElement;
  expect(iframe.getAttribute('sandbox')).toBe('');
  expect(iframe.getAttribute('srcdoc')).toContain('분기 보고');
  expect(iframe.getAttribute('src')).toBeNull();
});

test('shows an error message when generation fails', async () => {
  generateReportMock.mockRejectedValue(new Error('생성 실패'));
  const user = userEvent.setup();
  render(<ReportForm />);

  uploadMarkdown();
  await user.click(screen.getByRole('button', { name: '보고서 생성' }));

  expect(await screen.findByRole('alert')).toHaveTextContent('생성 실패');
  expect(screen.queryByTestId('report-result')).not.toBeInTheDocument();
});

test('clears a visible result when an editable option changes', async () => {
  generateReportMock.mockResolvedValue(RESPONSE);
  const user = userEvent.setup();
  render(<ReportForm />);

  uploadMarkdown();
  await user.click(screen.getByRole('button', { name: '보고서 생성' }));
  expect(await screen.findByTestId('report-result')).toBeInTheDocument();

  await user.type(screen.getByLabelText('제목'), '수정');
  expect(screen.queryByTestId('report-result')).not.toBeInTheDocument();
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
});

test('ignores a stale successful response and stale finally while a newer request is active', async () => {
  const first = deferred<ReportGenerateResponse>();
  const second = deferred<ReportGenerateResponse>();
  generateReportMock.mockImplementationOnce(() => first.promise).mockImplementationOnce(() => second.promise);
  const user = userEvent.setup();
  render(<ReportForm />);

  uploadMarkdown('first.md');
  await user.click(screen.getByRole('button', { name: '보고서 생성' }));
  await waitFor(() => expect(generateReportMock).toHaveBeenCalledTimes(1));

  uploadMarkdown('second.md');
  expect(generateReportMock.mock.calls[0][2].aborted).toBe(true);
  await user.click(screen.getByRole('button', { name: '보고서 생성' }));
  await waitFor(() => expect(generateReportMock).toHaveBeenCalledTimes(2));

  await act(async () => {
    first.resolve({ ...RESPONSE, title: '오래된 결과' });
    await first.promise;
  });

  expect(screen.queryByTestId('report-result')).not.toBeInTheDocument();
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: '생성 중…' })).toBeInTheDocument();

  await act(async () => {
    second.resolve({ ...RESPONSE, title: '최신 결과' });
    await second.promise;
  });
  expect(await screen.findByText('최신 결과')).toBeInTheDocument();
});

test('ignores a stale error and stale finally while a newer request is active', async () => {
  const first = deferred<ReportGenerateResponse>();
  const second = deferred<ReportGenerateResponse>();
  generateReportMock.mockImplementationOnce(() => first.promise).mockImplementationOnce(() => second.promise);
  const user = userEvent.setup();
  render(<ReportForm />);

  uploadMarkdown('first.md');
  await user.click(screen.getByRole('button', { name: '보고서 생성' }));
  await waitFor(() => expect(generateReportMock).toHaveBeenCalledTimes(1));

  uploadMarkdown('second.md');
  await user.click(screen.getByRole('button', { name: '보고서 생성' }));
  await waitFor(() => expect(generateReportMock).toHaveBeenCalledTimes(2));

  await act(async () => {
    first.reject(new Error('오래된 오류'));
    await first.promise.catch(() => undefined);
  });

  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: '생성 중…' })).toBeInTheDocument();

  await act(async () => {
    second.resolve(RESPONSE);
    await second.promise;
  });
  expect(await screen.findByTestId('report-result')).toBeInTheDocument();
});

test('treats AbortError as a silent cancellation', async () => {
  const aborted = new Error('취소됨');
  aborted.name = 'AbortError';
  generateReportMock.mockRejectedValue(aborted);
  const user = userEvent.setup();
  render(<ReportForm />);

  uploadMarkdown();
  await user.click(screen.getByRole('button', { name: '보고서 생성' }));

  await waitFor(() => expect(screen.getByRole('button', { name: '보고서 생성' })).toBeInTheDocument());
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  expect(screen.queryByTestId('report-result')).not.toBeInTheDocument();
});

test('aborts the active request when unmounted', async () => {
  const pending = deferred<ReportGenerateResponse>();
  generateReportMock.mockImplementation(() => pending.promise);
  const user = userEvent.setup();
  const view = render(<ReportForm />);

  uploadMarkdown();
  await user.click(screen.getByRole('button', { name: '보고서 생성' }));
  await waitFor(() => expect(generateReportMock).toHaveBeenCalledTimes(1));

  const signal = generateReportMock.mock.calls[0][2] as AbortSignal;
  view.unmount();
  expect(signal.aborted).toBe(true);

  await act(async () => {
    pending.resolve(RESPONSE);
    await pending.promise;
  });
});

test.each([
  { ai_mode: 'none' as const, llm_used: true, label: 'AI 편집 사용' },
  { ai_mode: 'executive' as const, llm_used: false, label: 'AI 미사용' },
])('uses llm_used for the provenance label ($label)', async ({ ai_mode, llm_used, label }) => {
  generateReportMock.mockResolvedValue({ ...RESPONSE, ai_mode, llm_used, warnings: ['LLM 연결 경고'] });
  const user = userEvent.setup();
  render(<ReportForm />);

  uploadMarkdown();
  await user.click(screen.getByRole('button', { name: '보고서 생성' }));

  expect(await screen.findByText(label)).toBeInTheDocument();
});

test('reopens a completed report through its returned owner-scoped preview URL when no inline HTML is stored', async () => {
  const job = reportJob({
    title: '저장 보고서',
    llm_used: true,
    preview_url: PREVIEW_PATH,
    bundle_url: BUNDLE_PATH,
    artifacts: [REPORT_ARTIFACT],
    request_summary: {
      subtitle: '저장된 부제',
      document_version: 'v2.0',
      tags: '이력,보고서',
      ai_mode: 'polish',
    },
  });

  render(
    <OfficeWorkspaceProvider selection={{ sequence: 1, mode: 'reopen', job }}>
      <ReportForm />
    </OfficeWorkspaceProvider>,
  );

  expect(await screen.findByTestId('report-result')).toBeInTheDocument();
  expect(screen.getByLabelText('제목')).toHaveValue('저장 보고서');
  expect(screen.getByLabelText('부제')).toHaveValue('저장된 부제');
  expect(screen.getByLabelText('버전')).toHaveValue('v2.0');
  expect(screen.getByLabelText('태그')).toHaveValue('이력,보고서');
  expect(screen.getByRole('combobox')).toHaveValue('polish');
  expect(screen.getByText('AI 편집 사용')).toBeInTheDocument();

  const iframe = screen.getByTitle('보고서 미리보기') as HTMLIFrameElement;
  expect(iframe.getAttribute('sandbox')).toBe('');
  expect(iframe.getAttribute('srcdoc')).toBeNull();
  expect(iframe.getAttribute('src')).toBe(`/api/frontend/office-tools/jobs/${JOB_ID}/artifacts/report.html`);
  expect(screen.getByRole('link', { name: 'report.html' })).toHaveAttribute(
    'href',
    `/api/frontend/office-tools/jobs/${JOB_ID}/artifacts/report.html`,
  );
  expect(screen.getByRole('link', { name: '전체 번들(zip)' })).toHaveAttribute(
    'href',
    `/api/frontend/office-tools/jobs/${JOB_ID}/bundle`,
  );
});

test('duplicates only safe report metadata and requires the original input to be reattached', async () => {
  const user = userEvent.setup();
  const view = render(
    <OfficeWorkspaceProvider selection={null}>
      <ReportForm />
    </OfficeWorkspaceProvider>,
  );

  uploadMarkdown();
  await user.type(screen.getByLabelText('제목'), '원본 제목');
  view.rerender(
    <OfficeWorkspaceProvider
      selection={{
        sequence: 1,
        mode: 'duplicate',
        job: reportJob({
          title: '복제 제목',
          request_summary: {
            subtitle: '복제 부제',
            version: 'v3',
            tags: '복제,설정',
            ai_mode: 'executive',
            source_filename: '원본.md',
          },
        }),
      }}
    >
      <ReportForm />
    </OfficeWorkspaceProvider>,
  );

  expect(await screen.findByRole('status')).toHaveTextContent('원본 Markdown과 첨부 자산을 다시 첨부하세요');
  expect(screen.getByLabelText('제목')).toHaveValue('복제 제목');
  expect(screen.getByLabelText('부제')).toHaveValue('복제 부제');
  expect(screen.getByLabelText('버전')).toHaveValue('v3');
  expect(screen.getByLabelText('태그')).toHaveValue('복제,설정');
  expect(screen.getByRole('combobox')).toHaveValue('executive');
  expect(screen.getByRole('button', { name: '보고서 생성' })).toBeDisabled();
  expect(screen.queryByText('선택됨:')).not.toBeInTheDocument();
  expect(screen.queryByTestId('report-result')).not.toBeInTheDocument();
  expect(generateReportMock).not.toHaveBeenCalled();
});

test('renders only valid manifest and bundle download paths through the artifact proxy', async () => {
  const malformedArtifactPath = 'https://example.test/api/v1/office-tools/jobs/other/artifacts/escape.html';
  generateReportMock.mockResolvedValue({
    ...RESPONSE,
    artifacts: [
      REPORT_ARTIFACT,
      {
        ...REPORT_ARTIFACT,
        filename: 'malformed.html',
        download_url: malformedArtifactPath,
      },
    ],
  });
  const user = userEvent.setup();
  render(<ReportForm />);

  uploadMarkdown();
  await user.click(screen.getByRole('button', { name: '보고서 생성' }));

  expect(await screen.findByRole('link', { name: 'report.html' })).toHaveAttribute(
    'href',
    `/api/frontend/office-tools/jobs/${JOB_ID}/artifacts/report.html`,
  );
  expect(screen.queryByRole('link', { name: 'malformed.html' })).not.toBeInTheDocument();
  expect(screen.getByRole('link', { name: '전체 번들(zip)' })).toHaveAttribute(
    'href',
    `/api/frontend/office-tools/jobs/${JOB_ID}/bundle`,
  );
  expect(getOfficeArtifactProxyPathMock).toHaveBeenCalledWith(PREVIEW_PATH);
  expect(getOfficeArtifactProxyPathMock).toHaveBeenCalledWith(BUNDLE_PATH);
  expect(getOfficeArtifactProxyPathMock).not.toHaveBeenCalledWith(malformedArtifactPath);
});