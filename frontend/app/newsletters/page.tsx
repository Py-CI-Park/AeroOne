import React from 'react';
import { cookies } from 'next/headers';

import { AppShell } from '@/components/layout/app-shell';
import { NewsletterDateCalendar } from '@/components/newsletter/newsletter-date-calendar';
import { NewsletterList } from '@/components/newsletter/newsletter-list';
import { NewslettersWorkspace } from '@/components/newsletter/newsletters-workspace';
import {
  fetchLatestNewsletter,
  fetchNewsletterAssetContent,
  fetchNewsletterCalendar,
  fetchNewsletterDetail,
  fetchNewsletters,
} from '@/lib/api';
import { NEWSLETTER_THEME_COOKIE, resolveNewsletterThemeFromSearchParam } from '@/lib/theme';
import type { NewsletterCalendarEntry, NewsletterDetail, NewsletterItem } from '@/lib/types';

export const dynamic = 'force-dynamic';

type SearchParams = {
  slug?: string;
  theme?: string;
};

function buildIssueDateDisplay(detail: NewsletterDetail | null, entries: NewsletterCalendarEntry[]) {
  if (!detail) {
    return undefined;
  }
  if (detail.published_at) {
    return detail.published_at.slice(0, 10);
  }

  return entries.find((entry) => entry.slug === detail.slug)?.date;
}

function buildDateNavigation(
  detail: NewsletterDetail | null,
  entries: NewsletterCalendarEntry[],
  theme: string,
) {
  if (!detail) {
    return undefined;
  }

  const sortedEntries = [...entries].sort((left, right) => right.date.localeCompare(left.date));
  const index = sortedEntries.findIndex((entry) => entry.slug === detail.slug);
  if (index < 0) {
    return undefined;
  }

  const newer = sortedEntries[index - 1];
  const older = sortedEntries[index + 1];

  return {
    previous: older ? { label: '이전 날짜', href: `/newsletters?slug=${older.slug}&theme=${theme}` } : undefined,
    next: newer ? { label: '다음 날짜', href: `/newsletters?slug=${newer.slug}&theme=${theme}` } : undefined,
  };
}

export default async function NewslettersPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const params = await searchParams;
  let detail: NewsletterDetail | null = null;
  let calendarEntries: NewsletterCalendarEntry[] = [];
  let fallbackItems: NewsletterItem[] = [];
  let initialContentHtml = '';
  let errorMessage = '';

  try {
    [fallbackItems, calendarEntries] = await Promise.all([
      fetchNewsletters(),
      fetchNewsletterCalendar(),
    ]);

    if (params.slug) {
      detail = await fetchNewsletterDetail(params.slug);
    } else {
      detail = await fetchLatestNewsletter();
    }

    if (detail && detail.default_asset_type !== 'pdf') {
      const activeDetail = detail;
      const asset = activeDetail.available_assets.find(
        (item) => item.asset_type === activeDetail.default_asset_type,
      );
      if (asset) {
        try {
          const payload = await fetchNewsletterAssetContent(asset.content_url);
          initialContentHtml = payload.content_html;
        } catch {
          initialContentHtml = '';
        }
      }
    }
  } catch (error) {
    errorMessage = error instanceof Error ? error.message : 'Newsletter 목록을 불러오지 못했습니다.';
  }

  const cookieStore = await cookies();
  const cookieTheme = cookieStore.getAll().find((cookie) => cookie.name === NEWSLETTER_THEME_COOKIE)?.value;
  const activeDetail = detail;
  const newsletterTheme = resolveNewsletterThemeFromSearchParam(params.theme, process.env.NEWSLETTERS_THEME, cookieTheme);
  const themePath = activeDetail?.slug ? `/newsletters?slug=${activeDetail.slug}` : '/newsletters';
  const displayDate = buildIssueDateDisplay(activeDetail, calendarEntries);
  const dateNavigation = buildDateNavigation(activeDetail, calendarEntries, newsletterTheme);

  return (
    <AppShell
      title="Newsletter"
      contentClassName="max-w-[1600px]"
      theme={newsletterTheme}
      showThemeSelector
      themePath={themePath}
    >
      {errorMessage ? (
        <div className="mb-4 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          Newsletter 목록을 불러오지 못했습니다. 백엔드 실행 상태와 포트(18437)를 확인해주세요.
          <div className="mt-1 text-xs text-red-600">{errorMessage}</div>
        </div>
      ) : null}

      {activeDetail ? (
        <div>
          <NewslettersWorkspace
            key={activeDetail.slug}
            calendarPanel={(
              <section data-testid="newsletters-calendar-panel" className="h-full">
                <NewsletterDateCalendar entries={calendarEntries} selectedSlug={activeDetail.slug} theme={newsletterTheme} />
              </section>
            )}
            newsletter={activeDetail}
            initialContentHtml={initialContentHtml}
            displayDate={displayDate}
            dateNavigation={dateNavigation}
            theme={newsletterTheme}
          />
        </div>
      ) : (
        <NewsletterList items={fallbackItems} />
      )}
    </AppShell>
  );
}
