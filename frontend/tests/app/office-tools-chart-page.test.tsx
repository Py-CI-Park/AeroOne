import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { ChartForm } from '@/components/office-tools/chart-form';
import type { ChartGenerateResponse, ChartInspectResponse } from '@/lib/types';

const { generateChartMock, inspectChartDataMock } = vi.hoisted(() => ({
  generateChartMock: vi.fn(),
  inspectChartDataMock: vi.fn(),
}));

vi.mock('@/lib/api', () => ({
  generateChart: generateChartMock,
  inspectChartData: inspectChartDataMock,
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

afterEach(() => {
  vi.clearAllMocks();
});

test('inspect shows the data profile table', async () => {
  inspectChartDataMock.mockResolvedValue(PROFILE);
  const user = userEvent.setup();
  render(<ChartForm />);

  await user.upload(screen.getByLabelText(/데이터 파일/), pickFile());
  await user.click(screen.getByRole('button', { name: '데이터 미리보기' }));

  await waitFor(() => expect(inspectChartDataMock).toHaveBeenCalledTimes(1));
  const profile = await screen.findByTestId('chart-profile');
  expect(profile).toHaveTextContent('행 4개');
  expect(profile).toHaveTextContent('매출');
});

test('generate calls generateChart and renders the preview + warning', async () => {
  generateChartMock.mockResolvedValue(RESULT);
  const user = userEvent.setup();
  render(<ChartForm />);

  await user.upload(screen.getByLabelText(/데이터 파일/), pickFile());
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

  await user.upload(screen.getByLabelText(/데이터 파일/), pickFile());
  await user.click(screen.getByRole('button', { name: '차트 생성' }));

  expect(await screen.findByRole('alert')).toHaveTextContent('생성 실패');
  expect(screen.queryByTestId('chart-preview-stub')).not.toBeInTheDocument();
});
