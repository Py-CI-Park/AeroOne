import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';

import NsaPage from '@/app/nsa/page';
import { ApiError, fetchCollectionList } from '@/lib/api';

const { cookieThemeMock } = vi.hoisted(() => ({
  cookieThemeMock: vi.fn<() => string | undefined>(),
}));

vi.mock('next/headers', () => ({
  cookies: vi.fn(() => ({
    getAll: () => (cookieThemeMock() ? [{ name: 'aeroone_theme', value: cookieThemeMock() }] : []),
  })),
}));

vi.mock('@/lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api')>();
  return {
    ...actual,
    fetchCollectionList: vi.fn(),
  };
});

vi.mock('@/components/documents/documents-workspace', () => ({
  DocumentsWorkspace: ({ documents, collection, initialPath }: { documents: { path: string }[]; collection: string; initialPath?: string }) => (
    <div data-testid="documents-workspace-stub" data-collection={collection} data-initial-path={initialPath ?? ''}>
      {documents.map((d) => d.path).join(',')}
    </div>
  ),
}));

const fetchCollectionListMock = vi.mocked(fetchCollectionList);

beforeEach(() => {
  cookieThemeMock.mockReturnValue(undefined);
  fetchCollectionListMock.mockResolvedValue({ documents: [{ path: 'secret.html', name: 'Secret', folder: '' }] });
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
  cookieThemeMock.mockReset();
  fetchCollectionListMock.mockReset();
});

test('renders AppShell with title NSA and loads the NSA collection workspace without password gate', async () => {
  render(await NsaPage({ searchParams: Promise.resolve({ path: 'secret.html' }) }));

  expect(screen.getByRole('heading', { name: 'NSA' })).toBeInTheDocument();
  expect(screen.queryByLabelText('비밀번호')).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: '확인' })).not.toBeInTheDocument();

  await waitFor(() => expect(fetchCollectionListMock).toHaveBeenCalledWith('nsa'));
  const workspace = await screen.findByTestId('documents-workspace-stub');
  expect(workspace).toHaveAttribute('data-collection', 'nsa');
  expect(workspace).toHaveAttribute('data-initial-path', 'secret.html');
  expect(workspace).toHaveTextContent('secret.html');
});

test('shows Korean access-denied copy when NSA list fetch returns 403', async () => {
  fetchCollectionListMock.mockRejectedValue(new ApiError('Forbidden', 403));

  render(await NsaPage({ searchParams: Promise.resolve({}) }));

  expect(await screen.findByText('NSA 자료는 권한이 있는 계정만 이용할 수 있습니다. 관리자에게 접근 권한을 요청하세요.')).toBeInTheDocument();
  expect(screen.queryByTestId('documents-workspace-stub')).not.toBeInTheDocument();
  expect(screen.queryByLabelText('비밀번호')).not.toBeInTheDocument();
});
