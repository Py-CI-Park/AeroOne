import React from 'react';
import { render, screen } from '@testing-library/react';

import CivilAircraftReportPage from '@/app/reports/civil-aircraft/page';

const { cookieThemeMock, fetchListMock } = vi.hoisted(() => ({
  cookieThemeMock: vi.fn<() => string | undefined>(),
  fetchListMock: vi.fn(),
}));

vi.mock('next/headers', () => ({
  cookies: vi.fn(() => ({
    getAll: () => (cookieThemeMock() ? [{ name: 'aeroone_theme', value: cookieThemeMock() }] : []),
  })),
}));

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return { ...actual, fetchCollectionListServer: fetchListMock };
});

vi.mock('@/components/layout/admin-nav-link', () => ({
  AdminNavLink: () => null,
}));

// DocumentsWorkspace 는 fetch effect + iframe 이라, 페이지 테스트에서는 렌더 위임만 확인하는 단순 div 로 대체.
vi.mock('@/components/documents/documents-workspace', () => ({
  DocumentsWorkspace: ({ documents }: { documents: { path: string }[] }) => (
    <div data-testid="documents-workspace-stub">{documents.map((d) => d.path).join(',')}</div>
  ),
}));

beforeEach(() => {
  cookieThemeMock.mockReturnValue(undefined);
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
  cookieThemeMock.mockReset();
  fetchListMock.mockReset();
});

test('renders the documents workspace when catalogs exist', async () => {
  fetchListMock.mockResolvedValue({
    documents: [
      { path: 'A320.html', name: 'A320', folder: '' },
      { path: 'B737.html', name: 'B737', folder: '' },
    ],
  });

  render(await CivilAircraftReportPage({ searchParams: Promise.resolve({}) }));

  expect(screen.getByRole('heading', { name: 'Civil Aircraft Spec Catalog' })).toBeInTheDocument();
  expect(screen.getByTestId('documents-workspace-stub')).toHaveTextContent('A320.html,B737.html');
  expect(screen.queryByText(/표시할 카탈로그가 없습니다/)).not.toBeInTheDocument();
});

test('shows a fallback message when there are no catalogs', async () => {
  fetchListMock.mockResolvedValue({ documents: [] });

  render(await CivilAircraftReportPage({ searchParams: Promise.resolve({}) }));

  expect(screen.getByText(/표시할 카탈로그가 없습니다/)).toBeInTheDocument();
  expect(screen.queryByTestId('documents-workspace-stub')).not.toBeInTheDocument();
});

test('shows a fallback message when the list request fails', async () => {
  fetchListMock.mockRejectedValue(new Error('network error'));

  render(await CivilAircraftReportPage({ searchParams: Promise.resolve({}) }));

  expect(screen.getByText(/표시할 카탈로그가 없습니다/)).toBeInTheDocument();
  expect(screen.getByText(/network error/)).toBeInTheDocument();
});
