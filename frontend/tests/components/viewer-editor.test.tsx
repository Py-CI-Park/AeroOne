import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

import { ViewerEditor, inferDocType } from '@/components/viewer/viewer-editor';

afterEach(() => {
  vi.restoreAllMocks();
});

function loadTextFile(name: string, content: string) {
  const input = screen.getByTestId('viewer-file-input') as HTMLInputElement;
  const file = new File([content], name, { type: 'text/plain' });
  fireEvent.change(input, { target: { files: [file] } });
}

it('infers doc type from the file extension', () => {
  expect(inferDocType('a.md')).toBe('markdown');
  expect(inferDocType('a.markdown')).toBe('markdown');
  expect(inferDocType('a.html')).toBe('html');
  expect(inferDocType('a.htm')).toBe('html');
  expect(inferDocType('a.txt')).toBe('markdown');
});

it('loads a local file then renders sanitized HTML into the preview iframe via the proxy', async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => ({ html: '<p>sanitized</p>' }),
  });
  vi.stubGlobal('fetch', fetchMock);

  render(<ViewerEditor />);

  loadTextFile('note.md', '# hello');

  // FileReader 가 비동기로 textarea 에 내용을 채운다.
  await waitFor(() =>
    expect((screen.getByTestId('viewer-editor') as HTMLTextAreaElement).value).toBe('# hello'),
  );

  fireEvent.click(screen.getByRole('button', { name: '미리보기 렌더' }));

  await waitFor(() =>
    expect(screen.getByTestId('viewer-preview')).toHaveAttribute('srcdoc', '<p>sanitized</p>'),
  );

  // 프록시는 same-origin 상대 경로 + {type, text} 본문만 사용한다(외부 URL 금지).
  expect(fetchMock).toHaveBeenCalledTimes(1);
  const [url, init] = fetchMock.mock.calls[0];
  expect(url).toBe('/api/frontend/render');
  expect(init.method).toBe('POST');
  expect(JSON.parse(init.body)).toEqual({ type: 'markdown', text: '# hello' });

  vi.unstubAllGlobals();
});

it('shows an error when the render proxy returns a malformed payload', async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => ({ html: null }),
  });
  vi.stubGlobal('fetch', fetchMock);

  render(<ViewerEditor />);
  fireEvent.click(screen.getByRole('button', { name: '미리보기 렌더' }));

  expect(await screen.findByTestId('viewer-error')).toHaveTextContent('렌더 응답이 올바르지 않습니다.');
  expect(screen.getByTestId('viewer-preview')).toHaveAttribute('srcdoc', '');

  vi.unstubAllGlobals();
});

it('previews with an EMPTY sandbox so untrusted file scripts cannot execute [AC5]', () => {
  render(<ViewerEditor />);
  const iframe = screen.getByTestId('viewer-preview');
  // 빈 sandbox: allow-scripts/allow-same-origin 둘 다 없어야 한다.
  expect(iframe.getAttribute('sandbox')).toBe('');
  expect(iframe.getAttribute('sandbox')).not.toContain('allow-scripts');
  expect(iframe.getAttribute('sandbox')).not.toContain('allow-same-origin');
});

it('switches the preview into a focused full-width layout', () => {
  render(<ViewerEditor />);

  fireEvent.click(screen.getByRole('button', { name: '미리보기 집중' }));

  expect(screen.getByRole('button', { name: '미리보기 집중' })).toHaveAttribute('aria-pressed', 'true');
  expect(screen.getByTestId('viewer-editor-grid')).toHaveClass('lg:grid-cols-1');
  expect(screen.getByTestId('viewer-editor').closest('label')).toHaveClass('hidden');

  fireEvent.click(screen.getByRole('button', { name: '편집+미리보기' }));

  expect(screen.getByRole('button', { name: '편집+미리보기' })).toHaveAttribute('aria-pressed', 'true');
  expect(screen.getByTestId('viewer-editor-grid')).toHaveClass('lg:grid-cols-2');
});

it('opens fullscreen preview with the same srcDoc and an EMPTY sandbox', async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => ({ html: '<article><h1>safe preview</h1></article>' }),
  });
  vi.stubGlobal('fetch', fetchMock);

  render(<ViewerEditor />);

  loadTextFile('note.html', '<h1>draft</h1>');
  await waitFor(() =>
    expect((screen.getByTestId('viewer-editor') as HTMLTextAreaElement).value).toBe('<h1>draft</h1>'),
  );

  fireEvent.click(screen.getByRole('button', { name: '미리보기 렌더' }));

  await waitFor(() =>
    expect(screen.getByTestId('viewer-preview')).toHaveAttribute(
      'srcdoc',
      '<article><h1>safe preview</h1></article>',
    ),
  );

  fireEvent.click(screen.getByRole('button', { name: '전체화면 미리보기' }));

  const fullscreenPreview = screen.getByTestId('viewer-preview-fullscreen');
  expect(fullscreenPreview).toHaveAttribute('srcdoc', '<article><h1>safe preview</h1></article>');
  expect(fullscreenPreview.getAttribute('sandbox')).toBe('');
  expect(fullscreenPreview.getAttribute('sandbox')).not.toContain('allow-scripts');
  expect(fullscreenPreview.getAttribute('sandbox')).not.toContain('allow-same-origin');

  fireEvent.click(screen.getByRole('button', { name: '닫기' }));
  expect(screen.queryByTestId('viewer-preview-fullscreen')).not.toBeInTheDocument();

  vi.unstubAllGlobals();
});

it('saves the edited text via a Blob download (client-only, no server write)', async () => {
  const createObjectURL = vi.fn((_blob: Blob) => 'blob:viewer-test');
  const revokeObjectURL = vi.fn();
  Object.defineProperty(window.URL, 'createObjectURL', { configurable: true, value: createObjectURL });
  Object.defineProperty(window.URL, 'revokeObjectURL', { configurable: true, value: revokeObjectURL });
  const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});

  render(<ViewerEditor />);
  loadTextFile('note.html', '<h1>edit me</h1>');
  await waitFor(() =>
    expect((screen.getByTestId('viewer-editor') as HTMLTextAreaElement).value).toBe('<h1>edit me</h1>'),
  );

  fireEvent.click(screen.getByRole('button', { name: '저장 (다운로드)' }));

  expect(createObjectURL).toHaveBeenCalledTimes(1);
  const blob = createObjectURL.mock.calls[0][0] as Blob;
  const blobText = await new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsText(blob);
  });
  expect(blobText).toBe('<h1>edit me</h1>');
  expect(clickSpy).toHaveBeenCalled();
  expect(revokeObjectURL).toHaveBeenCalledWith('blob:viewer-test');
});

it('only references the same-origin render proxy (no external/cross-origin URL)', async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => ({ html: '<p>ok</p>' }),
  });
  vi.stubGlobal('fetch', fetchMock);

  render(<ViewerEditor />);
  fireEvent.click(screen.getByRole('button', { name: '미리보기 렌더' }));

  await waitFor(() => expect(fetchMock).toHaveBeenCalled());
  for (const call of fetchMock.mock.calls) {
    const url = String(call[0]);
    expect(url.startsWith('/')).toBe(true);
    expect(url).not.toMatch(/^https?:\/\//);
  }

  vi.unstubAllGlobals();
});
