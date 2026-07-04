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
  DocumentsWorkspace: ({ documents, initialPath }: { documents: { path: string }[]; initialPath?: string }) => (
    <div data-testid="documents-workspace-stub" data-initial-path={initialPath ?? ''}>{documents.map((d) => d.path).join(',')}</div>
  ),
}));

const DOCS = [
  { path: 'secret-a.html', name: 'Secret A', folder: '' },
  { path: 'secret-b.html', name: 'Secret B', folder: '' },
];

beforeEach(() => {
  window.localStorage.clear();
});

afterEach(() => {
  vi.restoreAllMocks();
  fetchCollectionListMock.mockReset();
});

test('initial render shows password form and fetchCollectionList is NOT called', () => {
  render(<CollectionPasswordGate collection="private" code="1111" />);

  expect(screen.getByRole('button', { name: '확인' })).toBeInTheDocument();
  expect(screen.getByLabelText('비밀번호')).toBeInTheDocument();
  expect(fetchCollectionListMock.mock.calls.length).toBe(0);
});

test('focuses the password input immediately on the locked screen', () => {
  render(<CollectionPasswordGate collection="private" code="1111" />);

  expect(screen.getByLabelText('비밀번호')).toHaveFocus();
});

test('wrong code shows error and fetchCollectionList is still NOT called', () => {
  render(<CollectionPasswordGate collection="private" code="1111" />);

  fireEvent.change(screen.getByLabelText('비밀번호'), { target: { value: '1234' } });
  fireEvent.click(screen.getByRole('button', { name: '확인' }));

  expect(screen.getByRole('alert')).toHaveTextContent('비밀번호가 올바르지 않습니다.');
  expect(fetchCollectionListMock.mock.calls.length).toBe(0);
});

test('correct code unlocks: fetchCollectionList called with the collection and workspace renders', async () => {
  fetchCollectionListMock.mockResolvedValue({ documents: DOCS });

  render(<CollectionPasswordGate collection="private" code="1111" />);

  fireEvent.change(screen.getByLabelText('비밀번호'), { target: { value: '1111' } });
  fireEvent.click(screen.getByRole('button', { name: '확인' }));

  await waitFor(() =>
    expect(fetchCollectionListMock).toHaveBeenCalledWith('private'),
  );
  expect(fetchCollectionListMock).toHaveBeenCalledTimes(1);

  const stub = await screen.findByTestId('documents-workspace-stub');
  expect(stub).toHaveTextContent('secret-a.html,secret-b.html');
});

test('initialPath is hidden while locked and forwarded only after unlock', async () => {
  fetchCollectionListMock.mockResolvedValue({ documents: DOCS });

  render(<CollectionPasswordGate collection="private" code="1111" initialPath="secret-b.html" />);

  expect(screen.queryByText('secret-b.html')).not.toBeInTheDocument();
  expect(fetchCollectionListMock).not.toHaveBeenCalled();

  fireEvent.change(screen.getByLabelText('비밀번호'), { target: { value: '1111' } });
  fireEvent.click(screen.getByRole('button', { name: '확인' }));

  const stub = await screen.findByTestId('documents-workspace-stub');
  expect(stub).toHaveAttribute('data-initial-path', 'secret-b.html');
});

test('stored unlock keeps a gated collection usable after reload or hash navigation', async () => {
  fetchCollectionListMock.mockResolvedValue({ documents: DOCS });
  window.localStorage.setItem('aeroone.collection.private.unlocked', '1');

  render(<CollectionPasswordGate collection="private" code="1111" />);

  await waitFor(() =>
    expect(fetchCollectionListMock).toHaveBeenCalledWith('private'),
  );
  expect(screen.queryByLabelText('비밀번호')).not.toBeInTheDocument();
  expect(await screen.findByTestId('documents-workspace-stub')).toHaveTextContent('secret-a.html');
});

test('unlocked collection shows status and can be locked again', async () => {
  fetchCollectionListMock.mockResolvedValue({ documents: DOCS });
  window.localStorage.setItem('aeroone.collection.private.unlocked', '1');

  render(<CollectionPasswordGate collection="private" title="Private" code="1111" />);

  expect(await screen.findByText('Private 잠금 해제됨')).toBeInTheDocument();

  fireEvent.click(screen.getByTestId('collection-gate-lock'));

  expect(screen.getByLabelText('비밀번호')).toBeInTheDocument();
  expect(window.localStorage.getItem('aeroone.collection.private.unlocked')).toBeNull();
});
