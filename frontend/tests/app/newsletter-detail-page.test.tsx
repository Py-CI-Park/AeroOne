import React from 'react';
import { render, screen } from '@testing-library/react';

import NewsletterDetailPage from '@/app/newsletters/[slug]/page';
import type { NewsletterCalendarEntry, NewsletterDetail, NewsletterItem } from '@/lib/types';

const {
  cookieThemeMock,
  fetchNewsletterAssetContentMock,
  fetchNewsletterCalendarMock,
  fetchNewsletterDetailMock,
  fetchNewslettersMock,
} = vi.hoisted(() => ({
  cookieThemeMock: vi.fn<() => string | undefined>(),
  fetchNewsletterAssetContentMock: vi.fn(),
  fetchNewsletterCalendarMock: vi.fn(),
  fetchNewsletterDetailMock: vi.fn(),
  fetchNewslettersMock: vi.fn(),
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
    fetchNewsletterCalendar: fetchNewsletterCalendarMock,
    fetchNewsletterDetail: fetchNewsletterDetailMock,
    fetchNewsletters: fetchNewslettersMock,
  };
});

vi.mock('@/components/layout/app-shell', () => ({
  AppShell: ({
    title,
    children,
    theme,
    themePath,
  }: {
    title: string;
    children: React.ReactNode;
    theme?: string;
    themePath?: string;
  }) => (
    <div data-testid="app-shell" data-theme={theme} data-theme-path={themePath}>
      <h1>{title}</h1>
      {children}
    </div>
  ),
}));

vi.mock('@/components/newsletter/newsletters-reading', () => ({
  NewslettersReading: ({
    newsletter,
    initialContentHtml,
    theme,
  }: {
    newsletter: NewsletterDetail;
    initialContentHtml?: string;
    theme?: string;
  }) => (
    <div data-testid="newsletters-reading" data-theme={theme}>
      <div data-testid="reading-title">{newsletter.title}</div>
      <div data-testid="reading-html">{initialContentHtml ?? ''}</div>
    </div>
  ),
}));

const detail: NewsletterDetail = {
  id: 2,
  title: 'Newsletter 2026-03-30',
  slug: 'newsletter-20260330',
  description: 'Summary',
  source_type: 'html',
  tags: [],
  published_at: '2026-03-30T00:00:00',
  available_assets: [
    {
      asset_type: 'html',
      content_url: '/api/v1/newsletters/2/content/html',
      download_url: '/api/v1/newsletters/2/download/html',
      is_primary: true,
    },
  ],
  default_asset_type: 'html',
  summary: 'Summary',
  category: null,
  thumbnail_url: null,
};

const items: NewsletterItem[] = [
  {
    id: 2,
    title: detail.title,
    slug: detail.slug,
    description: 'Summary',
    source_type: 'html',
    published_at: '2026-03-30T00:00:00',
    category: null,
    tags: [],
    available_assets: detail.available_assets,
  },
];

const calendarEntries: NewsletterCalendarEntry[] = [
  { date: '2026-03-30', slug: detail.slug, title: detail.title, source_type: 'html' },
];

beforeEach(() => {
  cookieThemeMock.mockReturnValue(undefined);
  fetchNewsletterAssetContentMock.mockResolvedValue({ asset_type: 'html', content_html: '<h1>hello</h1>' });
  fetchNewsletterCalendarMock.mockResolvedValue(calendarEntries);
  fetchNewsletterDetailMock.mockResolvedValue(detail);
  fetchNewslettersMock.mockResolvedValue(items);
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
  cookieThemeMock.mockReset();
  fetchNewsletterAssetContentMock.mockReset();
  fetchNewsletterCalendarMock.mockReset();
  fetchNewsletterDetailMock.mockReset();
  fetchNewslettersMock.mockReset();
});

test('renders the reading view for the requested slug with its HTML and a canonical theme path', async () => {
  render(await NewsletterDetailPage({
    params: Promise.resolve({ slug: detail.slug }),
    searchParams: Promise.resolve({ theme: 'dark' }),
  }));

  expect(fetchNewsletterDetailMock).toHaveBeenCalledWith(detail.slug);
  expect(screen.getByTestId('app-shell')).toHaveAttribute('data-theme', 'dark');
  expect(screen.getByTestId('app-shell')).toHaveAttribute('data-theme-path', `/newsletters?slug=${detail.slug}`);
  expect(screen.getByTestId('reading-title')).toHaveTextContent(detail.title);
  expect(screen.getByTestId('reading-html')).toHaveTextContent('<h1>hello</h1>');
});

test('keeps the reader stable when the asset html fetch fails', async () => {
  fetchNewsletterAssetContentMock.mockRejectedValueOnce(new Error('asset unavailable'));

  render(await NewsletterDetailPage({
    params: Promise.resolve({ slug: detail.slug }),
    searchParams: Promise.resolve({ theme: 'dark' }),
  }));

  expect(screen.getByTestId('reading-html')).toHaveTextContent('');
  expect(screen.queryByText('asset unavailable')).not.toBeInTheDocument();
});

test('uses cookie theme on the reader when query is absent', async () => {
  cookieThemeMock.mockReturnValue('dark');

  render(await NewsletterDetailPage({
    params: Promise.resolve({ slug: detail.slug }),
    searchParams: Promise.resolve({}),
  }));

  expect(screen.getByTestId('app-shell')).toHaveAttribute('data-theme', 'dark');
  expect(screen.getByTestId('newsletters-reading')).toHaveAttribute('data-theme', 'dark');
});
