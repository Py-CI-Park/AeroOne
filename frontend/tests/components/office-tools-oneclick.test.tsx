import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { DiagramForm } from '@/components/office-tools/diagram-form';
import { ChartForm } from '@/components/office-tools/chart-form';
import { ReportForm } from '@/components/office-tools/report-form';

const mocks = vi.hoisted(() => ({
  generateDiagram: vi.fn(),
  generateChart: vi.fn(),
  generateReport: vi.fn(),
  inspectChartData: vi.fn(),
  fetchOfficeSamples: vi.fn(),
}));

vi.mock('@/lib/api', () => ({
  generateDiagram: mocks.generateDiagram,
  generateChart: mocks.generateChart,
  generateReport: mocks.generateReport,
  inspectChartData: mocks.inspectChartData,
  fetchOfficeSamples: mocks.fetchOfficeSamples,
}));

vi.mock('@/lib/cookies', () => ({ getCsrfCookie: () => 'csrf-test-token' }));

vi.mock('@/components/office-tools/diagram-preview', () => ({
  DiagramPreview: () => <div data-testid="diagram-preview-stub" />,
}));
vi.mock('@/components/office-tools/chart-preview', () => ({
  ChartPreview: () => <div data-testid="chart-preview-stub" />,
}));

const DIAGRAM_SAMPLE = {
  key: 'diagram-flow',
  tool: 'diagram',
  filename: 'f.txt',
  media_type: 'text/plain',
  title: '처리 흐름',
  description: '흐름 예제',
  content: '수집 -> 정제 -> 발행',
  hints: { diagram_type: 'flowchart', title: '흐름도' },
};

const CHART_SAMPLE = {
  key: 'chart-region-bar',
  tool: 'chart',
  filename: 'm.csv',
  media_type: 'text/csv',
  title: '지역 매출(막대)',
  description: '지역별',
  content: 'region,sales\n서울,120\n부산,80\n',
  hints: { prompt: '지역별 매출 비교', chart_type: 'bar' },
};

const REPORT_SAMPLE = {
  key: 'report-sales',
  tool: 'report',
  filename: 'r.md',
  media_type: 'text/markdown',
  title: '매출 보고',
  description: '매출',
  content: '# 매출 보고\n\n본문',
  hints: { title: '2월 매출 보고', subtitle: '요약', ai_mode: 'none' },
};

afterEach(() => {
  vi.clearAllMocks();
});

test('diagram: clicking an example generates immediately (one click)', async () => {
  mocks.fetchOfficeSamples.mockResolvedValue([DIAGRAM_SAMPLE]);
  mocks.generateDiagram.mockResolvedValue({ job_id: 'a'.repeat(32), title: '흐름도', mermaid: 'graph TD;A-->B', warnings: [], artifacts: [] });
  const user = userEvent.setup();
  render(<DiagramForm />);

  await user.click(await screen.findByRole('button', { name: '처리 흐름' }));

  await waitFor(() => expect(mocks.generateDiagram).toHaveBeenCalledTimes(1));
  const [payload] = mocks.generateDiagram.mock.calls[0];
  expect(payload.description).toContain('수집');
  expect(payload.diagram_type).toBe('flowchart');
});

test('chart: clicking an example generates immediately (one click)', async () => {
  mocks.fetchOfficeSamples.mockResolvedValue([CHART_SAMPLE]);
  mocks.generateChart.mockResolvedValue({
    job_id: 'a'.repeat(32), status: 'completed', title: '지역 매출', llm_used: false,
    chart_spec: { type: 'bar' }, echarts_option: { series: [] }, warnings: [], artifacts: [],
    preview_url: '/p', bundle_url: '/b',
  });
  const user = userEvent.setup();
  render(<ChartForm />);

  await user.click(await screen.findByRole('button', { name: '지역 매출(막대)' }));

  await waitFor(() => expect(mocks.generateChart).toHaveBeenCalledTimes(1));
  const [payload] = mocks.generateChart.mock.calls[0];
  expect(payload.dataFile).toBeInstanceOf(File);
  expect(payload.prompt).toBe('지역별 매출 비교');
  expect(payload.chartType).toBe('bar');
});

test('chart: a manual_spec example passes the full ChartSpec through (stacked/grouped)', async () => {
  const stackedSample = {
    key: 'chart-region-channel-stacked',
    tool: 'chart',
    filename: 'rc.csv',
    media_type: 'text/csv',
    title: '지역×채널 누적막대(스택)',
    description: '누적',
    content: 'region,channel,revenue\n서울,온라인,10\n서울,오프라인,5\n',
    hints: { manual_spec: { type: 'bar', x: 'region', y: ['revenue'], group: 'channel', stacked: true } },
  };
  mocks.fetchOfficeSamples.mockResolvedValue([stackedSample]);
  mocks.generateChart.mockResolvedValue({
    job_id: 'a'.repeat(32), status: 'completed', title: '누적', llm_used: false,
    chart_spec: { type: 'bar' }, echarts_option: { series: [] }, warnings: [], artifacts: [],
    preview_url: '/p', bundle_url: '/b',
  });
  const user = userEvent.setup();
  render(<ChartForm />);

  await user.click(await screen.findByRole('button', { name: '지역×채널 누적막대(스택)' }));

  await waitFor(() => expect(mocks.generateChart).toHaveBeenCalledTimes(1));
  const [payload] = mocks.generateChart.mock.calls[0];
  expect(payload.manualSpecJson).toBeTruthy();
  expect(JSON.parse(payload.manualSpecJson).stacked).toBe(true);
  expect(JSON.parse(payload.manualSpecJson).group).toBe('channel');
  expect(payload.manualSpec).toBeUndefined();
});

test('report: clicking an example generates immediately (one click)', async () => {
  mocks.fetchOfficeSamples.mockResolvedValue([REPORT_SAMPLE]);
  mocks.generateReport.mockResolvedValue({ job_id: 'a'.repeat(32), title: '2월 매출 보고', html: '<h1>x</h1>', warnings: [], artifacts: [] });
  const user = userEvent.setup();
  render(<ReportForm />);

  await user.click(await screen.findByRole('button', { name: '매출 보고' }));

  await waitFor(() => expect(mocks.generateReport).toHaveBeenCalledTimes(1));
  const [payload] = mocks.generateReport.mock.calls[0];
  expect(payload.markdownFile).toBeInstanceOf(File);
  expect(payload.title).toBe('2월 매출 보고');
  expect(payload.aiMode).toBe('none');
});
