import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { ChartForm } from '@/components/office-tools/chart-form';
import { OfficeWorkspaceProvider } from '@/components/office-tools/workspace-context';
import type { ChartGenerateResponse, ChartInspectResponse, OfficeJobDetail } from '@/lib/types';

const { generateChartMock, getOfficeArtifactProxyPathMock, inspectChartDataMock } = vi.hoisted(() => ({
  generateChartMock: vi.fn(),
  getOfficeArtifactProxyPathMock: vi.fn((path: string) => path.replace('/api/v1/office-tools/', '/api/frontend/office-tools/')),
  inspectChartDataMock: vi.fn(),
}));

vi.mock('@/lib/api', () => ({
  generateChart: generateChartMock,
  getOfficeArtifactProxyPath: getOfficeArtifactProxyPathMock,
  inspectChartData: inspectChartDataMock,
  fetchOfficeSamples: () => Promise.resolve([]),
}));

vi.mock('@/lib/cookies', () => ({
  getCsrfCookie: () => 'csrf-test-token',
}));

// echarts 미리보기는 option 만 확인하도록 대체(실제 echarts 렌더 회피).
vi.mock('@/components/office-tools/chart-preview', () => ({
  ChartPreview: ({ option, title }: { option: Record<string, unknown>; title: string }) => (
    <div data-testid="chart-preview-stub" data-title={title}>
      {JSON.stringify(option)}
    </div>
  ),
}));

const PROFILE: ChartInspectResponse = {
  row_count: 4,
  column_count: 2,
  columns: [
    { name: '지역', dtype: 'object', non_null: 4, null: 0, unique: 3, numeric: false, datetime: false },
    { name: '매출', dtype: 'int64', non_null: 4, null: 0, unique: 4, numeric: true, datetime: false },
  ],
  sample: [{ 지역: '서울', 매출: 120 }],
};

const RESULT: ChartGenerateResponse = {
  job_id: 'a'.repeat(32),
  status: 'completed',
  title: '지역별 매출',
  llm_used: false,
  chart_spec: { type: 'bar' },
  echarts_option: { series: [{ type: 'bar', data: [150, 80] }] },
  warnings: ['AI 추천을 요청했지만 활성 LLM 연결이 없어 규칙 기반 추천을 사용했습니다.'],
  artifacts: [],
  preview_url: '/api/v1/office-tools/jobs/aaaa/artifacts/echarts_option.json',
  bundle_url: '/api/v1/office-tools/jobs/aaaa/bundle',
};

function pickFile(): File {
  return new File(['지역,매출\n서울,120\n'], 'sales.csv', { type: 'text/csv' });
}
const ADVANCED_PROFILE: ChartInspectResponse = {
  row_count: 4,
  column_count: 4,
  columns: [
    { name: 'region', dtype: 'object', non_null: 4, null: 0, unique: 2, numeric: false, datetime: false },
    { name: 'channel', dtype: 'object', non_null: 4, null: 0, unique: 2, numeric: false, datetime: false },
    { name: 'revenue', dtype: 'int64', non_null: 4, null: 0, unique: 4, numeric: true, datetime: false },
    { name: 'cost', dtype: 'int64', non_null: 4, null: 0, unique: 4, numeric: true, datetime: false },
  ],
  sample: [{ region: '서울', channel: '온라인', revenue: 120, cost: 30 }],
};

const WORKSPACE_JOB_ID = 'b'.repeat(32);
const WORKSPACE_ARTIFACT = `/api/v1/office-tools/jobs/${WORKSPACE_JOB_ID}/artifacts/echarts_option.json`;
const WORKSPACE_BUNDLE = `/api/v1/office-tools/jobs/${WORKSPACE_JOB_ID}/bundle`;

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

