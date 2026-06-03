import React from 'react';

import { NewsletterDateCalendar } from '@/components/newsletter/newsletter-date-calendar';
import { NewsletterDetailClient } from '@/components/newsletter/newsletter-detail-client';
import { ReadBeacon } from '@/components/newsletter/read-beacon';
import { ScrollToTop } from '@/components/ui/scroll-to-top';
import type { NewsletterTheme } from '@/lib/theme';
import type { NewsletterCalendarEntry, NewsletterDetail } from '@/lib/types';

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
  return (
    <div data-testid="newsletters-reading" className="grid gap-5 lg:grid-cols-[300px_minmax(0,1fr)]">
      {/* 읽음 비콘 — 독자 브라우저가 백엔드를 직접 호출해 접속 IP 를 기록(렌더 출력 없음) */}
      <ReadBeacon newsletterId={newsletter.id} />

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

      {/* 우측 — 헤더 없이 이슈 HTML 본문을 곧바로 렌더 */}
      <section className="min-w-0">
        <NewsletterDetailClient
          newsletter={newsletter}
          selectedAsset={newsletter.default_asset_type}
          initialContentHtml={initialContentHtml}
        />
      </section>

      <ScrollToTop />
    </div>
  );
}
