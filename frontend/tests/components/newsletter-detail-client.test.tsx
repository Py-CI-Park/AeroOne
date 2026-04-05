import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import { NewsletterDetailClient } from '@/components/newsletter/newsletter-detail-client';

beforeEach(() => {
  vi.stubGlobal('URL', {
    createObjectURL: vi.fn(() => 'blob:newsletter-pdf-preview'),
    revokeObjectURL: vi.fn(),
  });

  vi.spyOn(global, 'fetch').mockImplementation(async (input: RequestInfo | URL) => {
    const url = String(input);

    if (url.includes('/content/pdf')) {
      return {
        ok: true,
        status: 200,
        blob: async () => new Blob(['pdf'], { type: 'application/pdf' }),
      } as Response;
    }

    return {
      ok: true,
      status: 200,
      json: async () => ({ asset_type: 'html', content_html: '<h1>hello</h1>' }),
    } as Response;
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

test('renders an explicit asset selector panel and preview panel', () => {
  render(
    <NewsletterDetailClient
      newsletter={{
        id: 1,
        title: 'Layout Newsletter',
        slug: 'layout-newsletter',
        description: 'desc',
        source_type: 'html',
        thumbnail_url: null,
        category: null,
        tags: [],
        available_assets: [
          { asset_type: 'html', content_url: '/api/v1/newsletters/1/content/html', download_url: '/api/v1/newsletters/1/download/html', is_primary: true },
          { asset_type: 'markdown', content_url: '/api/v1/newsletters/1/content/markdown', download_url: '/api/v1/newsletters/1/download/markdown', is_primary: false },
          { asset_type: 'pdf', content_url: '/api/v1/newsletters/1/content/pdf', download_url: '/api/v1/newsletters/1/download/pdf', is_primary: false },
        ],
        summary: 'summary',
        default_asset_type: 'html',
      }}
      initialContentHtml="<h1>hello</h1>"
    />,
  );

  expect(screen.getByTestId('newsletter-asset-selector')).toBeInTheDocument();
  expect(screen.getByTestId('newsletter-preview-panel')).toBeInTheDocument();
});

test('updates rendered html when newsletter slug changes', async () => {
  const { rerender } = render(
    <NewsletterDetailClient
      newsletter={{
        id: 1,
        title: 'First Newsletter',
        slug: 'newsletter-20260329',
        description: 'desc',
        source_type: 'html',
        thumbnail_url: null,
        category: null,
        tags: [],
        available_assets: [
          { asset_type: 'html', content_url: '/api/v1/newsletters/1/content/html', download_url: '/api/v1/newsletters/1/download/html', is_primary: true },
          { asset_type: 'pdf', content_url: '/api/v1/newsletters/1/content/pdf', download_url: '/api/v1/newsletters/1/download/pdf', is_primary: false },
        ],
        summary: 'summary',
        default_asset_type: 'html',
      }}
      initialContentHtml="<h1>first</h1>"
    />,
  );

  expect(screen.getByTitle('First Newsletter')).toHaveAttribute('srcdoc', '<h1>first</h1>');

  rerender(
    <NewsletterDetailClient
      newsletter={{
        id: 2,
        title: 'Second Newsletter',
        slug: 'newsletter-20260330',
        description: 'desc',
        source_type: 'html',
        thumbnail_url: null,
        category: null,
        tags: [],
        available_assets: [
          { asset_type: 'html', content_url: '/api/v1/newsletters/2/content/html', download_url: '/api/v1/newsletters/2/download/html', is_primary: true },
          { asset_type: 'pdf', content_url: '/api/v1/newsletters/2/content/pdf', download_url: '/api/v1/newsletters/2/download/pdf', is_primary: false },
        ],
        summary: 'summary',
        default_asset_type: 'html',
      }}
      initialContentHtml="<h1>second</h1>"
    />,
  );

  await waitFor(() => {
    expect(screen.getByTitle('Second Newsletter')).toHaveAttribute('srcdoc', '<h1>second</h1>');
  });
});

test('requests html assets through the frontend newsletter proxy', async () => {
  render(
    <NewsletterDetailClient
      newsletter={{
        id: 1,
        title: 'Proxy Test',
        slug: 'proxy-test',
        description: 'desc',
        source_type: 'html',
        thumbnail_url: null,
        category: null,
        tags: [],
        available_assets: [
          { asset_type: 'html', content_url: '/api/v1/newsletters/1/content/html', download_url: '/api/v1/newsletters/1/download/html', is_primary: true },
          { asset_type: 'pdf', content_url: '/api/v1/newsletters/1/content/pdf', download_url: '/api/v1/newsletters/1/download/pdf', is_primary: false },
        ],
        summary: 'summary',
        default_asset_type: 'pdf',
      }}
    />,
  );

  fireEvent.click(screen.getByRole('button', { name: 'HTML' }));

  await waitFor(() => {
    expect(global.fetch).toHaveBeenCalledWith('/api/frontend/newsletters/1/content/html');
  });
  await waitFor(() => {
    expect(screen.getByTitle('Proxy Test')).toHaveAttribute('srcdoc', '<h1>hello</h1>');
  });
});

test('keeps the previous content visible when non-pdf asset loading fails', async () => {
  vi.mocked(global.fetch).mockRejectedValueOnce(new Error('upstream unavailable'));
  const errorLog = vi.spyOn(console, 'error').mockImplementation(() => {});

  render(
    <NewsletterDetailClient
      newsletter={{
        id: 1,
        title: 'Failure Fallback',
        slug: 'failure-fallback',
        description: 'desc',
        source_type: 'html',
        thumbnail_url: null,
        category: null,
        tags: [],
        available_assets: [
          { asset_type: 'html', content_url: '/api/v1/newsletters/1/content/html', download_url: '/api/v1/newsletters/1/download/html', is_primary: true },
          { asset_type: 'markdown', content_url: '/api/v1/newsletters/1/content/markdown', download_url: '/api/v1/newsletters/1/download/markdown', is_primary: false },
        ],
        summary: 'summary',
        default_asset_type: 'html',
      }}
      initialContentHtml="<h1>stable html</h1>"
    />,
  );

  fireEvent.click(screen.getByRole('button', { name: 'MARKDOWN' }));

  await waitFor(() => {
    expect(errorLog).toHaveBeenCalledWith(
      '[FRONTEND][FETCH] Failed to load newsletter asset /api/frontend/newsletters/1/content/markdown',
      expect.any(Error),
    );
  });
  expect(screen.getByText('stable html')).toBeInTheDocument();
});

test('attempts pdf preview on mount when pdf is the default asset', async () => {
  render(
    <NewsletterDetailClient
      newsletter={{
        id: 1,
        title: 'Default PDF Preview',
        slug: 'default-pdf-preview',
        description: 'desc',
        source_type: 'pdf',
        thumbnail_url: null,
        category: null,
        tags: [],
        available_assets: [
          { asset_type: 'html', content_url: '/api/v1/newsletters/1/content/html', download_url: '/api/v1/newsletters/1/download/html', is_primary: false },
          { asset_type: 'pdf', content_url: '/api/v1/newsletters/1/content/pdf', download_url: '/api/v1/newsletters/1/download/pdf', is_primary: true },
        ],
        summary: 'summary',
        default_asset_type: 'pdf',
      }}
    />,
  );

  await waitFor(() => {
    expect(global.fetch).toHaveBeenCalledWith('/api/frontend/newsletters/1/content/pdf');
  });
  await waitFor(() => {
    expect(
      screen.queryByTitle('PDF viewer') ?? screen.queryByTestId('newsletter-pdf-fallback'),
    ).toBeInTheDocument();
  });
});

test('shows inline pdf preview when pdf tab is selected', async () => {
  render(
    <NewsletterDetailClient
      newsletter={{
        id: 1,
        title: 'PDF Preview',
        slug: 'pdf-preview',
        description: 'desc',
        source_type: 'html',
        thumbnail_url: null,
        category: null,
        tags: [],
        available_assets: [
          { asset_type: 'html', content_url: '/api/v1/newsletters/1/content/html', download_url: '/api/v1/newsletters/1/download/html', is_primary: true },
          { asset_type: 'pdf', content_url: '/api/v1/newsletters/1/content/pdf', download_url: '/api/v1/newsletters/1/download/pdf', is_primary: false },
        ],
        summary: 'summary',
        default_asset_type: 'html',
      }}
      initialContentHtml="<h1>hello</h1>"
    />,
  );

  fireEvent.click(screen.getByRole('button', { name: 'PDF' }));

  await waitFor(() => {
    expect(global.fetch).toHaveBeenCalledWith('/api/frontend/newsletters/1/content/pdf');
  });
  await waitFor(() => {
    expect(screen.getByTitle('PDF viewer')).toHaveAttribute('src', 'blob:newsletter-pdf-preview');
  });
});

test('shows a download fallback when pdf preview fails', async () => {
  vi.mocked(global.fetch).mockImplementation(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes('/content/pdf')) {
      return { ok: false, status: 500 } as Response;
    }
    return {
      ok: true,
      status: 200,
      json: async () => ({ asset_type: 'html', content_html: '<h1>hello</h1>' }),
    } as Response;
  });

  render(
    <NewsletterDetailClient
      newsletter={{
        id: 1,
        title: 'PDF Fallback',
        slug: 'pdf-fallback',
        description: 'desc',
        source_type: 'html',
        thumbnail_url: null,
        category: null,
        tags: [],
        available_assets: [
          { asset_type: 'html', content_url: '/api/v1/newsletters/1/content/html', download_url: '/api/v1/newsletters/1/download/html', is_primary: true },
          { asset_type: 'pdf', content_url: '/api/v1/newsletters/1/content/pdf', download_url: '/api/v1/newsletters/1/download/pdf', is_primary: false },
        ],
        summary: 'summary',
        default_asset_type: 'html',
      }}
      initialContentHtml="<h1>hello</h1>"
    />,
  );

  fireEvent.click(screen.getByRole('button', { name: 'PDF' }));

  await waitFor(() => {
    expect(global.fetch).toHaveBeenCalledWith('/api/frontend/newsletters/1/content/pdf');
  });

  await waitFor(() => {
    expect(screen.getByTestId('newsletter-pdf-fallback')).toBeInTheDocument();
  });

  expect(screen.getByRole('link', { name: /PDF/ })).toHaveAttribute(
    'href',
    '/api/frontend/newsletters/1/download/pdf',
  );
});
