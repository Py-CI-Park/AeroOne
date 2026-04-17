import React from 'react';
import { render, screen } from '@testing-library/react';

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

test('removes the home hero copy while keeping the newsletter service link and theme selector', async () => {
  render(await HomePage({ searchParams: Promise.resolve({}) }));

  expect(screen.queryByText('AeroOne Internal Platform')).not.toBeInTheDocument();
  expect(screen.queryByText('사내 문서형 서비스 시작점')).not.toBeInTheDocument();
  expect(
    screen.queryByText(/현재는 뉴스레터 서비스부터 시작합니다/),
  ).not.toBeInTheDocument();

  const newsletterLink = screen.getByRole('link', { name: /뉴스레터 서비스/i });

  expect(newsletterLink).toHaveAttribute('href', '/newsletters');
  expect(newsletterLink).toHaveTextContent('가장 최신 뉴스레터를 바로 열고, 발행 날짜별로 이전 뉴스레터를 탐색합니다.');
  expect(newsletterLink).toHaveTextContent('활성 서비스');
  expect(screen.queryByTestId('service-card-icon')).not.toBeInTheDocument();
  expect(screen.getByTestId('newsletter-theme-selector')).toBeInTheDocument();
});

test('home page uses dark theme from cookie', async () => {
  cookieThemeMock.mockReturnValue('dark');

  render(await HomePage({ searchParams: Promise.resolve({}) }));

  expect(screen.getByTestId('app-shell')).toHaveClass('bg-slate-950');
  expect(screen.getByRole('link', { name: '라이트 테마로 전환' })).toBeInTheDocument();
});
