import React from 'react';
import { render, screen } from '@testing-library/react';

import NewslettersPage from '@/app/newsletters/page';
import type { NewsletterCalendarEntry, NewsletterDetail, NewsletterItem } from '@/lib/types';

const {
  fetchLatestNewsletterMock,
  fetchNewsletterCalendarMock,
  fetchNewsletterDetailMock,
  fetchNewslettersMock,
  getServerApiBaseMock,
} = vi.hoisted(() => ({
  fetchLatestNewsletterMock: vi.fn(),
  fetchNewsletterCalendarMock: vi.fn(),
  fetchNewsletterDetailMock: vi.fn(),
  fetchNewslettersMock: vi.fn(),
  getServerApiBaseMock: vi.fn(() => 'http://localhost:18437'),
}));

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return {
    ...actual,
    fetchLatestNewsletter: fetchLatestNewsletterMock,
    fetchNewsletterCalendar: fetchNewsletterCalendarMock,
    fetchNewsletterDetail: fetchNewsletterDetailMock,
    fetchNewsletters: fetchNewslettersMock,
    getServerApiBase: getServerApiBaseMock,
  };
});

vi.mock('@/components/newsletter/newsletter-date-calendar', () => ({
  NewsletterDateCalendar: ({ selectedSlug }: { selectedSlug: string }) => <div data-testid="newsletter-date-calendar">{selectedSlug}</div>,
}));

vi.mock('@/components/newsletter/newsletter-detail-client', () => ({
  NewsletterDetailClient: ({ newsletter }: { newsletter: NewsletterDetail }) => <div data-testid="newsletter-detail-client">{newsletter.title}</div>,
}));

vi.mock('@/components/newsletter/newsletter-list', () => ({
  NewsletterList: ({ items }: { items: NewsletterItem[] }) => <div data-testid="newsletter-list">{items.length}</div>,
}));

const detail: NewsletterDetail = {
  id: 1,
  title: '2026-03-30 뉴스레터',
  slug: 'newsletter-20260330',
  description: '설명',
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
  summary: '요약',
  category: null,
  thumbnail_url: null,
};

const items: NewsletterItem[] = [
  {
    id: 1,
    title: detail.title,
    slug: detail.slug,
    description: detail.description,
    source_type: detail.source_type,
    tags: [],
    available_assets: detail.available_assets,
    category: null,
  },
];

const calendarEntries: NewsletterCalendarEntry[] = [
  {
    date: '2026-03-30',
    slug: detail.slug,
    title: detail.title,
    source_type: detail.source_type,
  },
];

beforeEach(() => {
  fetchLatestNewsletterMock.mockResolvedValue(detail);
  fetchNewsletterCalendarMock.mockResolvedValue(calendarEntries);
  fetchNewsletterDetailMock.mockResolvedValue(detail);
  fetchNewslettersMock.mockImplementation((filters?: Record<string, string>) => Promise.resolve(filters ? items : items));
  vi.spyOn(global, 'fetch').mockResolvedValue({
    ok: true,
    json: async () => ({ asset_type: 'html', content_html: '<h1>hello</h1>' }),
  } as Response);
});

afterEach(() => {
  vi.restoreAllMocks();
  fetchLatestNewsletterMock.mockReset();
  fetchNewsletterCalendarMock.mockReset();
  fetchNewsletterDetailMock.mockReset();
  fetchNewslettersMock.mockReset();
  getServerApiBaseMock.mockClear();
});

test('renders newsletters page without hero copy and quick move section', async () => {
  render(await NewslettersPage({ searchParams: Promise.resolve({}) }));

  expect(screen.getByRole('heading', { name: '뉴스레터 서비스' })).toBeInTheDocument();
  expect(screen.getByTestId('newsletter-date-calendar')).toHaveTextContent(detail.slug);
  expect(screen.getByTestId('newsletter-detail-client')).toHaveTextContent(detail.title);
  expect(screen.queryByText('Latest First')).not.toBeInTheDocument();
  expect(screen.queryByText('가장 최신 뉴스레터를 바로 확인하세요')).not.toBeInTheDocument();
  expect(screen.queryByText('뉴스레터 빠른 이동')).not.toBeInTheDocument();
});
