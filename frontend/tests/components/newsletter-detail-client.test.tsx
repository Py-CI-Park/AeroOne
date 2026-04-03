import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import { NewsletterDetailClient } from '@/components/newsletter/newsletter-detail-client';

beforeEach(() => {
  vi.spyOn(global, 'fetch').mockResolvedValue({
    json: async () => ({ asset_type: 'html', content_html: '<h1>hello</h1>' }),
  } as Response);
});

afterEach(() => {
  vi.restoreAllMocks();
});

test('renders asset switch buttons and file download link', () => {
  render(
    <NewsletterDetailClient
      newsletter={{
        id: 1,
        title: 'Test Detail',
        slug: 'test-detail',
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

  expect(screen.getByRole('button', { name: 'HTML' })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'PDF' })).toBeInTheDocument();
  expect(screen.queryByText('Test Detail')).not.toBeInTheDocument();
  expect(screen.queryByText('desc')).not.toBeInTheDocument();
});

test('updates rendered html when newsletter slug changes', () => {
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

  expect(screen.getByTitle('Second Newsletter')).toHaveAttribute('srcdoc', '<h1>second</h1>');
});

test('shows pdf download-focused panel when pdf tab is selected', () => {
  render(
    <NewsletterDetailClient
      newsletter={{
        id: 1,
        title: 'PDF Newsletter',
        slug: 'pdf-newsletter',
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
  expect(screen.getByRole('link', { name: /PDF/ })).toBeInTheDocument();
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

  expect(global.fetch).toHaveBeenCalledWith('/api/frontend/newsletters/1/content/html');
  await waitFor(() => {
    expect(screen.getByTitle('Proxy Test')).toHaveAttribute('srcdoc', '<h1>hello</h1>');
  });
});

test('uses the frontend newsletter proxy for pdf downloads', () => {
  render(
    <NewsletterDetailClient
      newsletter={{
        id: 1,
        title: 'Proxy PDF',
        slug: 'proxy-pdf',
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

  expect(screen.getByRole('link', { name: /PDF/ })).toHaveAttribute(
    'href',
    '/api/frontend/newsletters/1/download/pdf',
  );
});
