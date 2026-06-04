import React from 'react';
import { render, screen, within } from '@testing-library/react';

import HomePage from '@/app/page';

const { cookieThemeMock } = vi.hoisted(() => ({
  cookieThemeMock: vi.fn<() => string | undefined>(),
}));

vi.mock('next/headers', () => ({
  cookies: vi.fn(() => ({
    getAll: () => (cookieThemeMock() ? [{ name: 'aeroone_theme', value: cookieThemeMock() }] : []),
  })),
}));

beforeEach(() => {
  cookieThemeMock.mockReturnValue(undefined);
});

afterEach(() => {
  vi.unstubAllEnvs();
  cookieThemeMock.mockReset();
});

test('removes the home hero copy while keeping the Newsletter link and theme selector', async () => {
  render(await HomePage({ searchParams: Promise.resolve({}) }));

  expect(screen.queryByText('AeroOne Internal Platform')).not.toBeInTheDocument();
  expect(screen.queryByText('사내 문서형 서비스 시작점')).not.toBeInTheDocument();
  expect(
    screen.queryByText(/현재는 뉴스레터 서비스부터 시작합니다/),
  ).not.toBeInTheDocument();

  const newsletterLink = within(screen.getByRole('main')).getByRole('link', { name: /Newsletter/i });

  expect(newsletterLink).toHaveAttribute('href', '/newsletters');
  expect(newsletterLink).not.toHaveTextContent('Open the latest issue and browse previous issues by date.');
  expect(newsletterLink).toHaveTextContent('Active');
  expect(newsletterLink).not.toHaveTextContent('뉴스레터 서비스');
  expect(newsletterLink).not.toHaveTextContent('뉴스레터');
  expect(within(newsletterLink).queryByTestId('service-card-description')).not.toBeInTheDocument();
  expect(screen.queryByTestId('service-card-icon')).not.toBeInTheDocument();
  expect(screen.getByTestId('newsletter-theme-selector')).toBeInTheDocument();
});

test('adds an active Civil Aircraft Spec Catalog card linking to the report page', async () => {
  render(await HomePage({ searchParams: Promise.resolve({}) }));

  const main = screen.getByRole('main');
  const reportLink = within(main).getByRole('link', { name: /Civil Aircraft Spec Catalog/i });

  expect(reportLink).toHaveAttribute('href', '/reports/civil-aircraft');
  expect(reportLink).toHaveTextContent('Active');
  expect(within(reportLink).getByTestId('service-card-description')).toHaveTextContent(/Commercial aircraft specs/i);

  // 상단 요약 카운트는 MODULES 에서 파생 — Document 활성화로 활성 카드가 3개로 갱신된다.
  expect(screen.getByText('3 active · 2 coming soon')).toBeInTheDocument();
});

test('adds an active Document card linking to the documents page', async () => {
  render(await HomePage({ searchParams: Promise.resolve({}) }));

  const main = screen.getByRole('main');
  const documentLink = within(main).getByRole('link', { name: /Document/i });

  expect(documentLink).toHaveAttribute('href', '/documents');
  expect(documentLink).toHaveTextContent('Active');
  expect(within(documentLink).getByTestId('service-card-description')).toHaveTextContent(/HTML documents organized in folders/i);
});

test('home page uses dark theme from cookie', async () => {
  cookieThemeMock.mockReturnValue('dark');

  render(await HomePage({ searchParams: Promise.resolve({}) }));

  // 테마는 <html>(layout) 에 부착 — 셸이 아니라 토글 방향으로 dark 반영을 확인.
  expect(screen.getByRole('link', { name: '라이트 테마로 전환' })).toBeInTheDocument();
});
