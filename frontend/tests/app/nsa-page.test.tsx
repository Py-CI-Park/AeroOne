import React from 'react';
import { render, screen } from '@testing-library/react';

import NsaPage from '@/app/nsa/page';

const { cookieThemeMock } = vi.hoisted(() => ({
  cookieThemeMock: vi.fn<() => string | undefined>(),
}));

vi.mock('next/headers', () => ({
  cookies: vi.fn(() => ({
    getAll: () => (cookieThemeMock() ? [{ name: 'aeroone_theme', value: cookieThemeMock() }] : []),
  })),
}));

// CollectionPasswordGate는 client 컴포넌트 + fetch 효과라 페이지 테스트에서는 stub 으로 대체.
vi.mock('@/components/collections/collection-password-gate', () => ({
  CollectionPasswordGate: ({ collection, title }: { collection: string; title?: string }) => (
    <div data-testid="collection-password-gate-stub" data-collection={collection}>
      {title}
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
});

test('renders AppShell with title NSA and the password gate', async () => {
  render(await NsaPage({ searchParams: Promise.resolve({}) }));

  expect(screen.getByRole('heading', { name: 'NSA' })).toBeInTheDocument();

  const gate = screen.getByTestId('collection-password-gate-stub');
  expect(gate).toBeInTheDocument();
  expect(gate).toHaveAttribute('data-collection', 'nsa');
});
