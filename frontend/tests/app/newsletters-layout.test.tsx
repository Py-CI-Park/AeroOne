import React from 'react';
import { render, screen } from '@testing-library/react';

import NewslettersPage from '@/app/newsletters/page';
import type { NewsletterCalendarEntry, NewsletterDetail, NewsletterItem } from '@/lib/types';

const {
  cookieThemeMock,
  fetchLatestNewsletterMock,
  fetchNewsletterAssetContentMock,
  fetchNewsletterCalendarMock,
  fetchNewsletterDetailMock,
  fetchNewslettersMock,
} = vi.hoisted(() => ({
  cookieThemeMock: vi.fn<() => string | undefined>(),
  fetchLatestNewsletterMock: vi.fn(),
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
    fetchLatestNewsletter: fetchLatestNewsletterMock,
    fetchNewsletterAssetContent: fetchNewsletterAssetContentMock,
    fetchNewsletterCalendar: fetchNewsletterCalendarMock,
    fetchNewsletterDetail: fetchNewsletterDetailMock,
    fetchNewsletters: fetchNewslettersMock,
  };
});

vi.mock('@/components/newsletter/newsletter-date-calendar', () => ({
  NewsletterDateCalendar: ({ theme, defaultOpen }: { theme: string; defaultOpen?: boolean }) => (
    <div data-testid="newsletter-date-calendar" data-theme={theme} data-default-open={String(Boolean(defaultOpen))} />
  ),
}));

vi.mock('@/components/newsletter/newsletter-detail-client', () => ({
  NewsletterDetailClient: ({ newsletter }: { newsletter: NewsletterDetail }) => (
    <div data-testid="newsletter-detail-client">{newsletter.title}</div>
  ),
}));

const latest: NewsletterDetail = {
  id: 1,
  title: 'Newsletter 2026-03-30',
  slug: 'newsletter-20260330',
  description: 'Summary',
  source_type: 'html',
  published_at: '2026-03-30T00:00:00',
  category: { id: 1, name: 'Briefing', slug: 'briefing' },
  tags: [],
  available_assets: [{ asset_type: 'html', content_url: '/c', download_url: '/d', is_primary: true }],
  default_asset_type: 'html',
  summary: 'Summary',
  thumbnail_url: null,
};

const items: NewsletterItem[] = [
  {
    id: 1,
    title: latest.title,
    slug: latest.slug,
    description: 'Summary',
    source_type: 'html',
    published_at: '2026-03-30T00:00:00',
    category: { id: 1, name: 'Briefing', slug: 'briefing' },
    tags: [],
    available_assets: latest.available_assets,
  },
];

const calendarEntries: NewsletterCalendarEntry[] = [
  { date: '2026-03-30', slug: latest.slug, title: latest.title, source_type: 'html' },
];

beforeEach(() => {
  cookieThemeMock.mockReturnValue(undefined);
  fetchNewslettersMock.mockResolvedValue(items);
  fetchNewsletterCalendarMock.mockResolvedValue(calendarEntries);
  fetchLatestNewsletterMock.mockResolvedValue(latest);
  fetchNewsletterDetailMock.mockResolvedValue(latest);
  fetchNewsletterAssetContentMock.mockResolvedValue({ asset_type: 'html', content_html: '<h1>hi</h1>' });
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
  cookieThemeMock.mockReset();
  fetchNewslettersMock.mockReset();
  fetchNewsletterCalendarMock.mockReset();
  fetchLatestNewsletterMock.mockReset();
  fetchNewsletterDetailMock.mockReset();
  fetchNewsletterAssetContentMock.mockReset();
});

test('renders the reading view in a token-themed shell with the newsletters nav active and calendar expanded', async () => {
  render(await NewslettersPage({ searchParams: Promise.resolve({}) }));

  expect(screen.getByTestId('newsletters-reading')).toBeInTheDocument();
  expect(screen.getByTestId('newsletter-date-calendar')).toHaveAttribute('data-theme', 'light');
  expect(screen.getByTestId('newsletter-date-calendar')).toHaveAttribute('data-default-open', 'true');

  const nav = screen.getByRole('navigation');
  expect(nav.querySelector('a[aria-current="page"]')?.textContent).toBe('Newsletter');
});

test('query theme overrides cookie and env defaults and reaches the calendar', async () => {
  cookieThemeMock.mockReturnValue('dark');
  vi.stubEnv('NEWSLETTERS_THEME', 'dark');

  render(await NewslettersPage({ searchParams: Promise.resolve({ theme: 'light' }) }));

  expect(screen.getByTestId('newsletter-date-calendar')).toHaveAttribute('data-theme', 'light');
});

test('uses dark cookie theme when no query is provided', async () => {
  cookieThemeMock.mockReturnValue('dark');

  render(await NewslettersPage({ searchParams: Promise.resolve({}) }));

  expect(screen.getByRole('link', { name: '라이트 테마로 전환' })).toBeInTheDocument();
});
