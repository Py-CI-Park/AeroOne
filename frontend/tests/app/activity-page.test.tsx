import React from 'react';
import { act, render, screen } from '@testing-library/react';

import ActivityPage from '@/app/activity/page';

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

// ActivityWorkspace 는 mount 시 fetch 를 수행하는 client island 라, 페이지 테스트에서는
// AppShell 안에 렌더 위임만 확인하는 단순 div 로 대체한다.
vi.mock('@/components/activity/activity-workspace', () => ({
  ActivityWorkspace: () => <div data-testid="activity-workspace-stub" />,
}));

beforeEach(() => {
  cookieThemeMock.mockReturnValue(undefined);
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
  cookieThemeMock.mockReset();
});

test('renders the AppShell with the 내 활동 title and mounts the activity workspace', async () => {
  render(await ActivityPage({ searchParams: Promise.resolve({}) }));
  // AccountMenu 세션 fetch 마이크로태스크를 act 로 플러시("not wrapped in act" 경고 제거).
  await act(async () => {});

  expect(screen.getByTestId('app-shell')).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: '내 활동' })).toBeInTheDocument();
  expect(screen.getByTestId('activity-workspace-stub')).toBeInTheDocument();
});
