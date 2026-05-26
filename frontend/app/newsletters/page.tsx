import React from 'react';
import { cookies } from 'next/headers';

import { AppShell } from '@/components/layout/app-shell';
import { NewslettersReading } from '@/components/newsletter/newsletters-reading';
import {
  fetchLatestNewsletter,
  fetchNewsletterAssetContent,
  fetchNewsletterCalendar,
  fetchNewsletterDetail,
} from '@/lib/api';
import { NEWSLETTER_THEME_COOKIE, resolveNewsletterThemeFromSearchParam } from '@/lib/theme';
import type { NewsletterCalendarEntry, NewsletterDetail } from '@/lib/types';

export const dynamic = 'force-dynamic';

type SearchParams = {
  slug?: string;
  theme?: string;
};

export default async function NewslettersPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const params = await searchParams;
  let calendarEntries: NewsletterCalendarEntry[] = [];
  let detail: NewsletterDetail | null = null;
  let initialContentHtml = '';
  let errorMessage = '';

  try {
    calendarEntries = await fetchNewsletterCalendar();
    detail = params.slug ? await fetchNewsletterDetail(params.slug) : await fetchLatestNewsletter();

    if (detail && detail.default_asset_type !== 'pdf') {
      const activeDetail = detail;
      const asset = activeDetail.available_assets.find((item) => item.asset_type === activeDetail.default_asset_type);
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
    errorMessage = error instanceof Error ? error.message : 'Newsletter 를 불러오지 못했습니다.';
  }

  const cookieStore = await cookies();
  const cookieTheme = cookieStore.getAll().find((cookie) => cookie.name === NEWSLETTER_THEME_COOKIE)?.value;
  const newsletterTheme = resolveNewsletterThemeFromSearchParam(params.theme, process.env.NEWSLETTERS_THEME, cookieTheme);
  const themePath = detail?.slug ? `/newsletters?slug=${detail.slug}` : '/newsletters';

  return (
    <AppShell
      title="Newsletter"
      contentClassName="max-w-[1600px]"
      theme={newsletterTheme}
      showThemeSelector
      themePath={themePath}
      active="newsletters"
      titleMeta={calendarEntries.length > 0 ? `${calendarEntries.length} issues` : undefined}
    >
      {errorMessage ? (
        <div className="mb-4 rounded-lg border border-danger/40 bg-danger-soft p-4 text-sm text-danger">
          Newsletter 를 불러오지 못했습니다. 백엔드 실행 상태와 포트(18437)를 확인해주세요.
          <div className="mt-1 text-xs">{errorMessage}</div>
        </div>
      ) : null}

      {detail ? (
        <NewslettersReading
          key={detail.slug}
          newsletter={detail}
          initialContentHtml={initialContentHtml}
          calendarEntries={calendarEntries}
          theme={newsletterTheme}
        />
      ) : !errorMessage ? (
        <div className="rounded-lg border border-dashed border-line bg-surface-raised p-8 text-sm text-ink-2">
          표시할 뉴스레터가 없습니다.
          <div className="mt-2 text-xs text-ink-3">
            관리자 화면에서 Import / Sync 를 실행하거나 setup 을 다시 실행해 외부 뉴스레터를 동기화하세요.
          </div>
        </div>
      ) : null}
    </AppShell>
  );
}
