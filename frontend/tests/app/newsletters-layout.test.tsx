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

vi.mock('@/components/newsletter/newsletter-date-calendar', () => ({
  NewsletterDateCalendar: ({ selectedSlug, theme }: { selectedSlug: string; theme: string }) => (
    <div data-testid="newsletter-date-calendar" data-selected-slug={selectedSlug} data-theme={theme} />
  ),
}));

vi.mock('@/components/newsletter/newsletter-detail-client', () => ({
  NewsletterDetailClient: ({ newsletter }: { newsletter: NewsletterDetail }) => (
    <div data-testid="newsletter-detail-client">{newsletter.title}</div>
  ),
}));

const detail: NewsletterDetail = {
  id: 1,
  title: 'Newsletter 2026-03-30',
  slug: 'newsletter-20260330',
  description: 'Summary',
  source_type: 'html',
  tags: [],
  published_at: '2026-03-30T00:00:00Z',
  available_assets: [
    {
      asset_type: 'html',
      content_url: '/api/v1/newsletters/1/content/html',
      download_url: '/api/v1/newsletters/1/download/html',
      is_primary: true,
    },
    {
      asset_type: 'pdf',
      content_url: '/api/v1/newsletters/1/content/pdf',
      download_url: '/api/v1/newsletters/1/download/pdf',
      is_primary: false,
    },
  ],
  default_asset_type: 'html',
  summary: 'Summary',
  category: null,
  thumbnail_url: null,
};

const items: NewsletterItem[] = [{
  id: 1,
  title: detail.title,
  slug: detail.slug,
  description: detail.description,
  source_type: detail.source_type,
  tags: [],
  available_assets: detail.available_assets,
  category: null,
}];

const calendarEntries: NewsletterCalendarEntry[] = [
  { date: '2026-03-31', slug: 'newer-newsletter', title: 'Newer Newsletter', source_type: detail.source_type },
  { date: '2026-03-30', slug: detail.slug, title: detail.title, source_type: detail.source_type },
  { date: '2026-03-29', slug: 'older-newsletter', title: 'Older Newsletter', source_type: detail.source_type },
];

beforeEach(() => {
  cookieThemeMock.mockReturnValue(undefined);
  fetchLatestNewsletterMock.mockResolvedValue(detail);
  fetchNewsletterAssetContentMock.mockResolvedValue({ asset_type: 'html', content_html: '<h1>hello</h1>' });
  fetchNewsletterCalendarMock.mockResolvedValue(calendarEntries);
  fetchNewsletterDetailMock.mockResolvedValue(detail);
  fetchNewslettersMock.mockResolvedValue(items);
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
  cookieThemeMock.mockReset();
  fetchLatestNewsletterMock.mockReset();
  fetchNewsletterAssetContentMock.mockReset();
  fetchNewsletterCalendarMock.mockReset();
  fetchNewsletterDetailMock.mockReset();
  fetchNewslettersMock.mockReset();
});

test('route exposes a report-style top control grid and single nav theme toggle', async () => {
  render(await NewslettersPage({ searchParams: Promise.resolve({}) }));

  const controlGrid = screen.getByTestId('newsletters-control-grid');
  const calendarPanel = screen.getByTestId('newsletters-calendar-panel');
  const formatPanel = screen.getByTestId('newsletters-format-panel');
  const previewPanel = screen.getByTestId('newsletters-preview-panel');
  const calendar = screen.getByTestId('newsletter-date-calendar');
  const detailClient = screen.getByTestId('newsletter-detail-client');
  const darkToggle = screen.getByRole('link', { name: '다크 테마로 전환' });

  expect(screen.getByRole('heading', { name: 'Newsletter' })).toBeInTheDocument();
  expect(screen.getByTestId('newsletter-theme-selector')).toBeInTheDocument();
  expect(darkToggle).toHaveTextContent('☾');
  expect(darkToggle).toHaveAttribute(
    'href',
    '/theme?theme=dark&next=%2Fnewsletters%3Fslug%3Dnewsletter-20260330',
  );
  expect(calendar).toHaveAttribute('data-selected-slug', detail.slug);
  expect(calendar).toHaveAttribute('data-theme', 'light');
  expect(calendarPanel).toContainElement(calendar);
  expect(controlGrid).toContainElement(calendarPanel);
  expect(controlGrid).toContainElement(formatPanel);
  expect(controlGrid).toHaveClass('items-stretch');
  expect(formatPanel).toHaveClass('h-full');
  expect(previewPanel).toContainElement(detailClient);
  expect(within(formatPanel).queryByRole('heading')).not.toBeInTheDocument();
  expect(within(formatPanel).queryByText(/HTML \/ Markdown \/ PDF/)).not.toBeInTheDocument();
  expect(within(formatPanel).queryByText(/미리보기 영역/)).not.toBeInTheDocument();
  expect(controlGrid.compareDocumentPosition(previewPanel) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
});

test('route renders selected issue date and previous next links preserving theme', async () => {
  render(await NewslettersPage({ searchParams: Promise.resolve({ theme: 'dark' }) }));

  expect(screen.getByText('2026-03-30')).toBeInTheDocument();
  expect(screen.getByRole('link', { name: '이전 날짜' })).toHaveAttribute(
    'href',
    '/newsletters?slug=older-newsletter&theme=dark',
  );
  expect(screen.getByRole('link', { name: '다음 날짜' })).toHaveAttribute(
    'href',
    '/newsletters?slug=newer-newsletter&theme=dark',
  );
});

test('query theme overrides cookie and NEWSLETTERS_THEME defaults', async () => {
  cookieThemeMock.mockReturnValue('dark');
  vi.stubEnv('NEWSLETTERS_THEME', 'dark');

  render(await NewslettersPage({ searchParams: Promise.resolve({ theme: 'light' }) }));

  expect(screen.getByTestId('app-shell')).toHaveClass('bg-slate-100');
  expect(screen.getByTestId('newsletters-format-panel')).toHaveClass('bg-white');
  expect(screen.getByRole('link', { name: '다크 테마로 전환' })).toHaveAttribute(
    'href',
    '/theme?theme=dark&next=%2Fnewsletters%3Fslug%3Dnewsletter-20260330',
  );
});
