import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';

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
        title: '테스트 상세',
        slug: 'test-detail',
        description: '설명',
        source_type: 'html',
        thumbnail_url: null,
        category: null,
        tags: [],
        available_assets: [
          { asset_type: 'html', content_url: '/api/v1/newsletters/1/content/html', download_url: '/api/v1/newsletters/1/download/html', is_primary: true },
          { asset_type: 'pdf', content_url: '/api/v1/newsletters/1/content/pdf', download_url: '/api/v1/newsletters/1/download/pdf', is_primary: false },
        ],
        summary: '요약',
        default_asset_type: 'html',
      }}
    />,
  );

  expect(screen.getByRole('button', { name: 'HTML' })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'PDF' })).toBeInTheDocument();
  expect(screen.queryByText('테스트 상세')).not.toBeInTheDocument();
  expect(screen.queryByText('설명')).not.toBeInTheDocument();
});

test('updates rendered html when newsletter slug changes', () => {
  const { rerender } = render(
    <NewsletterDetailClient
      newsletter={{
        id: 1,
        title: '첫 뉴스레터',
        slug: 'newsletter-20260329',
        description: '설명',
        source_type: 'html',
        thumbnail_url: null,
        category: null,
        tags: [],
        available_assets: [
          { asset_type: 'html', content_url: '/api/v1/newsletters/1/content/html', download_url: '/api/v1/newsletters/1/download/html', is_primary: true },
          { asset_type: 'pdf', content_url: '/api/v1/newsletters/1/content/pdf', download_url: '/api/v1/newsletters/1/download/pdf', is_primary: false },
        ],
        summary: '요약',
        default_asset_type: 'html',
      }}
      initialContentHtml="<h1>first</h1>"
    />,
  );

  expect(screen.getByTitle('첫 뉴스레터')).toHaveAttribute('srcdoc', '<h1>first</h1>');

  rerender(
    <NewsletterDetailClient
      newsletter={{
        id: 2,
        title: '둘째 뉴스레터',
        slug: 'newsletter-20260330',
        description: '설명',
        source_type: 'html',
        thumbnail_url: null,
        category: null,
        tags: [],
        available_assets: [
          { asset_type: 'html', content_url: '/api/v1/newsletters/2/content/html', download_url: '/api/v1/newsletters/2/download/html', is_primary: true },
          { asset_type: 'pdf', content_url: '/api/v1/newsletters/2/content/pdf', download_url: '/api/v1/newsletters/2/download/pdf', is_primary: false },
        ],
        summary: '요약',
        default_asset_type: 'html',
      }}
      initialContentHtml="<h1>second</h1>"
    />,
  );

  expect(screen.getByTitle('둘째 뉴스레터')).toHaveAttribute('srcdoc', '<h1>second</h1>');
});

test('shows pdf download-focused panel when pdf tab is selected', () => {
  render(
    <NewsletterDetailClient
      newsletter={{
        id: 1,
        title: 'PDF 뉴스레터',
        slug: 'pdf-newsletter',
        description: '설명',
        source_type: 'html',
        thumbnail_url: null,
        category: null,
        tags: [],
        available_assets: [
          { asset_type: 'html', content_url: '/api/v1/newsletters/1/content/html', download_url: '/api/v1/newsletters/1/download/html', is_primary: true },
          { asset_type: 'pdf', content_url: '/api/v1/newsletters/1/content/pdf', download_url: '/api/v1/newsletters/1/download/pdf', is_primary: false },
        ],
        summary: '요약',
        default_asset_type: 'html',
      }}
      initialContentHtml="<h1>hello</h1>"
    />,
  );

  fireEvent.click(screen.getByRole('button', { name: 'PDF' }));
  expect(screen.getByRole('link', { name: 'PDF 다운로드' })).toBeInTheDocument();
});
