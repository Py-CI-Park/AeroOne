import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

import { CollectionPasswordGate } from '@/components/collections/collection-password-gate';

const { fetchCollectionListMock } = vi.hoisted(() => ({
  fetchCollectionListMock: vi.fn(),
}));

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return { ...actual, fetchCollectionList: fetchCollectionListMock };
});

// DocumentsWorkspace 는 fetch effect + iframe 이라, 게이트 테스트에서는 단순 stub 으로 대체.
vi.mock('@/components/documents/documents-workspace', () => ({
  DocumentsWorkspace: ({ documents }: { documents: { path: string }[] }) => (
    <div data-testid="documents-workspace-stub">{documents.map((d) => d.path).join(',')}</div>
  ),
}));

const DOCS = [
  { path: 'secret-a.html', name: 'Secret A', folder: '' },
  { path: 'secret-b.html', name: 'Secret B', folder: '' },
];

afterEach(() => {
  vi.restoreAllMocks();
  fetchCollectionListMock.mockReset();
});

test('initial render shows password form and fetchCollectionList is NOT called', () => {
  render(<CollectionPasswordGate collection="nsa" />);

  expect(screen.getByRole('button', { name: '확인' })).toBeInTheDocument();
  expect(screen.getByLabelText('비밀번호')).toBeInTheDocument();
  expect(fetchCollectionListMock.mock.calls.length).toBe(0);
});

test('wrong code shows error and fetchCollectionList is still NOT called', () => {
  render(<CollectionPasswordGate collection="nsa" />);

  fireEvent.change(screen.getByLabelText('비밀번호'), { target: { value: '1234' } });
  fireEvent.click(screen.getByRole('button', { name: '확인' }));

  expect(screen.getByRole('alert')).toHaveTextContent('비밀번호가 올바르지 않습니다.');
  expect(fetchCollectionListMock.mock.calls.length).toBe(0);
});

test('correct code 0000 unlocks: fetchCollectionList called with "nsa" and workspace renders', async () => {
  fetchCollectionListMock.mockResolvedValue({ documents: DOCS });

  render(<CollectionPasswordGate collection="nsa" />);

  fireEvent.change(screen.getByLabelText('비밀번호'), { target: { value: '0000' } });
  fireEvent.click(screen.getByRole('button', { name: '확인' }));

  await waitFor(() =>
    expect(fetchCollectionListMock).toHaveBeenCalledWith('nsa'),
  );
  expect(fetchCollectionListMock).toHaveBeenCalledTimes(1);

  const stub = await screen.findByTestId('documents-workspace-stub');
  expect(stub).toHaveTextContent('secret-a.html,secret-b.html');
});
