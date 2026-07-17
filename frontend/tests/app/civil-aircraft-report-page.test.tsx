import React from 'react';
import { act, render, screen } from '@testing-library/react';

import CivilAircraftReportPage from '@/app/reports/civil-aircraft/page';

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

beforeEach(() => {
  cookieThemeMock.mockReturnValue(undefined);
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
  cookieThemeMock.mockReset();
});

// v1.16.0: the Civil Aircraft catalog is the interactive v1.7 dashboard embedded via a
// same-origin proxy (scripts run), replacing the previous sanitized single-report view.
const APP_SRC = '/api/frontend/reports/civil-aircraft/app/index.html';

test('renders the interactive v1.7 dashboard in a same-origin iframe', async () => {
  const { container } = render(await CivilAircraftReportPage({ searchParams: Promise.resolve({}) }));
  // AccountMenu 세션 fetch 마이크로태스크를 act 로 플러시("not wrapped in act" 경고 제거).
  await act(async () => {});

  expect(screen.getByRole('heading', { name: 'Civil Aircraft Spec Catalog' })).toBeInTheDocument();

  const frame = container.querySelector('iframe');
  expect(frame).not.toBeNull();
  expect(frame).toHaveAttribute('src', APP_SRC);
  expect(frame).toHaveAttribute('title', 'Civil Aircraft Data Portal v1.7');
  // Scripts must be allowed so the bundled dashboard runs (unlike the sanitized report path).
  expect(frame?.getAttribute('sandbox') ?? '').toContain('allow-scripts');
});

test('offers a new-tab launch link to the dashboard entry', async () => {
  render(await CivilAircraftReportPage({ searchParams: Promise.resolve({}) }));
  // AccountMenu 세션 fetch 마이크로태스크를 act 로 플러시("not wrapped in act" 경고 제거).
  await act(async () => {});

  const openLink = screen.getByRole('link', { name: /새 창으로 열기/ });
  expect(openLink).toHaveAttribute('href', APP_SRC);
  expect(openLink).toHaveAttribute('target', '_blank');
});
