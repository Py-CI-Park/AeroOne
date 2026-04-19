import React from 'react';
import { render, screen } from '@testing-library/react';

import NewsletterDetailPage from '@/app/newsletters/[slug]/page';
import type { NewsletterDetail } from '@/lib/types';

const {
  cookieThemeMock,
  fetchNewsletterAssetContentMock,
  fetchNewsletterDetailMock,
} = vi.hoisted(() => ({
  cookieThemeMock: vi.fn<() => string | undefined>(),
  fetchNewsletterAssetContentMock: vi.fn(),
  fetchNewsletterDetailMock: vi.fn(),
}));

vi.mock('next/headers', () => ({
  cookies: vi.fn(() => ({
    getAll: () => (cookieThemeMock() ? [{ name: 'aeroone_theme', value: cookieThemeMock() }] : []),
  })),
}));

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return {
    ...actual,
    fetchNewsletterAssetContent: fetchNewsletterAssetContentMock,
    fetchNewsletterDetail: fetchNewsletterDetailMock,
  };
});

vi.mock('@/components/layout/app-shell', () => ({
  AppShell: ({
    title,
    children,
    theme,
    showThemeSelector,
    themePath,
  }: {
    title: string;
    children: React.ReactNode;
    theme?: string;
    showThemeSelector?: boolean;
    themePath?: string;
  }) => (
    <div
      data-testid="app-shell"
      data-theme={theme}
      data-show-theme-selector={String(Boolean(showThemeSelector))}
      data-theme-path={themePath}
    >
      <h1>{title}</h1>
      {children}
    </div>
  ),
}));

vi.mock('@/components/newsletter/newsletters-workspace', () => ({
  NewslettersWorkspace: ({
    newsletter,
    initialContentHtml,
    theme,
  }: {
    newsletter: NewsletterDetail;
    initialContentHtml?: string;
    theme?: string;
  }) => (
    <div>
      <div data-testid="newsletters-workspace" data-theme={theme}>{newsletter.title}</div>
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
  cookieThemeMock.mockReturnValue(undefined);
  fetchNewsletterAssetContentMock.mockResolvedValue({ asset_type: 'html', content_html: '<h1>hello</h1>' });
  fetchNewsletterDetailMock.mockResolvedValue(detail);
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
  cookieThemeMock.mockReset();
  fetchNewsletterAssetContentMock.mockReset();
  fetchNewsletterDetailMock.mockReset();
});

test('renders newsletter detail page when asset html fetch fails', async () => {
  fetchNewsletterAssetContentMock.mockRejectedValueOnce(new Error('asset unavailable'));

  render(await NewsletterDetailPage({
    params: Promise.resolve({ slug: detail.slug }),
    searchParams: Promise.resolve({ theme: 'dark' }),
  }));

  expect(screen.getByRole('heading', { name: detail.title })).toBeInTheDocument();
  expect(screen.getByTestId('app-shell')).toHaveAttribute('data-theme', 'dark');
  expect(screen.getByTestId('app-shell')).toHaveAttribute('data-show-theme-selector', 'true');
  expect(screen.getByTestId('app-shell')).toHaveAttribute('data-theme-path', `/newsletters?slug=${detail.slug}`);
  expect(screen.getByTestId('newsletters-workspace')).toHaveTextContent(detail.title);
  expect(screen.getByTestId('newsletter-detail-html')).toHaveTextContent('');
  expect(screen.queryByText('asset unavailable')).not.toBeInTheDocument();
});

test('uses cookie theme on newsletter detail page when query is absent', async () => {
  cookieThemeMock.mockReturnValue('dark');

  render(await NewsletterDetailPage({
    params: Promise.resolve({ slug: detail.slug }),
    searchParams: Promise.resolve({}),
  }));

  expect(screen.getByTestId('app-shell')).toHaveAttribute('data-theme', 'dark');
  expect(screen.getByTestId('newsletters-workspace')).toHaveAttribute('data-theme', 'dark');
});
