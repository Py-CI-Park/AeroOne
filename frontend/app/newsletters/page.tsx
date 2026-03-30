import React from 'react';
import { AppShell } from '@/components/layout/app-shell';
import { NewsletterDateCalendar } from '@/components/newsletter/newsletter-date-calendar';
import { NewsletterDetailClient } from '@/components/newsletter/newsletter-detail-client';
import { NewsletterList } from '@/components/newsletter/newsletter-list';
import { fetchLatestNewsletter, fetchNewsletterCalendar, fetchNewsletterDetail, fetchNewsletters, getServerApiBase } from '@/lib/api';
import type { AssetType, NewsletterCalendarEntry, NewsletterDetail, NewsletterItem } from '@/lib/types';

export const dynamic = 'force-dynamic';

type SearchParams = {
  slug?: string;
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
      const asset = activeDetail.available_assets.find((item) => item.asset_type === activeDetail.default_asset_type);
      if (asset) {
        const response = await fetch(`${getServerApiBase()}${asset.content_url}`, { cache: 'no-store' });
        if (response.ok) {
          const payload = (await response.json()) as { asset_type: AssetType; content_html: string };
          initialContentHtml = payload.content_html;
        }
      }
    }
  } catch (error) {
    errorMessage = error instanceof Error ? error.message : '뉴스레터 목록을 불러오지 못했습니다.';
  }

  return (
    <AppShell title="뉴스레터 서비스">
      {errorMessage ? (
        <div className="mb-4 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          뉴스레터 목록을 불러오지 못했습니다. 백엔드 실행 상태와 포트(18437)를 확인해주세요.
          <div className="mt-1 text-xs text-red-600">{errorMessage}</div>
        </div>
      ) : null}

      {detail ? (
        <div className="space-y-6">
          <NewsletterDateCalendar entries={calendarEntries} selectedSlug={detail.slug} />
          <NewsletterDetailClient key={detail.slug} newsletter={detail} initialContentHtml={initialContentHtml} />
        </div>
      ) : (
        <NewsletterList items={fallbackItems} />
      )}
    </AppShell>
  );
}
