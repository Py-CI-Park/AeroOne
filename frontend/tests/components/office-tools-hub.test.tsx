import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { OfficeToolsHub } from '@/components/office-tools/office-tools-hub';
import type { OfficeJobDetail, OfficeJobListItem, OfficeJobListResponse } from '@/lib/types';

const apiMocks = vi.hoisted(() => ({
  fetchOfficeJob: vi.fn(),
  fetchOfficeJobs: vi.fn(),
  getOfficeArtifactProxyPath: vi.fn(),
}));

vi.mock('@/lib/api', () => ({
  fetchOfficeJob: apiMocks.fetchOfficeJob,
  fetchOfficeJobs: apiMocks.fetchOfficeJobs,
  getOfficeArtifactProxyPath: apiMocks.getOfficeArtifactProxyPath,
}));

// 각 폼은 dynamic import(mermaid/echarts)·업로드를 품으므로 허브 탭 테스트에서는 대체한다.
vi.mock('@/components/office-tools/diagram-form', async () => {
  const { useOfficeWorkspaceSelection } = await vi.importActual<typeof import('@/components/office-tools/workspace-context')>(
    '@/components/office-tools/workspace-context',
  );

  return {
    DiagramForm: () => {
      const selection = useOfficeWorkspaceSelection();
      return (
        <div data-testid="diagram-form-stub">
          {selection ? `${selection.sequence}:${selection.mode}:${selection.job.job_id}` : 'none'}
        </div>
      );
    },
  };
});
vi.mock('@/components/office-tools/chart-form', () => ({
  ChartForm: () => <div data-testid="chart-form-stub">chart</div>,
}));
vi.mock('@/components/office-tools/report-form', () => ({
  ReportForm: () => <div data-testid="report-form-stub">report</div>,
}));

const JOB_ID = 'a'.repeat(32);

function createJobListItem(overrides: Partial<OfficeJobListItem> = {}): OfficeJobListItem {
  return {
    job_id: JOB_ID,
    service: 'chart',
    status: 'completed',
    created_at: '2026-07-14T08:00:00Z',
    updated_at: '2026-07-14T09:00:00Z',
    warnings: [],
    artifacts: [],
    title: '분기 매출',
    llm_used: false,
    ...overrides,
  };
}

function createJobDetail(overrides: Partial<OfficeJobDetail> = {}): OfficeJobDetail {
  return {
    job_id: JOB_ID,
    service: 'chart',
    owner_id: 7,
    status: 'completed',
    created_at: '2026-07-14T08:00:00Z',
    updated_at: '2026-07-14T09:00:00Z',
    request_summary: { prompt: '분기 매출 비교' },
    warnings: [],
    artifacts: [],
    error: null,
    ...overrides,
  };
}

function createHistory(jobs: OfficeJobListItem[] = []): OfficeJobListResponse {
  return {
    jobs,
    usage: {
      job_count: jobs.length,
      total_bytes: 512,
      max_jobs_per_owner: 10,
      max_bytes_per_owner: 1024 * 1024,
    },
  };
}

beforeEach(() => {
  window.history.replaceState({}, '', '/office-tools');
  apiMocks.fetchOfficeJob.mockReset();
  apiMocks.fetchOfficeJobs.mockReset();
  apiMocks.getOfficeArtifactProxyPath.mockReset();

  apiMocks.fetchOfficeJobs.mockResolvedValue(createHistory());
  apiMocks.fetchOfficeJob.mockResolvedValue(createJobDetail());
  apiMocks.getOfficeArtifactProxyPath.mockImplementation((path: string) => (
    path.replace('/api/v1/office-tools/', '/api/frontend/office-tools/')
  ));
});

afterEach(() => {
  vi.restoreAllMocks();
});

