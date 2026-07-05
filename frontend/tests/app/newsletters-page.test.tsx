import React from 'react';
import { render, screen, within } from '@testing-library/react';

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

vi.mock('@/components/layout/admin-nav-link', () => ({
  AdminNavLink: () => null,
}));

vi.mock('@/components/newsletter/newsletter-date-calendar', () => ({
  NewsletterDateCalendar: ({
    selectedSlug,
    theme,
    defaultOpen,
  }: {
    selectedSlug?: string;
    theme: string;
    defaultOpen?: boolean;
  }) => (
    <div
      data-testid="newsletter-date-calendar"
      data-selected-slug={selectedSlug}
      data-theme={theme}
      data-default-open={String(Boolean(defaultOpen))}
    />
  ),
}));

vi.mock('@/components/newsletter/newsletter-detail-client', () => ({
  NewsletterDetailClient: ({ newsletter, initialContentHtml }: { newsletter: NewsletterDetail; initialContentHtml?: string }) => (
    <div>
      <div data-testid="newsletter-detail-client">{newsletter.title}</div>
      <div data-testid="newsletter-detail-html">{initialContentHtml ?? ''}</div>
    </div>
  ),
}));

const latest: NewsletterDetail = {
  id: 1,
  title: 'Runway surface treatment results',
  slug: 'runway-surface',
  description: 'Q1 trials',
  source_type: 'html',
  published_at: '2026-05-23T00:00:00',
  category: { id: 1, name: 'Aerospace Daily', slug: 'aerospace-daily' },
  tags: [],
  available_assets: [{ asset_type: 'html', content_url: '/api/v1/newsletters/1/content/html', download_url: '/d', is_primary: true }],
  default_asset_type: 'html',
  summary: 'Summary',
  thumbnail_url: null,
};

const items: NewsletterItem[] = [
  {
    id: 1,
    title: latest.title,
    slug: latest.slug,
    description: latest.description,
    source_type: 'html',
    published_at: '2026-05-23T00:00:00',
    category: { id: 1, name: 'Aerospace Daily', slug: 'aerospace-daily' },
    tags: [],
    available_assets: latest.available_assets,
  },
  {
    id: 2,
    title: 'Supply chain normalizes',
    slug: 'supply-chain',
    description: 'lead times',
    source_type: 'html',
    published_at: '2026-05-22T00:00:00',
    category: { id: 2, name: 'Supply Watch', slug: 'supply' },
    tags: [],
    available_assets: [{ asset_type: 'html', content_url: '/a2', download_url: '/d2', is_primary: true }],
  },
];

const calendarEntries: NewsletterCalendarEntry[] = [
  { date: '2026-05-23', slug: 'runway-surface', title: latest.title, source_type: 'html' },
  { date: '2026-05-22', slug: 'supply-chain', title: items[1].title, source_type: 'html' },
];

beforeEach(() => {
  cookieThemeMock.mockReturnValue(undefined);
  fetchNewslettersMock.mockResolvedValue(items);
  fetchNewsletterCalendarMock.mockResolvedValue(calendarEntries);
  fetchLatestNewsletterMock.mockResolvedValue(latest);
  fetchNewsletterDetailMock.mockResolvedValue(latest);
  fetchNewsletterAssetContentMock.mockResolvedValue({ asset_type: 'html', content_html: '<h1>hello</h1>' });
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

test('defaults to the latest issue, renders its HTML directly, with an expanded calendar and existing categories', async () => {
  render(await NewslettersPage({ searchParams: Promise.resolve({}) }));

  expect(fetchLatestNewsletterMock).toHaveBeenCalled();
  expect(screen.getByRole('heading', { name: 'Newsletter' })).toBeInTheDocument();

  const reading = screen.getByTestId('newsletters-reading');
  // 최신 이슈 HTML 이 본문에 직접 렌더된다.
  expect(within(reading).getByTestId('newsletter-detail-client')).toHaveTextContent(latest.title);
  expect(within(reading).getByTestId('newsletter-detail-html')).toHaveTextContent('<h1>hello</h1>');

  // 달력은 기본 펼침 + 최신 이슈 선택.
  const calendar = screen.getByTestId('newsletter-date-calendar');
  expect(calendar).toHaveAttribute('data-default-open', 'true');
  expect(calendar).toHaveAttribute('data-selected-slug', latest.slug);

  // Categories 패널은 더 이상 렌더하지 않는다.
  expect(screen.queryByTestId('newsletters-category-panel')).not.toBeInTheDocument();
});

test('loads the requested issue when a slug is provided', async () => {
  const supply: NewsletterDetail = {
    ...latest,
    id: 2,
    title: 'Supply chain normalizes',
    slug: 'supply-chain',
    category: { id: 2, name: 'Supply Watch', slug: 'supply' },
    published_at: '2026-05-22T00:00:00',
  };
  fetchNewsletterDetailMock.mockResolvedValue(supply);

  render(await NewslettersPage({ searchParams: Promise.resolve({ slug: 'supply-chain' }) }));

  expect(fetchNewsletterDetailMock).toHaveBeenCalledWith('supply-chain');
  expect(fetchLatestNewsletterMock).not.toHaveBeenCalled();
  expect(screen.getByTestId('newsletter-detail-client')).toHaveTextContent('Supply chain normalizes');
  expect(screen.getByTestId('newsletter-date-calendar')).toHaveAttribute('data-selected-slug', 'supply-chain');
});

test('query theme overrides cookie and env defaults', async () => {
  cookieThemeMock.mockReturnValue('dark');
  vi.stubEnv('NEWSLETTERS_THEME', 'dark');

  render(await NewslettersPage({ searchParams: Promise.resolve({ theme: 'light' }) }));

  // 테마는 <html> 에 부착 — 페이지가 해석한 theme 은 자식(달력)으로 전달돼 확인.
  expect(screen.getByTestId('newsletter-date-calendar')).toHaveAttribute('data-theme', 'light');
  expect(screen.getByRole('link', { name: '다크 테마로 전환' })).toHaveAttribute(
    'href',
    '/theme?theme=dark&next=%2Fnewsletters%3Fslug%3Drunway-surface',
  );
});
