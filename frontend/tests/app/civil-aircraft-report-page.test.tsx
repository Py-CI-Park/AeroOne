import React from 'react';
import { render, screen } from '@testing-library/react';

import CivilAircraftReportPage from '@/app/reports/civil-aircraft/page';

const { cookieThemeMock, fetchReportMock } = vi.hoisted(() => ({
  cookieThemeMock: vi.fn<() => string | undefined>(),
  fetchReportMock: vi.fn(),
}));

vi.mock('next/headers', () => ({
  cookies: vi.fn(() => ({
    getAll: () => (cookieThemeMock() ? [{ name: 'aeroone_theme', value: cookieThemeMock() }] : []),
  })),
}));

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return { ...actual, fetchCivilAircraftReport: fetchReportMock };
});

// HtmlViewer 는 iframe + observer 라 단위 테스트에서는 단순 div 로 대체(렌더 위임만 확인).
vi.mock('@/components/newsletter/html-viewer', () => ({
  HtmlViewer: ({ title, html }: { title: string; html: string }) => (
    <div data-testid="report-html" data-title={title}>
      {html}
    </div>
  ),
}));

beforeEach(() => {
  cookieThemeMock.mockReturnValue(undefined);
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
  cookieThemeMock.mockReset();
  fetchReportMock.mockReset();
});

test('renders the civil aircraft report html directly, without a calendar', async () => {
  fetchReportMock.mockResolvedValue({ asset_type: 'html', content_html: '<h1>spec</h1>' });

  render(await CivilAircraftReportPage({ searchParams: Promise.resolve({}) }));

  expect(screen.getByRole('heading', { name: 'Civil Aircraft Spec Catalog' })).toBeInTheDocument();
  expect(screen.getByTestId('civil-aircraft-report')).toBeInTheDocument();
  expect(screen.getByTestId('report-html')).toHaveTextContent('<h1>spec</h1>');

  // 달력 관련 요소는 일절 렌더되지 않는다(뉴스레터 리딩 뷰와의 핵심 차이).
  expect(screen.queryByTestId('newsletter-date-calendar')).not.toBeInTheDocument();
  expect(screen.queryByTestId('newsletters-calendar-panel')).not.toBeInTheDocument();
  expect(screen.queryByTestId('newsletters-reading')).not.toBeInTheDocument();
});

test('shows a fallback message when the report is unavailable', async () => {
  fetchReportMock.mockRejectedValue(new Error('not found'));

  render(await CivilAircraftReportPage({ searchParams: Promise.resolve({}) }));

  expect(screen.getByText(/표시할 보고서가 없습니다/)).toBeInTheDocument();
  expect(screen.queryByTestId('report-html')).not.toBeInTheDocument();
});
