import React from 'react';
import { render, screen } from '@testing-library/react';

import { NewsletterDetailClient } from '@/components/newsletter/newsletter-detail-client';

beforeEach(() => {
  vi.spyOn(global, 'fetch').mockResolvedValue({
    json: async () => ({ asset_type: 'html', content_html: '<h1>hello</h1>' }),
  } as Response);
});

afterEach(() => {
  vi.restoreAllMocks();
});

test('renders asset switch buttons and download link', () => {
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
  expect(screen.getByRole('link', { name: '다운로드' })).toBeInTheDocument();
});
