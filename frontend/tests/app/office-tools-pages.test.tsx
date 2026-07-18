import React from 'react';
import { act, render, screen } from '@testing-library/react';

import OfficeReportPage from '@/app/office-tools/report/page';
import OfficeChartPage from '@/app/office-tools/chart/page';
import OfficeDiagramPage from '@/app/office-tools/diagram/page';

const { cookieThemeMock } = vi.hoisted(() => ({
  cookieThemeMock: vi.fn<() => string | undefined>(),
}));

vi.mock('next/headers', () => ({
  cookies: vi.fn(() => ({
    getAll: () => (cookieThemeMock() ? [{ name: 'aeroone_theme', value: cookieThemeMock() }] : []),
  })),
}));

vi.mock('@/components/layout/admin-nav-link', () => ({
  AdminNavLink: () => null,
}));

// 다이어그램 폼은 mermaid dynamic import 를 품으므로 페이지 스모크 테스트에서는 대체한다.
vi.mock('@/components/office-tools/diagram-form', () => ({
  DiagramForm: () => <div data-testid="diagram-form-stub">diagram form</div>,
}));

// 보고서 폼은 업로드/미리보기 iframe 을 품으므로 페이지 스모크 테스트에서는 대체한다.
vi.mock('@/components/office-tools/report-form', () => ({
  ReportForm: () => <div data-testid="report-form-stub">report form</div>,
}));

// 차트 폼은 echarts dynamic import 를 품으므로 페이지 스모크 테스트에서는 대체한다.
vi.mock('@/components/office-tools/chart-form', () => ({
  ChartForm: () => <div data-testid="chart-form-stub">chart form</div>,
}));

beforeEach(() => {
  cookieThemeMock.mockReturnValue(undefined);
});

afterEach(() => {
  vi.restoreAllMocks();
  cookieThemeMock.mockReset();
});

test('report page renders AppShell title and the report form', async () => {
  render(await OfficeReportPage({ searchParams: Promise.resolve({}) }));
  // AccountMenu 세션 fetch 마이크로태스크를 act 로 플러시("not wrapped in act" 경고 제거).
  await act(async () => {});
  expect(screen.getAllByText('보고서 스튜디오').length).toBeGreaterThan(0);
  // 보고서 도구는 구현 완료 — 플레이스홀더가 아니라 폼이 렌더된다.
  expect(screen.getByTestId('report-form-stub')).toBeInTheDocument();
});

test('chart page renders AppShell title and the chart form', async () => {
  render(await OfficeChartPage({ searchParams: Promise.resolve({}) }));
  // AccountMenu 세션 fetch 마이크로태스크를 act 로 플러시("not wrapped in act" 경고 제거).
  await act(async () => {});
  expect(screen.getAllByText('차트 스튜디오').length).toBeGreaterThan(0);
  // 차트 도구는 구현 완료 — 플레이스홀더가 아니라 폼이 렌더된다.
  expect(screen.getByTestId('chart-form-stub')).toBeInTheDocument();
});

test('diagram page renders AppShell title and the diagram form', async () => {
  render(await OfficeDiagramPage({ searchParams: Promise.resolve({}) }));
  // AccountMenu 세션 fetch 마이크로태스크를 act 로 플러시("not wrapped in act" 경고 제거).
  await act(async () => {});
  expect(screen.getAllByText('다이어그램 스튜디오').length).toBeGreaterThan(0);
  // 다이어그램 도구는 구현 완료 — 플레이스홀더가 아니라 폼이 렌더된다.
  expect(screen.getByTestId('diagram-form-stub')).toBeInTheDocument();
});