function chartJob(extra: Record<string, unknown> = {}): OfficeJobDetail {
  return {
    job_id: WORKSPACE_JOB_ID,
    service: 'chart',
    owner_id: 1,
    status: 'completed',
    created_at: '2026-07-14T00:00:00Z',
    updated_at: '2026-07-14T00:01:00Z',
    request_summary: {},
    warnings: [],
    artifacts: [{ filename: 'echarts_option.json', media_type: 'application/json', size_bytes: 32, sha256: 'a'.repeat(64), download_url: WORKSPACE_ARTIFACT }],
    error: null,
    title: '이력 차트',
    llm_used: true,
    chart_spec: { type: 'line', aggregation: 'mean', stacked: true, sort: 'value_desc', limit: 12, orientation: 'horizontal' },
    echarts_option: { series: [{ type: 'line', data: [1, 2] }] },
    preview_url: WORKSPACE_ARTIFACT,
    bundle_url: WORKSPACE_BUNDLE,
    ...extra,
  } as OfficeJobDetail;
}

function renderWorkspace(mode: 'reopen' | 'duplicate', job = chartJob()) {
  return render(
    <OfficeWorkspaceProvider selection={{ sequence: 1, mode, job }}>
      <ChartForm />
    </OfficeWorkspaceProvider>,
  );
}

async function openOptions(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole('button', { name: /^옵션/ }));
}

function wait(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

afterEach(() => {
  vi.clearAllMocks();
});

test('auto-inspects attached data and renders column chips', async () => {
  inspectChartDataMock.mockResolvedValue(PROFILE);
  const user = userEvent.setup();
  render(<ChartForm />);

  await user.upload(screen.getByLabelText('데이터 파일'), pickFile());

  await waitFor(() => expect(inspectChartDataMock).toHaveBeenCalledTimes(1), { timeout: 2000 });
  const chips = await screen.findByTestId('chart-column-chips');
  expect(chips).toHaveTextContent('매출');
  expect(chips).toHaveTextContent('숫자');
  expect(chips).toHaveTextContent('지역');
  expect(chips).toHaveTextContent('범주');
});

test('generate calls generateChart and renders the preview + warning', async () => {
  generateChartMock.mockResolvedValue(RESULT);
  const user = userEvent.setup();
  render(<ChartForm />);

  await user.upload(screen.getByLabelText('데이터 파일'), pickFile());
  await user.type(screen.getByPlaceholderText(/지역별 매출/), '지역별 매출 비교');
  await user.click(screen.getByRole('button', { name: '차트 생성' }));

  await waitFor(() => expect(generateChartMock).toHaveBeenCalledTimes(1));
  const [payload, token] = generateChartMock.mock.calls[0];
  expect(payload.prompt).toBe('지역별 매출 비교');
  expect(payload.aiAssist).toBe(true);
  expect(token).toBe('csrf-test-token');

  const preview = await screen.findByTestId('chart-preview-stub');
  expect(preview).toHaveTextContent('bar');
  expect(screen.getByText(/규칙 기반 추천을 사용했습니다/)).toBeInTheDocument();
});

test('shows an error message when generation fails', async () => {
  generateChartMock.mockRejectedValue(new Error('생성 실패'));
  const user = userEvent.setup();
  render(<ChartForm />);

  await user.upload(screen.getByLabelText('데이터 파일'), pickFile());
  await user.click(screen.getByRole('button', { name: '차트 생성' }));

  expect(await screen.findByRole('alert')).toHaveTextContent('생성 실패');
  expect(screen.queryByTestId('chart-preview-stub')).not.toBeInTheDocument();
});

test('uses result.llm_used as the sole provenance signal', async () => {
  generateChartMock.mockResolvedValue({
    ...RESULT,
    llm_used: true,
    warnings: ['규칙 기반이라는 단어가 포함되어도 결과 메타데이터를 우선합니다.'],
  });
  const user = userEvent.setup();
  render(<ChartForm />);

  await user.upload(screen.getByLabelText('데이터 파일'), pickFile());
  await user.click(screen.getByRole('button', { name: '차트 생성' }));

  await waitFor(() => expect(screen.getByTestId('process-steps')).toHaveTextContent('엔진: AI 제안 사용'));
});

test('invalidates an auto-inspect request after data changes and ignores its late result', async () => {
  const first = deferred<ChartInspectResponse>();
  const second = deferred<ChartInspectResponse>();
  inspectChartDataMock.mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise);
  const user = userEvent.setup();
  render(<ChartForm />);

  await user.upload(screen.getByLabelText('데이터 파일'), pickFile());
  await waitFor(() => expect(inspectChartDataMock).toHaveBeenCalledTimes(1), { timeout: 2000 });
  const firstSignal = inspectChartDataMock.mock.calls[0][2] as AbortSignal;

  await user.upload(screen.getByLabelText('데이터 파일'), new File(['region,revenue\n서울,99\n'], 'replacement.csv', { type: 'text/csv' }));
  expect(firstSignal.aborted).toBe(true);
  await waitFor(() => expect(inspectChartDataMock).toHaveBeenCalledTimes(2), { timeout: 2000 });

  second.resolve({ ...PROFILE, row_count: 8 });
  await waitFor(() => expect(screen.getByTestId('chart-column-chips')).toBeInTheDocument());
  first.resolve({ ...PROFILE, row_count: 1 });
  await wait(50);
  // 늦게 도착한 첫 요청의 결과로 대체되지 않는다 — 실패 없이 두 번째 결과만 유효하다.
  expect(screen.getByTestId('chart-column-chips')).toBeInTheDocument();
});

