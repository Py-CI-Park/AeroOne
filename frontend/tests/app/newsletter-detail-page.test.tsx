import React from 'react';
import { render, screen } from '@testing-library/react';

import NewsletterDetailPage from '@/app/newsletters/[slug]/page';
import type { NewsletterDetail } from '@/lib/types';

const {
  fetchNewsletterAssetContentMock,
  fetchNewsletterDetailMock,
} = vi.hoisted(() => ({
  fetchNewsletterAssetContentMock: vi.fn(),
  fetchNewsletterDetailMock: vi.fn(),
}));

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return {
    ...actual,
    fetchNewsletterAssetContent: fetchNewsletterAssetContentMock,
    fetchNewsletterDetail: fetchNewsletterDetailMock,
  };
});

vi.mock('@/components/newsletter/newsletter-detail-client', () => ({
  NewsletterDetailClient: ({ newsletter, initialContentHtml }: { newsletter: NewsletterDetail; initialContentHtml?: string }) => (
    <div>
      <div data-testid="newsletter-detail-client">{newsletter.title}</div>
      <div data-testid="newsletter-detail-html">{initialContentHtml ?? ''}</div>
    </div>
  ),
}));

const detail: NewsletterDetail = {
  id: 1,
  title: 'Newsletter 2026-03-30',
  slug: 'newsletter-20260330',
  description: 'Summary',
  source_type: 'html',
  tags: [],
  available_assets: [
    {
      asset_type: 'html',
      content_url: '/api/v1/newsletters/1/content/html',
      download_url: '/api/v1/newsletters/1/download/html',
      is_primary: true,
    },
  ],
  default_asset_type: 'html',
  summary: 'Summary',
  category: null,
  thumbnail_url: null,
};

beforeEach(() => {
  fetchNewsletterAssetContentMock.mockResolvedValue({ asset_type: 'html', content_html: '<h1>hello</h1>' });
  fetchNewsletterDetailMock.mockResolvedValue(detail);
});

afterEach(() => {
  vi.restoreAllMocks();
  fetchNewsletterAssetContentMock.mockReset();
  fetchNewsletterDetailMock.mockReset();
});

test('renders newsletter detail page when asset html fetch fails', async () => {
  fetchNewsletterAssetContentMock.mockRejectedValueOnce(new Error('asset unavailable'));

  render(await NewsletterDetailPage({ params: Promise.resolve({ slug: detail.slug }) }));

  expect(screen.getByRole('heading', { name: detail.title })).toBeInTheDocument();
  expect(screen.getByTestId('newsletter-detail-client')).toHaveTextContent(detail.title);
  expect(screen.getByTestId('newsletter-detail-html')).toHaveTextContent('');
  expect(screen.queryByText('asset unavailable')).not.toBeInTheDocument();
});
