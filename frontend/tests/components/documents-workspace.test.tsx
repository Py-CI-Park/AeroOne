import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

import { DocumentsWorkspace } from '@/components/documents/documents-workspace';

const { fetchContentMock } = vi.hoisted(() => ({
  fetchContentMock: vi.fn(),
}));

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return { ...actual, fetchDocumentContent: fetchContentMock };
});

// HtmlViewer 는 iframe + observer 라 단위 테스트에서는 단순 div 로 대체(선택 본문 주입만 확인).
vi.mock('@/components/newsletter/html-viewer', () => ({
  HtmlViewer: ({ title, html }: { title: string; html: string }) => (
    <div data-testid="doc-html" data-title={title}>
      {html}
    </div>
  ),
}));

const DOCS = [
  { path: '회사소개.html', name: '회사소개', folder: '' },
  { path: '항공/상용기.html', name: '상용기', folder: '항공' },
  { path: '항공/엔진.html', name: '엔진', folder: '항공' },
];

beforeEach(() => {
  fetchContentMock.mockImplementation((path: string) =>
    Promise.resolve({ asset_type: 'html', content_html: `<p>${path}</p>` }),
  );
});

afterEach(() => {
  vi.restoreAllMocks();
  fetchContentMock.mockReset();
});

test('renders folders and documents as a tree', async () => {
  render(<DocumentsWorkspace documents={DOCS} />);

  // 폴더(항공) 토글 + 문서 버튼들이 모두 보인다(기본 펼침).
  expect(screen.getByTestId('doc-folder-항공')).toBeInTheDocument();
  expect(screen.getByTestId('doc-item-항공/상용기.html')).toBeInTheDocument();
  expect(screen.getByTestId('doc-item-항공/엔진.html')).toBeInTheDocument();
  expect(screen.getByTestId('doc-item-회사소개.html')).toBeInTheDocument();

  // 자동 선택 effect 의 비동기 state 갱신을 act 안에서 흘려보낸다.
  await waitFor(() => expect(fetchContentMock).toHaveBeenCalled());
});

test('auto-selects and loads the first document', async () => {
  render(<DocumentsWorkspace documents={DOCS} />);

  await waitFor(() => expect(fetchContentMock).toHaveBeenCalledWith('회사소개.html'));
  const viewer = await screen.findByTestId('doc-html');
  expect(viewer).toHaveTextContent('<p>회사소개.html</p>');
  expect(viewer).toHaveAttribute('data-title', '회사소개');
});

test('loads the document content when another item is selected', async () => {
  render(<DocumentsWorkspace documents={DOCS} />);

  await waitFor(() => expect(fetchContentMock).toHaveBeenCalledWith('회사소개.html'));

  fireEvent.click(screen.getByTestId('doc-item-항공/상용기.html'));

  await waitFor(() => expect(fetchContentMock).toHaveBeenCalledWith('항공/상용기.html'));
  await waitFor(() => expect(screen.getByTestId('doc-html')).toHaveTextContent('<p>항공/상용기.html</p>'));
});

test('collapsing a folder hides its documents', async () => {
  render(<DocumentsWorkspace documents={DOCS} />);

  // 자동 선택 effect 가 끝난 뒤 접기 동작을 검증(act 경고 방지).
  await waitFor(() => expect(fetchContentMock).toHaveBeenCalled());
  expect(screen.getByTestId('doc-item-항공/상용기.html')).toBeInTheDocument();

  fireEvent.click(screen.getByTestId('doc-folder-항공'));

  expect(screen.queryByTestId('doc-item-항공/상용기.html')).not.toBeInTheDocument();
  // 루트 문서는 폴더 접힘과 무관하게 그대로 보인다.
  expect(screen.getByTestId('doc-item-회사소개.html')).toBeInTheDocument();
});

test('collapsing the sidebar hides the tree and shows a top selector', async () => {
  render(<DocumentsWorkspace documents={DOCS} />);
  await waitFor(() => expect(fetchContentMock).toHaveBeenCalled());

  // 기본은 좌측 트리가 보이고 상단 셀렉트는 없다.
  expect(screen.getByTestId('documents-tree')).toBeInTheDocument();
  expect(screen.queryByTestId('documents-select')).not.toBeInTheDocument();

  // 접으면 트리가 사라지고 상단 셀렉트가 나타난다(뷰어가 전체 폭).
  fireEvent.click(screen.getByTestId('documents-sidebar-toggle'));
  expect(screen.queryByTestId('documents-tree')).not.toBeInTheDocument();
  expect(screen.getByTestId('documents-select')).toBeInTheDocument();

  // 다시 펼치면 트리 복귀.
  fireEvent.click(screen.getByTestId('documents-sidebar-toggle'));
  expect(screen.getByTestId('documents-tree')).toBeInTheDocument();
  expect(screen.queryByTestId('documents-select')).not.toBeInTheDocument();
});

test('selecting from the top selector loads that document', async () => {
  render(<DocumentsWorkspace documents={DOCS} />);
  await waitFor(() => expect(fetchContentMock).toHaveBeenCalledWith('회사소개.html'));

  fireEvent.click(screen.getByTestId('documents-sidebar-toggle'));
  fireEvent.change(screen.getByTestId('documents-select'), { target: { value: '항공/엔진.html' } });

  await waitFor(() => expect(fetchContentMock).toHaveBeenCalledWith('항공/엔진.html'));
  await waitFor(() => expect(screen.getByTestId('doc-html')).toHaveTextContent('<p>항공/엔진.html</p>'));
});
