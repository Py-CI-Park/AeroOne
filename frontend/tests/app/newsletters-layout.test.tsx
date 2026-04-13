import React from 'react';
import { render, screen, within } from '@testing-library/react';

import NewslettersPage from '@/app/newsletters/page';
import type { NewsletterCalendarEntry, NewsletterDetail, NewsletterItem } from '@/lib/types';

const {
  fetchLatestNewsletterMock,
  fetchNewsletterAssetContentMock,
  fetchNewsletterCalendarMock,
  fetchNewsletterDetailMock,
  fetchNewslettersMock,
} = vi.hoisted(() => ({
  fetchLatestNewsletterMock: vi.fn(),
  fetchNewsletterAssetContentMock: vi.fn(),
  fetchNewsletterCalendarMock: vi.fn(),
  fetchNewsletterDetailMock: vi.fn(),
  fetchNewslettersMock: vi.fn(),
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
  NewsletterDateCalendar: ({ selectedSlug }: { selectedSlug: string }) => (
    <div data-testid="newsletter-date-calendar" data-selected-slug={selectedSlug} />
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

const calendarEntries: NewsletterCalendarEntry[] = [{
  date: '2026-03-30',
  slug: detail.slug,
  title: detail.title,
  source_type: detail.source_type,
}];

beforeEach(() => {
  fetchLatestNewsletterMock.mockResolvedValue(detail);
  fetchNewsletterAssetContentMock.mockResolvedValue({ asset_type: 'html', content_html: '<h1>hello</h1>' });
  fetchNewsletterCalendarMock.mockResolvedValue(calendarEntries);
  fetchNewsletterDetailMock.mockResolvedValue(detail);
  fetchNewslettersMock.mockResolvedValue(items);
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
  fetchLatestNewsletterMock.mockReset();
  fetchNewsletterAssetContentMock.mockReset();
  fetchNewsletterCalendarMock.mockReset();
  fetchNewsletterDetailMock.mockReset();
  fetchNewslettersMock.mockReset();
});

test('route exposes a report-style top control grid and nav theme selector', async () => {
  render(await NewslettersPage({ searchParams: Promise.resolve({}) }));

  const controlGrid = screen.getByTestId('newsletters-control-grid');
  const calendarPanel = screen.getByTestId('newsletters-calendar-panel');
  const formatPanel = screen.getByTestId('newsletters-format-panel');
  const previewPanel = screen.getByTestId('newsletters-preview-panel');
  const calendar = screen.getByTestId('newsletter-date-calendar');
  const detailClient = screen.getByTestId('newsletter-detail-client');

  expect(screen.getByTestId('newsletter-theme-selector')).toBeInTheDocument();
  expect(screen.queryByText('화면 테마 선택')).not.toBeInTheDocument();
  expect(screen.getByRole('link', { name: '라이트 테마' })).toHaveAttribute(
    'href',
    `/newsletters?slug=${detail.slug}&theme=light`,
  );
  expect(screen.getByRole('link', { name: '다크 테마' })).toHaveAttribute(
    'href',
    `/newsletters?slug=${detail.slug}&theme=dark`,
  );
  expect(calendar).toHaveAttribute('data-selected-slug', detail.slug);
  expect(calendarPanel).toContainElement(calendar);
  expect(controlGrid).toContainElement(calendarPanel);
  expect(controlGrid).toContainElement(formatPanel);
  expect(previewPanel).toContainElement(detailClient);
  expect(within(formatPanel).getByRole('heading', { name: 'HTML / Markdown / PDF 선택' })).toBeInTheDocument();
  expect(controlGrid.compareDocumentPosition(previewPanel) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
});

test('route renders dark theme when NEWSLETTERS_THEME is dark', async () => {
  vi.stubEnv('NEWSLETTERS_THEME', 'dark');

  render(await NewslettersPage({ searchParams: Promise.resolve({}) }));

  expect(screen.getByTestId('app-shell')).toHaveClass('bg-slate-950');
  expect(screen.getByTestId('newsletters-format-panel')).toHaveClass('bg-slate-900/95');
  expect(screen.getByTestId('newsletters-preview-panel')).toHaveClass('bg-slate-900/95');
});

test('query theme overrides NEWSLETTERS_THEME environment default', async () => {
  vi.stubEnv('NEWSLETTERS_THEME', 'dark');

  render(await NewslettersPage({ searchParams: Promise.resolve({ theme: 'light' }) }));

  expect(screen.getByTestId('app-shell')).toHaveClass('bg-slate-100');
  expect(screen.getByTestId('newsletters-format-panel')).toHaveClass('bg-white');
  expect(screen.getByRole('link', { name: '라이트 테마' })).toHaveAttribute('aria-current', 'true');
});
