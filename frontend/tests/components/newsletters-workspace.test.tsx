import React from 'react';
import { fireEvent, render, screen, within } from '@testing-library/react';

import { NewslettersWorkspace } from '@/components/newsletter/newsletters-workspace';
import type { NewsletterDetail } from '@/lib/types';

vi.mock('@/components/newsletter/newsletter-detail-client', () => ({
  NewsletterDetailClient: ({
    newsletter,
    selectedAsset,
  }: {
    newsletter: NewsletterDetail;
    selectedAsset: string;
  }) => (
    <div data-testid="newsletter-detail-client" data-slug={newsletter.slug} data-selected-asset={selectedAsset}>
      {newsletter.title}
    </div>
  ),
}));

const firstNewsletter: NewsletterDetail = {
  id: 1,
  title: 'First Newsletter',
  slug: 'first-newsletter',
  description: 'desc',
  source_type: 'html',
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
  ],
  default_asset_type: 'html',
  summary: 'summary',
  category: null,
  thumbnail_url: null,
};

const secondNewsletter: NewsletterDetail = {
  id: 2,
  title: 'Second Newsletter',
  slug: 'second-newsletter',
  description: 'desc',
  source_type: 'html',
  tags: [],
  available_assets: [
    {
      asset_type: 'html',
      content_url: '/api/v1/newsletters/2/content/html',
      download_url: '/api/v1/newsletters/2/download/html',
      is_primary: true,
    },
    {
      asset_type: 'markdown',
      content_url: '/api/v1/newsletters/2/content/markdown',
      download_url: '/api/v1/newsletters/2/download/markdown',
      is_primary: false,
    },
  ],
  default_asset_type: 'html',
  summary: 'summary',
  category: null,
  thumbnail_url: null,
};

test('resets the selected asset to the new newsletter default when the newsletter changes', () => {
  const { rerender } = render(
    <NewslettersWorkspace key={firstNewsletter.slug} newsletter={firstNewsletter} initialContentHtml="<h1>first</h1>" />,
  );

  const formatPanel = screen.getByTestId('newsletters-format-panel');
  fireEvent.click(within(formatPanel).getByRole('button', { name: /MARKDOWN/ }));

  expect(within(formatPanel).getByRole('button', { name: /MARKDOWN/ })).toHaveAttribute('aria-pressed', 'true');
  expect(screen.getByTestId('newsletter-detail-client')).toHaveAttribute('data-selected-asset', 'markdown');

  rerender(
    <NewslettersWorkspace
      key={secondNewsletter.slug}
      newsletter={secondNewsletter}
      initialContentHtml="<h1>second</h1>"
    />,
  );

  const rerenderedFormatPanel = screen.getByTestId('newsletters-format-panel');
  expect(within(rerenderedFormatPanel).getByRole('button', { name: /HTML/ })).toHaveAttribute('aria-pressed', 'true');
  expect(within(rerenderedFormatPanel).getByRole('button', { name: /MARKDOWN/ })).toHaveAttribute('aria-pressed', 'false');
  expect(screen.getByTestId('newsletter-detail-client')).toHaveAttribute('data-slug', 'second-newsletter');
  expect(screen.getByTestId('newsletter-detail-client')).toHaveAttribute('data-selected-asset', 'html');
});