test('keeps every form mounted in linked tab panels while hiding inactive panels', async () => {
  render(<OfficeToolsHub />);
  await screen.findByText('아직 작업 이력이 없습니다.');

  const diagramTab = screen.getByRole('tab', { name: '다이어그램' });
  const chartTab = screen.getByRole('tab', { name: '차트' });
  const reportTab = screen.getByRole('tab', { name: '보고서' });
  const diagramPanel = document.getElementById('office-tools-panel-diagram');
  const chartPanel = document.getElementById('office-tools-panel-chart');
  const reportPanel = document.getElementById('office-tools-panel-report');

  expect(screen.getByTestId('diagram-form-stub')).toBeInTheDocument();
  expect(screen.getByTestId('chart-form-stub')).toBeInTheDocument();
  expect(screen.getByTestId('report-form-stub')).toBeInTheDocument();
  expect(diagramTab).toHaveAttribute('id', 'office-tools-tab-diagram');
  expect(diagramTab).toHaveAttribute('aria-controls', 'office-tools-panel-diagram');
  expect(diagramTab).toHaveAttribute('aria-selected', 'true');
  expect(diagramTab).toHaveAttribute('tabindex', '0');
  expect(chartTab).toHaveAttribute('aria-controls', 'office-tools-panel-chart');
  expect(chartTab).toHaveAttribute('tabindex', '-1');
  expect(reportTab).toHaveAttribute('aria-controls', 'office-tools-panel-report');
  expect(diagramPanel).toHaveAttribute('role', 'tabpanel');
  expect(diagramPanel).toHaveAttribute('aria-labelledby', 'office-tools-tab-diagram');
  expect(chartPanel).toHaveAttribute('role', 'tabpanel');
  expect(chartPanel).toHaveAttribute('aria-labelledby', 'office-tools-tab-chart');
  expect(reportPanel).toHaveAttribute('role', 'tabpanel');
  expect(reportPanel).toHaveAttribute('aria-labelledby', 'office-tools-tab-report');
  expect(chartPanel).toHaveAttribute('hidden');
  expect(reportPanel).toHaveAttribute('hidden');
});

test('honors the initial tab prop when no tab query is present', async () => {
  render(<OfficeToolsHub initialTab="chart" />);
  await screen.findByText('아직 작업 이력이 없습니다.');

  expect(document.getElementById('office-tools-panel-chart')).not.toHaveAttribute('hidden');
  expect(document.getElementById('office-tools-panel-diagram')).toHaveAttribute('hidden');
  expect(new URLSearchParams(window.location.search).get('tab')).toBe('chart');
});

test('clicking and ArrowLeft/ArrowRight/Home/End activate and focus tabs', async () => {
  const user = userEvent.setup();
  render(<OfficeToolsHub />);
  await screen.findByText('아직 작업 이력이 없습니다.');

  await user.click(screen.getByRole('tab', { name: '보고서' }));
  expect(screen.getByRole('tab', { name: '보고서' })).toHaveAttribute('aria-selected', 'true');
  expect(document.getElementById('office-tools-panel-report')).not.toHaveAttribute('hidden');
  expect(document.getElementById('office-tools-panel-diagram')).toHaveAttribute('hidden');

  const reportTab = screen.getByRole('tab', { name: '보고서' });
  reportTab.focus();
  await user.keyboard('{ArrowRight}');
  expect(screen.getByRole('tab', { name: '다이어그램' })).toHaveFocus();
  expect(screen.getByRole('tab', { name: '다이어그램' })).toHaveAttribute('aria-selected', 'true');

  await user.keyboard('{ArrowLeft}');
  expect(screen.getByRole('tab', { name: '보고서' })).toHaveFocus();
  expect(screen.getByRole('tab', { name: '보고서' })).toHaveAttribute('aria-selected', 'true');

  await user.keyboard('{Home}');
  expect(screen.getByRole('tab', { name: '다이어그램' })).toHaveFocus();
  expect(screen.getByRole('tab', { name: '다이어그램' })).toHaveAttribute('aria-selected', 'true');

  await user.keyboard('{End}');
  expect(screen.getByRole('tab', { name: '보고서' })).toHaveFocus();
  expect(screen.getByRole('tab', { name: '보고서' })).toHaveAttribute('aria-selected', 'true');
});

