import React from 'react';

import { NewsletterDateCalendar } from '@/components/newsletter/newsletter-date-calendar';
import { NewsletterDetailClient } from '@/components/newsletter/newsletter-detail-client';
import { Tag } from '@/components/ui/primitives';
import type { NewsletterTheme } from '@/lib/theme';
import type { NewsletterCalendarEntry, NewsletterDetail } from '@/lib/types';

// /newsletters 리딩 뷰 — 좌: 펼친 달력 / 우: 선택(또는 최신) 이슈 HTML 직접.
export function NewslettersReading({
  newsletter,
  initialContentHtml = '',
  displayDate,
  calendarEntries,
  theme = 'light',
}: {
  newsletter: NewsletterDetail;
  initialContentHtml?: string;
  displayDate?: string;
  calendarEntries: NewsletterCalendarEntry[];
  theme?: NewsletterTheme;
}) {
  return (
    <div data-testid="newsletters-reading" className="grid gap-5 lg:grid-cols-[300px_minmax(0,1fr)]">
      {/* 좌측 — 달력(기본 펼침) */}
      <aside className="flex flex-col gap-3">
        {calendarEntries.length > 0 ? (
          <section data-testid="newsletters-calendar-panel">
            <NewsletterDateCalendar
              entries={calendarEntries}
              selectedSlug={newsletter.slug}
              theme={theme}
              defaultOpen
            />
          </section>
        ) : null}
      </aside>

      {/* 우측 — 이슈 메타 + HTML 본문 직접 */}
      <section className="flex min-w-0 flex-col gap-4">
        <div>
          {newsletter.category ? (
            <div className="mb-2">
              <Tag tone="accent">{newsletter.category.name}</Tag>
            </div>
          ) : null}
          <h2 className="text-3xl font-semibold leading-tight tracking-tight text-ink-1">{newsletter.title}</h2>
          {displayDate ? <p className="mt-1.5 font-mono text-sm text-ink-3">{displayDate}</p> : null}
        </div>

        <div className="min-w-0">
          <NewsletterDetailClient
            newsletter={newsletter}
            selectedAsset={newsletter.default_asset_type}
            initialContentHtml={initialContentHtml}
          />
        </div>
      </section>
    </div>
  );
}