test('invalidates a generate request after options change and ignores its late result', async () => {
  const first = deferred<ChartGenerateResponse>();
  const second = deferred<ChartGenerateResponse>();
  generateChartMock.mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise);
  const user = userEvent.setup();
  render(<ChartForm />);

  await user.upload(screen.getByLabelText('데이터 파일'), pickFile());
  await user.click(screen.getByRole('button', { name: '차트 생성' }));
  await waitFor(() => expect(generateChartMock).toHaveBeenCalledTimes(1));
  const firstSignal = generateChartMock.mock.calls[0][2] as AbortSignal;

  await user.type(screen.getByPlaceholderText(/지역별 매출/), '새');
  expect(firstSignal.aborted).toBe(true);
  await user.click(screen.getByRole('button', { name: '차트 생성' }));
  await waitFor(() => expect(generateChartMock).toHaveBeenCalledTimes(2));

  second.resolve({ ...RESULT, title: '새 결과' });
  expect(await screen.findByTestId('chart-preview-stub')).toHaveAttribute('data-title', '새 결과');
  first.resolve({ ...RESULT, title: '오래된 결과' });
  await waitFor(() => expect(screen.getByTestId('chart-preview-stub')).toHaveAttribute('data-title', '새 결과'));
});

test('suppresses AbortError without replacing the current UI with an error', async () => {
  inspectChartDataMock.mockRejectedValue({ name: 'AbortError' });
  const user = userEvent.setup();
  render(<ChartForm />);

  await user.upload(screen.getByLabelText('데이터 파일'), pickFile());

  await waitFor(() => expect(inspectChartDataMock).toHaveBeenCalledTimes(1), { timeout: 2000 });
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  expect(screen.queryByTestId('chart-column-chips')).not.toBeInTheDocument();
});

test('aborts both independent request lanes when the chart form unmounts', async () => {
  const inspect = deferred<ChartInspectResponse>();
  const generate = deferred<ChartGenerateResponse>();
  inspectChartDataMock.mockReturnValue(inspect.promise);
  generateChartMock.mockReturnValue(generate.promise);
  const user = userEvent.setup();
  const { unmount } = render(<ChartForm />);

  await user.upload(screen.getByLabelText('데이터 파일'), pickFile());
  await waitFor(() => expect(inspectChartDataMock).toHaveBeenCalledTimes(1), { timeout: 2000 });
  await user.click(screen.getByRole('button', { name: '차트 생성' }));
  await waitFor(() => expect(generateChartMock).toHaveBeenCalledTimes(1));

  const inspectSignal = inspectChartDataMock.mock.calls[0][2] as AbortSignal;
  const generateSignal = generateChartMock.mock.calls[0][2] as AbortSignal;
  unmount();

  expect(inspectSignal.aborted).toBe(true);
  expect(generateSignal.aborted).toBe(true);
});