test('canonicalizes tab URLs with replaceState and applies popstate changes', async () => {
  window.history.replaceState({}, '', '/office-tools?view=recent#history');
  const replaceState = vi.spyOn(window.history, 'replaceState');
  const pushState = vi.spyOn(window.history, 'pushState');
  const user = userEvent.setup();

  render(<OfficeToolsHub />);
  await screen.findByText('아직 작업 이력이 없습니다.');

  expect(new URLSearchParams(window.location.search).get('view')).toBe('recent');
  expect(new URLSearchParams(window.location.search).get('tab')).toBe('diagram');
  expect(replaceState.mock.calls.map((call) => call[2])).toContain('/office-tools?view=recent&tab=diagram#history');

  await user.click(screen.getByRole('tab', { name: '차트' }));
  expect(new URLSearchParams(window.location.search).get('tab')).toBe('chart');
  expect(replaceState.mock.calls.map((call) => call[2])).toContain('/office-tools?view=recent&tab=chart#history');
  expect(pushState).not.toHaveBeenCalled();

  window.history.replaceState({}, '', '/office-tools?view=recent&tab=report');
  fireEvent.popState(window);
  expect(screen.getByRole('tab', { name: '보고서' })).toHaveAttribute('aria-selected', 'true');

  window.history.replaceState({}, '', '/office-tools?view=recent&tab=unknown');
  fireEvent.popState(window);
  expect(screen.getByRole('tab', { name: '다이어그램' })).toHaveAttribute('aria-selected', 'true');
  expect(new URLSearchParams(window.location.search).get('view')).toBe('recent');
  expect(new URLSearchParams(window.location.search).get('tab')).toBe('diagram');
});

test('shows the job history loading state, empty state, and refreshes the owner-scoped list', async () => {
  let resolveHistory: (value: OfficeJobListResponse) => void = () => {};
  apiMocks.fetchOfficeJobs.mockReturnValueOnce(new Promise<OfficeJobListResponse>((resolve) => {
    resolveHistory = resolve;
  }));
  const user = userEvent.setup();

  render(<OfficeToolsHub />);
  expect(screen.getByRole('status')).toHaveTextContent('작업 이력을 불러오는 중…');

  resolveHistory(createHistory());
  expect(await screen.findByText('아직 작업 이력이 없습니다.')).toBeInTheDocument();

  await user.click(screen.getByRole('button', { name: '새로고침' }));
  await waitFor(() => expect(apiMocks.fetchOfficeJobs).toHaveBeenCalledTimes(2));
});

