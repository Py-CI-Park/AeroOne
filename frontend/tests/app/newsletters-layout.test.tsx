import React from 'react';
import { render, screen } from '@testing-library/react';

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
  vi.restoreAllMocks();
  fetchLatestNewsletterMock.mockReset();
  fetchNewsletterAssetContentMock.mockReset();
  fetchNewsletterCalendarMock.mockReset();
  fetchNewsletterDetailMock.mockReset();
  fetchNewslettersMock.mockReset();
});

test('renders calendar, format, and preview panels in order', async () => {
  render(await NewslettersPage({ searchParams: Promise.resolve({}) }));

  const calendarPanel = screen.getByTestId('newsletters-calendar-panel');
  const formatPanel = screen.getByTestId('newsletters-format-panel');
  const previewPanel = screen.getByTestId('newsletters-preview-panel');

  expect(calendarPanel.compareDocumentPosition(formatPanel) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(formatPanel.compareDocumentPosition(previewPanel) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
});