test('submits grouped, stacked multi-y advanced configuration through typed manualSpec', async () => {
  inspectChartDataMock.mockResolvedValue(ADVANCED_PROFILE);
  generateChartMock.mockResolvedValue(RESULT);
  const user = userEvent.setup();
  render(<ChartForm />);

  await user.upload(screen.getByLabelText('데이터 파일'), pickFile());
  await waitFor(() => expect(inspectChartDataMock).toHaveBeenCalledTimes(1), { timeout: 2000 });
  await screen.findByTestId('chart-column-chips');
  await openOptions(user);
  await user.selectOptions(screen.getByLabelText('차트 유형'), 'bar');
  await user.click(screen.getByLabelText('고급 차트 설정 사용'));
  await user.selectOptions(screen.getByLabelText('X 축 열'), 'region');
  await user.selectOptions(screen.getByLabelText('그룹 열 (선택)'), 'channel');
  await user.click(screen.getByLabelText('Y 축 revenue'));
  await user.click(screen.getByLabelText('Y 축 cost'));
  await user.selectOptions(screen.getByLabelText('집계'), 'sum');
  await user.selectOptions(screen.getByLabelText('정렬'), 'value_desc');
  await user.clear(screen.getByLabelText('표시 행 수'));
  await user.type(screen.getByLabelText('표시 행 수'), '15');
  await user.selectOptions(screen.getByLabelText('방향'), 'horizontal');
  await user.click(screen.getByLabelText('누적 표시'));
  await user.click(screen.getByRole('button', { name: '차트 생성' }));

  await waitFor(() => expect(generateChartMock).toHaveBeenCalledTimes(1));
  const [payload] = generateChartMock.mock.calls[0];
  expect(payload.manualSpec).toEqual({
    type: 'bar',
    x: 'region',
    y: ['revenue', 'cost'],
    group: 'channel',
    aggregation: 'sum',
    stacked: true,
    sort: 'value_desc',
    limit: 15,
    orientation: 'horizontal',
  });
  expect(payload).not.toHaveProperty('manualSpecJson');
});