test('shows owner job metadata and only renders valid manifest artifact proxy links', async () => {
  const validArtifactPath = `/api/v1/office-tools/jobs/${JOB_ID}/artifacts/chart_spec.json`;
  const malformedArtifactPath = 'https://example.invalid/private.csv';
  const traversalArtifactPath = `/api/v1/office-tools/jobs/${JOB_ID}/artifacts/..`;
  apiMocks.fetchOfficeJobs.mockResolvedValue(createHistory([
    createJobListItem({
      warnings: ['규칙 기반으로 생성했습니다.'],
      llm_used: true,
      artifacts: [
        { filename: 'chart_spec.json', media_type: 'application/json', size_bytes: 12, sha256: 'a'.repeat(64), download_url: validArtifactPath },
        { filename: 'private.csv', media_type: 'text/csv', size_bytes: 8, sha256: 'b'.repeat(64), download_url: malformedArtifactPath },
        { filename: 'traversal', media_type: 'text/plain', size_bytes: 1, sha256: 'c'.repeat(64), download_url: traversalArtifactPath },
      ],
    }),
  ]));

  render(<OfficeToolsHub />);

  expect(await screen.findByText('분기 매출')).toBeInTheDocument();
  expect(screen.getByText('chart · completed')).toBeInTheDocument();
  expect(screen.getByText(/업데이트/)).toHaveAttribute('datetime', '2026-07-14T09:00:00Z');
  expect(screen.getByText('생성 경로: AI 보조 사용')).toBeInTheDocument();
  expect(screen.getByText('경고: 규칙 기반으로 생성했습니다.')).toBeInTheDocument();
  expect(screen.getByText('사용량: 작업 1 / 10 · 저장소 512 B / 1.0 MB')).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'chart_spec.json (12 B)' })).toHaveAttribute(
    'href',
    `/api/frontend/office-tools/jobs/${JOB_ID}/artifacts/chart_spec.json`,
  );
  expect(screen.queryByRole('link', { name: /private\.csv/ })).not.toBeInTheDocument();
  expect(screen.queryByRole('link', { name: /traversal/ })).not.toBeInTheDocument();
  expect(apiMocks.getOfficeArtifactProxyPath).toHaveBeenCalledWith(validArtifactPath);
  expect(apiMocks.getOfficeArtifactProxyPath).not.toHaveBeenCalledWith(malformedArtifactPath);
  expect(apiMocks.getOfficeArtifactProxyPath).not.toHaveBeenCalledWith(traversalArtifactPath);
});

test('shows a fetch error when the owner-scoped history request fails', async () => {
  apiMocks.fetchOfficeJobs.mockRejectedValue(new Error('network unavailable'));

  render(<OfficeToolsHub />);

  expect(await screen.findByRole('alert')).toHaveTextContent('작업 이력을 불러오지 못했습니다: network unavailable');
});

test('selecting owner history detail switches tabs and publishes monotonic reopen and duplicate context', async () => {
  apiMocks.fetchOfficeJobs.mockResolvedValue(createHistory([createJobListItem({ service: 'chart' })]));
  apiMocks.fetchOfficeJob.mockResolvedValue(createJobDetail({ service: 'chart' }));
  const user = userEvent.setup();

  render(<OfficeToolsHub />);
  await screen.findByText('분기 매출');

  await user.click(screen.getByRole('button', { name: '다시 열기' }));
  await waitFor(() => {
    expect(apiMocks.fetchOfficeJob).toHaveBeenCalledWith(JOB_ID);
    expect(screen.getByRole('tab', { name: '차트' })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByTestId('diagram-form-stub')).toHaveTextContent(`1:reopen:${JOB_ID}`);
  });

  await user.click(screen.getByRole('button', { name: '설정 복제' }));
  await waitFor(() => expect(screen.getByTestId('diagram-form-stub')).toHaveTextContent(`2:duplicate:${JOB_ID}`));
  expect(screen.getByText('설정 복제는 새 작업을 실행하지 않습니다. 원본 파일 또는 텍스트가 이력에 없으면 다시 첨부해야 합니다.')).toBeInTheDocument();
});

test('rejects history details with an unsupported service without publishing a selection', async () => {
  apiMocks.fetchOfficeJobs.mockResolvedValue(createHistory([createJobListItem({ service: 'unknown' })]));
  apiMocks.fetchOfficeJob.mockResolvedValue(createJobDetail({ service: 'unknown' }));
  const user = userEvent.setup();

  render(<OfficeToolsHub />);
  await screen.findByText('분기 매출');

  await user.click(screen.getByRole('button', { name: '다시 열기' }));

  expect(await screen.findByRole('alert')).toHaveTextContent('지원하지 않는 작업 서비스라서 이 작업을 열 수 없습니다.');
  expect(screen.getByRole('tab', { name: '다이어그램' })).toHaveAttribute('aria-selected', 'true');
  expect(screen.getByTestId('diagram-form-stub')).toHaveTextContent('none');
});
