import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

import { DocumentsWorkspace } from '@/components/documents/documents-workspace';

const { fetchCollectionContentMock } = vi.hoisted(() => ({
  fetchCollectionContentMock: vi.fn(),
}));

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return { ...actual, fetchCollectionContent: fetchCollectionContentMock };
});

// HtmlViewer 는 iframe + observer 라 단위 테스트에서는 단순 div 로 대체(선택 본문 주입만 확인).
vi.mock('@/components/newsletter/html-viewer', () => ({
  HtmlViewer: ({
    title,
    html,
    downloadHref,
    onDownload,
  }: {
    title: string;
    html: string;
    downloadHref?: string;
    onDownload?: () => void;
  }) => (
    <div data-testid="doc-html" data-title={title}>
      <a href={downloadHref} download data-testid="html-viewer-download" onClick={onDownload}>
        HTML 다운로드
      </a>
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
  fetchCollectionContentMock.mockImplementation((collection: string, path: string) =>
    Promise.resolve({ asset_type: 'html', content_html: `<p>${path}</p>` }),
  );
  window.localStorage.clear();
});

afterEach(() => {
  vi.restoreAllMocks();
  fetchCollectionContentMock.mockReset();
});

test('default render: sidebar collapsed — tree hidden, select visible', async () => {
  render(<DocumentsWorkspace documents={DOCS} />);

  // 기본 접힘: 좌측 트리 없음, 상단 셀렉트 있음.
  expect(screen.queryByTestId('documents-tree')).not.toBeInTheDocument();
  expect(screen.getByTestId('documents-select')).toBeInTheDocument();

  // 첫 번째 문서 자동 선택 + 본문 로드 확인.
  await waitFor(() =>
    expect(fetchCollectionContentMock).toHaveBeenCalledWith('document', '회사소개.html'),
  );
  const viewer = await screen.findByTestId('doc-html');
  expect(viewer).toHaveTextContent('<p>회사소개.html</p>');
  expect(viewer).toHaveAttribute('data-title', '회사소개');
});

test('renders download links for the viewer and tree items', async () => {
  render(<DocumentsWorkspace documents={DOCS} />);
  await waitFor(() => expect(fetchCollectionContentMock).toHaveBeenCalledWith('document', '회사소개.html'));

  expect(screen.queryByTestId('documents-selected-download')).not.toBeInTheDocument();
  expect(screen.getByTestId('html-viewer-download')).toHaveAttribute(
    'href',
    '/api/frontend/collections/document/download/html?path=%ED%9A%8C%EC%82%AC%EC%86%8C%EA%B0%9C.html',
  );
  expect(screen.getByTestId('html-viewer-download')).toHaveTextContent('HTML 다운로드');

  fireEvent.click(screen.getByTestId('documents-sidebar-toggle'));
  fireEvent.click(screen.getByTestId('doc-folder-항공'));

  expect(screen.getByTestId('doc-download-항공/상용기.html')).toHaveAttribute(
    'href',
    '/api/frontend/collections/document/download/html?path=%ED%95%AD%EA%B3%B5%2F%EC%83%81%EC%9A%A9%EA%B8%B0.html',
  );
});

test('filters documents by file name or folder and shows result count', async () => {
  render(<DocumentsWorkspace documents={DOCS} />);
  await waitFor(() => expect(fetchCollectionContentMock).toHaveBeenCalledWith('document', '회사소개.html'));

  fireEvent.change(screen.getByTestId('documents-search'), { target: { value: '엔진' } });

  expect(screen.getByTestId('documents-search-count')).toHaveTextContent('1/3개 표시');
  expect(screen.getByRole('option', { name: '엔진' })).toBeInTheDocument();
  expect(screen.queryByRole('option', { name: '회사소개' })).not.toBeInTheDocument();
});

test('restores the recent document for the collection and updates it on selection', async () => {
  window.localStorage.setItem('aeroone.collection.document.recentDocument', '항공/엔진.html');

  render(<DocumentsWorkspace documents={DOCS} />);

  await waitFor(() =>
    expect(fetchCollectionContentMock).toHaveBeenCalledWith('document', '항공/엔진.html'),
  );

  fireEvent.change(screen.getByTestId('documents-select'), { target: { value: '회사소개.html' } });

  await waitFor(() =>
    expect(window.localStorage.getItem('aeroone.collection.document.recentDocument')).toBe('회사소개.html'),
  );
});

test('initialPath takes priority over recent document and selects linked file', async () => {
  window.localStorage.setItem('aeroone.collection.document.recentDocument', '항공/엔진.html');

  render(<DocumentsWorkspace documents={DOCS} initialPath="항공/상용기.html" />);

  await waitFor(() =>
    expect(fetchCollectionContentMock).toHaveBeenCalledWith('document', '항공/상용기.html'),
  );
  expect(screen.getByTestId('documents-select')).toHaveValue('항공/상용기.html');
});

test('viewer download announces the file being downloaded', async () => {
  render(<DocumentsWorkspace documents={DOCS} />);
  await waitFor(() => expect(fetchCollectionContentMock).toHaveBeenCalledWith('document', '회사소개.html'));

  const downloadLink = screen.getByTestId('html-viewer-download');
  downloadLink.addEventListener('click', (event) => event.preventDefault());
  fireEvent.click(downloadLink);

  expect(screen.getByTestId('documents-download-notice')).toHaveTextContent('회사소개 다운로드를 시작했습니다.');
});

test('clicking sidebar toggle shows the tree; folders are collapsed by default', async () => {
  render(<DocumentsWorkspace documents={DOCS} />);
  await waitFor(() => expect(fetchCollectionContentMock).toHaveBeenCalled());

  // 토글 클릭 → 트리 표시.
  fireEvent.click(screen.getByTestId('documents-sidebar-toggle'));
  expect(screen.getByTestId('documents-tree')).toBeInTheDocument();

  // 폴더 버튼 자체는 보이지만(이름 표시), 하위 문서들은 기본 접힘이라 보이지 않는다.
  expect(screen.getByTestId('doc-folder-항공')).toBeInTheDocument();
  expect(screen.queryByTestId('doc-item-항공/상용기.html')).not.toBeInTheDocument();
  expect(screen.queryByTestId('doc-item-항공/엔진.html')).not.toBeInTheDocument();

  // 루트 문서는 폴더 없이 바로 보인다.
  expect(screen.getByTestId('doc-item-회사소개.html')).toBeInTheDocument();
});

test('expanding a folder reveals its documents', async () => {
  render(<DocumentsWorkspace documents={DOCS} />);
  await waitFor(() => expect(fetchCollectionContentMock).toHaveBeenCalled());

  // 트리 열기.
  fireEvent.click(screen.getByTestId('documents-sidebar-toggle'));

  // 폴더 접힘 상태 → 클릭으로 펼침.
  expect(screen.queryByTestId('doc-item-항공/상용기.html')).not.toBeInTheDocument();
  fireEvent.click(screen.getByTestId('doc-folder-항공'));
  expect(screen.getByTestId('doc-item-항공/상용기.html')).toBeInTheDocument();
  expect(screen.getByTestId('doc-item-항공/엔진.html')).toBeInTheDocument();
});

test('collapsing a folder hides its documents', async () => {
  render(<DocumentsWorkspace documents={DOCS} />);
  await waitFor(() => expect(fetchCollectionContentMock).toHaveBeenCalled());

  // 트리 열기 후 폴더 펼침.
  fireEvent.click(screen.getByTestId('documents-sidebar-toggle'));
  fireEvent.click(screen.getByTestId('doc-folder-항공'));
  expect(screen.getByTestId('doc-item-항공/상용기.html')).toBeInTheDocument();

  // 다시 접으면 하위 문서 숨김.
  fireEvent.click(screen.getByTestId('doc-folder-항공'));
  expect(screen.queryByTestId('doc-item-항공/상용기.html')).not.toBeInTheDocument();

  // 루트 문서는 무관하게 보인다.
  expect(screen.getByTestId('doc-item-회사소개.html')).toBeInTheDocument();
});

test('loads a different document when clicked in the tree', async () => {
  render(<DocumentsWorkspace documents={DOCS} />);
  await waitFor(() => expect(fetchCollectionContentMock).toHaveBeenCalledWith('document', '회사소개.html'));

  // 트리 열고 폴더 펼쳐서 아이템 클릭.
  fireEvent.click(screen.getByTestId('documents-sidebar-toggle'));
  fireEvent.click(screen.getByTestId('doc-folder-항공'));
  fireEvent.click(screen.getByTestId('doc-item-항공/상용기.html'));

  await waitFor(() =>
    expect(fetchCollectionContentMock).toHaveBeenCalledWith('document', '항공/상용기.html'),
  );
  await waitFor(() =>
    expect(screen.getByTestId('doc-html')).toHaveTextContent('<p>항공/상용기.html</p>'),
  );
});

test('selecting from the top selector loads that document', async () => {
  render(<DocumentsWorkspace documents={DOCS} />);
  await waitFor(() => expect(fetchCollectionContentMock).toHaveBeenCalledWith('document', '회사소개.html'));

  // 기본 접힘이므로 셀렉트가 이미 보임.
  fireEvent.change(screen.getByTestId('documents-select'), { target: { value: '항공/엔진.html' } });

  await waitFor(() =>
    expect(fetchCollectionContentMock).toHaveBeenCalledWith('document', '항공/엔진.html'),
  );
  await waitFor(() =>
    expect(screen.getByTestId('doc-html')).toHaveTextContent('<p>항공/엔진.html</p>'),
  );
});

test('collection prop is forwarded to fetchCollectionContent', async () => {
  render(<DocumentsWorkspace documents={DOCS} collection="civil" />);

  await waitFor(() =>
    expect(fetchCollectionContentMock).toHaveBeenCalledWith('civil', '회사소개.html'),
  );
});

test('expanding sidebar and re-collapsing restores select', async () => {
  render(<DocumentsWorkspace documents={DOCS} />);
  await waitFor(() => expect(fetchCollectionContentMock).toHaveBeenCalled());

  // 기본: 셀렉트 보임, 트리 없음.
  expect(screen.getByTestId('documents-select')).toBeInTheDocument();
  expect(screen.queryByTestId('documents-tree')).not.toBeInTheDocument();

  // 펼치면 트리, 셀렉트 숨김.
  fireEvent.click(screen.getByTestId('documents-sidebar-toggle'));
  expect(screen.getByTestId('documents-tree')).toBeInTheDocument();
  expect(screen.queryByTestId('documents-select')).not.toBeInTheDocument();

  // 다시 접으면 원래대로.
  fireEvent.click(screen.getByTestId('documents-sidebar-toggle'));
  expect(screen.queryByTestId('documents-tree')).not.toBeInTheDocument();
  expect(screen.getByTestId('documents-select')).toBeInTheDocument();
});
