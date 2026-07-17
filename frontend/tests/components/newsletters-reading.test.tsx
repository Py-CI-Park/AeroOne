import React from 'react';
import { render, screen } from '@testing-library/react';

import { NewslettersReading, resolveAdjacentIssues } from '@/components/newsletter/newsletters-reading';
import type { NewsletterCalendarEntry, NewsletterDetail } from '@/lib/types';

vi.mock('@/components/newsletter/newsletter-detail-client', () => ({
  NewsletterDetailClient: () => <div data-testid="detail-client-stub" />,
}));

vi.mock('@/components/newsletter/newsletter-date-calendar', () => ({
  NewsletterDateCalendar: () => <div data-testid="calendar-stub" />,
}));

vi.mock('@/components/newsletter/read-beacon', () => ({
  ReadBeacon: () => null,
}));

vi.mock('@/components/ui/scroll-to-top', () => ({
  ScrollToTop: () => null,
}));

const ENTRIES: NewsletterCalendarEntry[] = [
  { date: '2026-06-04', slug: 'issue-0604', title: '6월 첫 호', source_type: 'html' },
  { date: '2026-06-18', slug: 'issue-0618', title: '6월 둘째 호', source_type: 'html' },
  { date: '2026-07-02', slug: 'issue-0702', title: '7월 첫 호', source_type: 'html' },
];

function detail(slug: string): NewsletterDetail {
  return {
    id: 1,
    title: `뉴스레터 ${slug}`,
    slug,
    status: 'published',
    default_asset_type: 'html',
    available_assets: [],
  } as unknown as NewsletterDetail;
}

test('resolveAdjacentIssues orders by date and returns older/newer neighbors', () => {
  // 입력 순서와 무관하게 date 기준으로 이웃을 찾는다.
  const shuffled = [ENTRIES[2], ENTRIES[0], ENTRIES[1]];
  expect(resolveAdjacentIssues(shuffled, 'issue-0618')).toEqual({
    previous: ENTRIES[0],
    next: ENTRIES[2],
  });
  expect(resolveAdjacentIssues(shuffled, 'issue-0604')).toEqual({ previous: null, next: ENTRIES[1] });
  expect(resolveAdjacentIssues(shuffled, 'issue-0702')).toEqual({ previous: ENTRIES[1], next: null });
});

test('resolveAdjacentIssues hides nav for unknown slug and dedupes repeated slugs', () => {
  expect(resolveAdjacentIssues(ENTRIES, 'missing')).toEqual({ previous: null, next: null });
  // 같은 슬러그가 여러 날짜로 들어와도 이웃 계산은 슬러그당 1건으로 안정.
  const duplicated: NewsletterCalendarEntry[] = [...ENTRIES, { ...ENTRIES[2], date: '2026-07-09', title: '7월 첫 호(재게시)' }];
  expect(resolveAdjacentIssues(duplicated, 'issue-0618').next?.slug).toBe('issue-0702');
});

test('renders prev/next issue links pointing at the neighbor detail pages', () => {
  render(
    <NewslettersReading newsletter={detail('issue-0618')} calendarEntries={ENTRIES} />,
  );

  const nav = screen.getByTestId('newsletter-issue-nav');
  expect(nav).toBeInTheDocument();
  expect(screen.getByTestId('newsletter-issue-prev')).toHaveAttribute('href', '/newsletters/issue-0604');
  expect(screen.getByTestId('newsletter-issue-prev')).toHaveTextContent('이전 이슈 · 6월 첫 호');
  expect(screen.getByTestId('newsletter-issue-next')).toHaveAttribute('href', '/newsletters/issue-0702');
  expect(screen.getByTestId('newsletter-issue-next')).toHaveTextContent('다음 이슈 · 7월 첫 호');
});

test('renders only the available direction at the edges of the archive', () => {
  render(
    <NewslettersReading newsletter={detail('issue-0702')} calendarEntries={ENTRIES} />,
  );

  expect(screen.getByTestId('newsletter-issue-prev')).toBeInTheDocument();
  expect(screen.queryByTestId('newsletter-issue-next')).not.toBeInTheDocument();
});

test('hides the issue nav entirely when the calendar has no entries', () => {
  render(<NewslettersReading newsletter={detail('issue-0618')} calendarEntries={[]} />);

  expect(screen.queryByTestId('newsletter-issue-nav')).not.toBeInTheDocument();
});
