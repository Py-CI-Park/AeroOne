import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';

import { NewsletterDetailClient } from '@/components/newsletter/newsletter-detail-client';
import type { NewsletterDetail } from '@/lib/types';

const baseNewsletter: NewsletterDetail = {
  id: 1,
  title: 'Preview Newsletter',
  slug: 'preview-newsletter',
  description: 'desc',
  source_type: 'html',
  thumbnail_url: null,
  category: null,
  tags: [],
  available_assets: [
    {
      asset_type: 'html',
      content_url: '/api/v1/newsletters/1/content/html',
      download_url: '/api/v1/newsletters/1/download/html',
      is_primary: true,
    },
    {
      asset_type: 'markdown',
      content_url: '/api/v1/newsletters/1/content/markdown',
      download_url: '/api/v1/newsletters/1/download/markdown',
      is_primary: false,
    },
    {
      asset_type: 'pdf',
      content_url: '/api/v1/newsletters/1/content/pdf',
      download_url: '/api/v1/newsletters/1/download/pdf',
      is_primary: false,
    },
  ],
  summary: 'summary',
  default_asset_type: 'html',
};

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

test('renders html preview when html is selected', () => {
  render(
    <NewsletterDetailClient
      newsletter={baseNewsletter}
      selectedAsset="html"
      initialContentHtml="<h1>hello</h1>"
    />,
  );

  expect(screen.getByTitle(baseNewsletter.title)).toHaveAttribute('srcdoc', '<h1>hello</h1>');
  expect(screen.queryByTestId('newsletter-pdf-fallback')).not.toBeInTheDocument();
});

test('renders fetched markdown preview when markdown is selected', async () => {
  render(
    <NewsletterDetailClient
      newsletter={baseNewsletter}
      selectedAsset="markdown"
      initialContentHtml="<h1>hello</h1>"
    />,
  );

  await waitFor(() => {
    expect(global.fetch).toHaveBeenCalledWith('/api/frontend/newsletters/1/content/markdown');
  });
  expect(await screen.findByText('hello')).toBeInTheDocument();
});

test('updates rendered html when the newsletter slug changes', async () => {
  const { rerender } = render(
    <NewsletterDetailClient
      newsletter={baseNewsletter}
      selectedAsset="html"
      initialContentHtml="<h1>first</h1>"
    />,
  );

  expect(screen.getByTitle(baseNewsletter.title)).toHaveAttribute('srcdoc', '<h1>first</h1>');

  rerender(
    <NewsletterDetailClient
      newsletter={{ ...baseNewsletter, id: 2, slug: 'next-newsletter', title: 'Next Newsletter' }}
      selectedAsset="html"
      initialContentHtml="<h1>second</h1>"
    />,
  );

  await waitFor(() => {
    expect(screen.getByTitle('Next Newsletter')).toHaveAttribute('srcdoc', '<h1>second</h1>');
  });
});

test('keeps the previous content visible when non-pdf asset loading fails', async () => {
  vi.mocked(global.fetch).mockRejectedValueOnce(new Error('upstream unavailable'));
  const errorLog = vi.spyOn(console, 'error').mockImplementation(() => {});

  const { rerender } = render(
    <NewsletterDetailClient
      newsletter={baseNewsletter}
      selectedAsset="html"
      initialContentHtml="<h1>stable html</h1>"
    />,
  );

  rerender(
    <NewsletterDetailClient
      newsletter={baseNewsletter}
      selectedAsset="markdown"
      initialContentHtml="<h1>stable html</h1>"
    />,
  );

  await waitFor(() => {
    expect(errorLog).toHaveBeenCalledWith(
      '[FRONTEND][FETCH] Failed to load newsletter asset /api/frontend/newsletters/1/content/markdown',
      expect.any(Error),
    );
  });
  expect(screen.getByText('stable html')).toBeInTheDocument();
});

test('attempts pdf preview on mount when pdf is selected', async () => {
  render(
    <NewsletterDetailClient newsletter={baseNewsletter} selectedAsset="pdf" initialContentHtml="<h1>hello</h1>" />,
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

test('shows a download fallback when pdf preview fails', async () => {
  const errorLog = vi.spyOn(console, 'error').mockImplementation(() => {});

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
    <NewsletterDetailClient newsletter={baseNewsletter} selectedAsset="pdf" initialContentHtml="<h1>hello</h1>" />,
  );

  await waitFor(() => {
    expect(global.fetch).toHaveBeenCalledWith('/api/frontend/newsletters/1/content/pdf');
  });
  await waitFor(() => {
    expect(screen.getByTestId('newsletter-pdf-fallback')).toBeInTheDocument();
  });
  expect(errorLog).toHaveBeenCalledWith(
    '[FRONTEND][FETCH] Failed to preview newsletter PDF /api/frontend/newsletters/1/content/pdf',
    expect.any(Error),
  );

  expect(screen.getByRole('link', { name: 'Download PDF' })).toHaveAttribute(
    'href',
    '/api/frontend/newsletters/1/download/pdf',
  );
});
