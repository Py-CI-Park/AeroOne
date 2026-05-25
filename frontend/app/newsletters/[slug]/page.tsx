import React from 'react';
import { cookies } from 'next/headers';

import { AppShell } from '@/components/layout/app-shell';
import { NewslettersReading } from '@/components/newsletter/newsletters-reading';
import { fetchNewsletterAssetContent, fetchNewsletterCalendar, fetchNewsletterDetail } from '@/lib/api';
import { NEWSLETTER_THEME_COOKIE, resolveNewsletterThemeFromSearchParam } from '@/lib/theme';
import type { NewsletterCalendarEntry, NewsletterDetail } from '@/lib/types';

export const dynamic = 'force-dynamic';

function buildDisplayDate(detail: NewsletterDetail, entries: NewsletterCalendarEntry[]) {
  if (detail.published_at) {
    return detail.published_at.slice(0, 10);
  }
  return entries.find((entry) => entry.slug === detail.slug)?.date;
}

export default async function NewsletterDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ slug: string }>;
  searchParams: Promise<{ theme?: string }>;
}) {
  const { slug } = await params;
  const query = await searchParams;
  const detail = await fetchNewsletterDetail(slug);

  let calendarEntries: NewsletterCalendarEntry[] = [];
  try {
    calendarEntries = await fetchNewsletterCalendar();
  } catch {
    calendarEntries = [];
  }

  let initialContentHtml = '';
  if (detail.default_asset_type !== 'pdf') {
    const asset = detail.available_assets.find((item) => item.asset_type === detail.default_asset_type);
    if (asset) {
      try {
        const payload = await fetchNewsletterAssetContent(asset.content_url);
        initialContentHtml = payload.content_html;
      } catch {
        initialContentHtml = '';
      }
    }
  }

  const cookieStore = await cookies();
  const cookieTheme = cookieStore.getAll().find((cookie) => cookie.name === NEWSLETTER_THEME_COOKIE)?.value;
  const newsletterTheme = resolveNewsletterThemeFromSearchParam(query.theme, process.env.NEWSLETTERS_THEME, cookieTheme);

  return (
    <AppShell
      title="Newsletter"
      contentClassName="max-w-[1600px]"
      theme={newsletterTheme}
      showThemeSelector
      themePath={`/newsletters?slug=${detail.slug}`}
      active="newsletters"
    >
      <NewslettersReading
        key={detail.slug}
        newsletter={detail}
        initialContentHtml={initialContentHtml}
        displayDate={buildDisplayDate(detail, calendarEntries)}
        calendarEntries={calendarEntries}
        theme={newsletterTheme}
      />
    </AppShell>
  );
}
