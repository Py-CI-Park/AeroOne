'use client';

import Link from 'next/link';
import React, { useMemo, useState } from 'react';

import { NewsletterDateCalendar } from '@/components/newsletter/newsletter-date-calendar';
import { NewsletterDetailClient } from '@/components/newsletter/newsletter-detail-client';
import { ReadBeacon } from '@/components/newsletter/read-beacon';
import { ScrollToTop } from '@/components/ui/scroll-to-top';
import type { NewsletterTheme } from '@/lib/theme';
import type { NewsletterCalendarEntry, NewsletterDetail } from '@/lib/types';

// 달력 엔트리에서 현재 이슈의 이전(더 과거)/다음(더 최신) 이슈를 찾는다.
// 엔트리는 슬러그당 1건으로 date 기준 정렬해 사용하며, 현재 슬러그가 달력에 없으면 내비를 숨긴다.
export function resolveAdjacentIssues(
  entries: NewsletterCalendarEntry[],
  currentSlug: string,
): { previous: NewsletterCalendarEntry | null; next: NewsletterCalendarEntry | null } {
  const seen = new Set<string>();
  const ordered = [...entries]
    .sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : a.slug.localeCompare(b.slug)))
    .filter((entry) => {
      if (seen.has(entry.slug)) return false;
      seen.add(entry.slug);
      return true;
    });
  const index = ordered.findIndex((entry) => entry.slug === currentSlug);
  if (index === -1) {
    return { previous: null, next: null };
  }
  return {
    previous: index > 0 ? ordered[index - 1] : null,
    next: index < ordered.length - 1 ? ordered[index + 1] : null,
  };
}

// /newsletters 리딩 뷰 — 좌: 펼친 달력 / 우: 선택(또는 최신) 이슈 HTML 직접.
export function NewslettersReading({
  newsletter,
  initialContentHtml = '',
  calendarEntries,
  theme = 'light',
}: {
  newsletter: NewsletterDetail;
  initialContentHtml?: string;
  calendarEntries: NewsletterCalendarEntry[];
  theme?: NewsletterTheme;
}) {
  const [calendarOpen, setCalendarOpen] = useState(true);
  const { previous, next } = useMemo(
    () => resolveAdjacentIssues(calendarEntries, newsletter.slug),
    [calendarEntries, newsletter.slug],
  );
  const gridClassName =
    calendarEntries.length === 0
      ? 'grid gap-5'
      : `grid gap-5 ${calendarOpen ? 'lg:grid-cols-[300px_minmax(0,1fr)]' : 'lg:grid-cols-[max-content_minmax(0,1fr)]'}`;

  return (
    <div data-testid="newsletters-reading" data-calendar-open={calendarOpen} className={gridClassName}>
      {/* 읽음 비콘 — 독자 브라우저가 백엔드를 직접 호출해 접속 IP 를 기록(렌더 출력 없음) */}
      <ReadBeacon newsletterId={newsletter.id} />

      {/* 좌측 — 달력(기본 펼침) */}
      <aside className={`flex flex-col gap-3 ${calendarOpen ? '' : 'lg:w-max'}`}>
        {calendarEntries.length > 0 ? (
          <section data-testid="newsletters-calendar-panel">
            <NewsletterDateCalendar
              entries={calendarEntries}
              selectedSlug={newsletter.slug}
              theme={theme}
              defaultOpen
              open={calendarOpen}
              onOpenChange={setCalendarOpen}
            />
          </section>
        ) : null}
      </aside>

      {/* 우측 — 헤더 없이 이슈 HTML 본문을 곧바로 렌더 */}
      <section className="min-w-0">
        <NewsletterDetailClient
          newsletter={newsletter}
          selectedAsset={newsletter.default_asset_type}
          initialContentHtml={initialContentHtml}
        />
        {previous || next ? (
          <nav
            data-testid="newsletter-issue-nav"
            aria-label="이슈 이동"
            className="mt-4 flex items-center justify-between gap-3 border-t border-line-subtle pt-3 text-sm"
          >
            {previous ? (
              <Link
                data-testid="newsletter-issue-prev"
                href={`/newsletters/${encodeURIComponent(previous.slug)}?theme=${theme}`}
                className="min-w-0 max-w-[48%] truncate text-ink-2 transition-colors hover:text-ink-1"
                title={`이전 이슈 — ${previous.title} (${previous.date})`}
              >
                ← 이전 이슈 · {previous.title}
              </Link>
            ) : (
              <span />
            )}
            {next ? (
              <Link
                data-testid="newsletter-issue-next"
                href={`/newsletters/${encodeURIComponent(next.slug)}?theme=${theme}`}
                className="min-w-0 max-w-[48%] truncate text-right text-ink-2 transition-colors hover:text-ink-1"
                title={`다음 이슈 — ${next.title} (${next.date})`}
              >
                다음 이슈 · {next.title} →
              </Link>
            ) : (
              <span />
            )}
          </nav>
        ) : null}
      </section>

      <ScrollToTop />
    </div>
  );
}
