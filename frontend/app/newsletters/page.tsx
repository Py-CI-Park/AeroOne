import React from 'react';

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
import { resolveNewsletterThemeFromSearchParam } from '@/lib/theme';
import type { NewsletterCalendarEntry, NewsletterDetail, NewsletterItem } from '@/lib/types';

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
    errorMessage = error instanceof Error ? error.message : '뉴스레터 목록을 불러오지 못했습니다.';
  }

  const activeDetail = detail;
  const newsletterTheme = resolveNewsletterThemeFromSearchParam(params.theme);

  return (
    <AppShell
      title="뉴스레터 서비스"
      contentClassName="max-w-[1600px]"
      theme={newsletterTheme}
      showThemeSelector
      themeSlug={activeDetail?.slug}
    >
      {errorMessage ? (
        <div className="mb-4 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          뉴스레터 목록을 불러오지 못했습니다. 백엔드 실행 상태와 포트(18437)를 확인해주세요.
          <div className="mt-1 text-xs text-red-600">{errorMessage}</div>
        </div>
      ) : null}

      {activeDetail ? (
        <div>
          <NewslettersWorkspace
            key={activeDetail.slug}
            calendarPanel={(
              <section data-testid="newsletters-calendar-panel">
                <NewsletterDateCalendar entries={calendarEntries} selectedSlug={activeDetail.slug} theme={newsletterTheme} />
              </section>
            )}
            newsletter={activeDetail}
            initialContentHtml={initialContentHtml}
            theme={newsletterTheme}
          />
        </div>
      ) : (
        <NewsletterList items={fallbackItems} />
      )}
    </AppShell>
  );
}
