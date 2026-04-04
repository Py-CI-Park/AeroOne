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
    expect(screen.getByTestId('newsletter-pdf-fallback')).toBeInTheDocument();
  });

  expect(screen.getByRole('link', { name: /PDF/ })).toHaveAttribute(
    'href',
    '/api/frontend/newsletters/1/download/pdf',
  );
});