test('blocks advanced generation with invalid required selections before fetching', async () => {
  inspectChartDataMock.mockResolvedValue(ADVANCED_PROFILE);
  const user = userEvent.setup();
  render(<ChartForm />);

  await user.upload(screen.getByLabelText('데이터 파일'), pickFile());
  await waitFor(() => expect(inspectChartDataMock).toHaveBeenCalledTimes(1), { timeout: 2000 });
  await screen.findByTestId('chart-column-chips');
  await openOptions(user);
  await user.click(screen.getByLabelText('고급 차트 설정 사용'));
  await user.click(screen.getByRole('button', { name: '차트 생성' }));

  expect(await screen.findByRole('alert')).toHaveTextContent('X 축 열이 필요합니다');
  expect(generateChartMock).not.toHaveBeenCalled();

  // X 축만 고르고 Y 축을 비우면 집계에 필요한 Y 축 경고로 여전히 요청을 막는다.
  await user.selectOptions(screen.getByLabelText('X 축 열'), 'region');
  await user.click(screen.getByRole('button', { name: '차트 생성' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Y 축 열이 필요합니다');
  expect(generateChartMock).not.toHaveBeenCalled();
});

test('resets profile, result, and advanced selections when data changes', async () => {
  inspectChartDataMock.mockResolvedValue(ADVANCED_PROFILE);
  generateChartMock.mockResolvedValue(RESULT);
  const user = userEvent.setup();
  render(<ChartForm />);

  await user.upload(screen.getByLabelText('데이터 파일'), pickFile());
  await waitFor(() => expect(inspectChartDataMock).toHaveBeenCalledTimes(1), { timeout: 2000 });
  await screen.findByTestId('chart-column-chips');
  await openOptions(user);
  await user.click(screen.getByLabelText('고급 차트 설정 사용'));
  await user.selectOptions(screen.getByLabelText('X 축 열'), 'region');
  await user.click(screen.getByLabelText('Y 축 revenue'));
  await user.click(screen.getByRole('button', { name: '차트 생성' }));
  await screen.findByTestId('chart-result');

  await user.upload(screen.getByLabelText('데이터 파일'), new File(['region,revenue\n부산,88\n'], 'replacement.csv', { type: 'text/csv' }));
  expect(screen.queryByTestId('chart-column-chips')).not.toBeInTheDocument();
  expect(screen.queryByTestId('chart-result')).not.toBeInTheDocument();

  await waitFor(() => expect(inspectChartDataMock).toHaveBeenCalledTimes(2), { timeout: 2000 });
  await screen.findByTestId('chart-column-chips');
  await user.click(screen.getByLabelText('고급 차트 설정 사용'));
  expect(screen.getByLabelText('X 축 열')).toHaveValue('');
  expect(screen.getByLabelText('Y 축 revenue')).not.toBeChecked();
});

test('reopens a validated completed chart workspace result without a rerun', async () => {
  renderWorkspace('reopen');

  expect(await screen.findByTestId('chart-result')).toBeInTheDocument();
  expect(screen.getByTestId('chart-preview-stub')).toHaveAttribute('data-title', '이력 차트');
  expect(screen.getByTestId('process-steps')).toHaveTextContent('엔진: AI 제안 사용');
  expect(generateChartMock).not.toHaveBeenCalled();
  expect(inspectChartDataMock).not.toHaveBeenCalled();
});

test('duplicates only safe chart settings and requires source data to be attached', async () => {
  inspectChartDataMock.mockResolvedValue(ADVANCED_PROFILE);
  const user = userEvent.setup();
  renderWorkspace('duplicate');

  expect(await screen.findByRole('status')).toHaveTextContent('원본 데이터는 복제되지 않습니다');
  expect(screen.getByLabelText('차트 유형')).toHaveValue('line');
  expect(screen.getByRole('button', { name: '차트 생성' })).toBeDisabled();
  expect(screen.queryByTestId('chart-column-chips')).not.toBeInTheDocument();
  expect(screen.queryByTestId('chart-result')).not.toBeInTheDocument();
  expect(generateChartMock).not.toHaveBeenCalled();
  expect(inspectChartDataMock).not.toHaveBeenCalled();

  await user.upload(screen.getByLabelText('데이터 파일'), pickFile());
  await waitFor(() => expect(inspectChartDataMock).toHaveBeenCalledTimes(1), { timeout: 2000 });
  await screen.findByTestId('chart-column-chips');
  expect(screen.getByLabelText('고급 차트 설정 사용')).toBeChecked();
  expect(screen.getByLabelText('집계')).toHaveValue('mean');
  expect(screen.getByLabelText('표시 행 수')).toHaveValue(12);
});

test('renders only valid returned artifact and bundle paths through the office proxy', async () => {
  const validOption = `/api/v1/office-tools/jobs/${RESULT.job_id}/artifacts/echarts_option.json`;
  const validBundle = `/api/v1/office-tools/jobs/${RESULT.job_id}/bundle`;
  generateChartMock.mockResolvedValue({
    ...RESULT,
    artifacts: [
      { filename: 'echarts_option.json', media_type: 'application/json', size_bytes: 20, sha256: 'a'.repeat(64), download_url: validOption },
      { filename: 'private.csv', media_type: 'text/csv', size_bytes: 20, sha256: 'b'.repeat(64), download_url: 'https://example.invalid/private.csv' },
      { filename: 'traversal', media_type: 'text/plain', size_bytes: 20, sha256: 'c'.repeat(64), download_url: `/api/v1/office-tools/jobs/${RESULT.job_id}/artifacts/..` },
    ],
    preview_url: 'https://example.invalid/preview.json',
    bundle_url: validBundle,
  });
  const user = userEvent.setup();
  render(<ChartForm />);

  await user.upload(screen.getByLabelText('데이터 파일'), pickFile());
  await user.click(screen.getByRole('button', { name: '차트 생성' }));

  expect(await screen.findByRole('link', { name: 'ECharts option(JSON)' })).toHaveAttribute(
    'href',
    `/api/frontend/office-tools/jobs/${RESULT.job_id}/artifacts/echarts_option.json`,
  );
  expect(screen.getByRole('link', { name: '전체 번들(zip)' })).toHaveAttribute(
    'href',
    `/api/frontend/office-tools/jobs/${RESULT.job_id}/bundle`,
  );
  expect(screen.queryByRole('link', { name: 'private.csv' })).not.toBeInTheDocument();
  expect(screen.queryByRole('link', { name: 'traversal' })).not.toBeInTheDocument();
  expect(getOfficeArtifactProxyPathMock).toHaveBeenCalledWith(validOption);
  expect(getOfficeArtifactProxyPathMock).toHaveBeenCalledWith(validBundle);
});

test('follow-up command reuses the previous result as previousSpec with the same attached data file', async () => {
  const file = pickFile();
  generateChartMock
    .mockResolvedValueOnce(RESULT)
    .mockResolvedValueOnce({ ...RESULT, title: '상위 3개만 반영' });
  const user = userEvent.setup();
  render(<ChartForm />);

  await user.upload(screen.getByLabelText('데이터 파일'), file);
  await user.click(screen.getByRole('button', { name: '차트 생성' }));
  await screen.findByTestId('chart-result');

  const followUpInput = screen.getByPlaceholderText('예: 상위 5개만, 가로 막대로');
  await user.type(followUpInput, '상위 3개만{Enter}');

  await waitFor(() => expect(generateChartMock).toHaveBeenCalledTimes(2));
  const [followUpPayload] = generateChartMock.mock.calls[1];
  expect(followUpPayload.previousSpec).toEqual(RESULT.chart_spec);
  expect(followUpPayload.prompt).toBe('상위 3개만');
  expect(followUpPayload.dataFile).toBe(file);
  expect(followUpPayload.manualSpec).toBeUndefined();

  expect(await screen.findByTestId('chart-preview-stub')).toHaveAttribute('data-title', '상위 3개만 반영');
});

test('follow-up example chip sends immediately with previousSpec', async () => {
  generateChartMock
    .mockResolvedValueOnce(RESULT)
    .mockResolvedValueOnce({ ...RESULT, title: '가로 막대 결과' });
  const user = userEvent.setup();
  render(<ChartForm />);

  await user.upload(screen.getByLabelText('데이터 파일'), pickFile());
  await user.click(screen.getByRole('button', { name: '차트 생성' }));
  await screen.findByTestId('chart-result');

  await user.click(screen.getByRole('button', { name: '가로 막대로' }));

  await waitFor(() => expect(generateChartMock).toHaveBeenCalledTimes(2));
  const [followUpPayload] = generateChartMock.mock.calls[1];
  expect(followUpPayload.prompt).toBe('가로 막대로');
  expect(followUpPayload.previousSpec).toEqual(RESULT.chart_spec);
});

test('a failed follow-up command keeps the previous result and follow-up input visible', async () => {
  generateChartMock
    .mockResolvedValueOnce(RESULT)
    .mockRejectedValueOnce(new Error('히스토그램에는 정확히 하나의 숫자 y 열이 필요합니다'));
  const user = userEvent.setup();
  render(<ChartForm />);

  await user.upload(screen.getByLabelText('데이터 파일'), pickFile());
  await user.click(screen.getByRole('button', { name: '차트 생성' }));
  await screen.findByTestId('chart-result');

  const followUpInput = screen.getByPlaceholderText('예: 상위 5개만, 가로 막대로');
  await user.type(followUpInput, '히스토그램으로{Enter}');

  // 실패해도 다듬기 루프가 끊기지 않는다 — 직전 결과와 후속 입력이 남고 오류만 표시된다.
  expect(await screen.findByRole('alert')).toHaveTextContent('히스토그램에는 정확히 하나의 숫자 y 열이 필요합니다');
  expect(screen.getByTestId('chart-result')).toBeInTheDocument();
  expect(screen.getByTestId('chart-follow-up')).toBeInTheDocument();
});
