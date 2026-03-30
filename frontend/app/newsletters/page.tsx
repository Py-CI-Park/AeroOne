import { AppShell } from '@/components/layout/app-shell';
import { NewsletterDateCalendar } from '@/components/newsletter/newsletter-date-calendar';
import { NewsletterDetailClient } from '@/components/newsletter/newsletter-detail-client';
import { NewsletterFilterBar } from '@/components/newsletter/newsletter-filter-bar';
import { NewsletterList } from '@/components/newsletter/newsletter-list';
import { NewsletterRecentList } from '@/components/newsletter/newsletter-recent-list';
import { fetchLatestNewsletter, fetchNewsletterCalendar, fetchNewsletterDetail, fetchNewsletters, getServerApiBase } from '@/lib/api';
import type { AssetType, NewsletterCalendarEntry, NewsletterDetail, NewsletterItem, SourceType } from '@/lib/types';

export const dynamic = 'force-dynamic';

type SearchParams = {
  slug?: string;
  q?: string;
  category?: string;
  tag?: string;
  source_type?: SourceType;
};

function uniqueCategories(items: NewsletterItem[]) {
  const map = new Map<string, { slug: string; name: string }>();
  for (const item of items) {
    if (item.category) {
      map.set(item.category.slug, { slug: item.category.slug, name: item.category.name });
    }
  }
  return [...map.values()].sort((left, right) => left.name.localeCompare(right.name, 'ko-KR'));
}

function uniqueTags(items: NewsletterItem[]) {
  const map = new Map<string, { slug: string; name: string }>();
  for (const item of items) {
    for (const tag of item.tags) {
      map.set(tag.slug, { slug: tag.slug, name: tag.name });
    }
  }
  return [...map.values()].sort((left, right) => left.name.localeCompare(right.name, 'ko-KR'));
}

export default async function NewslettersPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const params = await searchParams;
  let detail: NewsletterDetail | null = null;
  let items: NewsletterItem[] = [];
  let allItems: NewsletterItem[] = [];
  let calendarEntries: NewsletterCalendarEntry[] = [];
  let initialContentHtml = '';
  let errorMessage = '';

  try {
    const filters: Record<string, string> = {};
    if (params.q) filters.q = params.q;
    if (params.category) filters.category = params.category;
    if (params.tag) filters.tag = params.tag;
    if (params.source_type) filters.source_type = params.source_type;

    [allItems, items, calendarEntries] = await Promise.all([
      fetchNewsletters(),
      fetchNewsletters(Object.keys(filters).length > 0 ? filters : undefined),
      fetchNewsletterCalendar(),
    ]);

    if (params.slug) {
      detail = await fetchNewsletterDetail(params.slug);
    } else if (items.length > 0 && Object.keys(filters).length > 0) {
      detail = await fetchNewsletterDetail(items[0].slug);
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
      <div className="mb-6 rounded-2xl bg-gradient-to-r from-slate-900 via-slate-800 to-blue-900 p-6 text-white shadow-lg">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-300">Latest First</p>
        <h2 className="mt-2 text-3xl font-semibold">가장 최신 뉴스레터를 바로 확인하세요</h2>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-200">
          상단 달력에서 발행 날짜를 선택해 과거 뉴스레터로 빠르게 이동할 수 있습니다. 오른쪽 패널에서는 최근 발행 및 검색/필터를 통해 원하는 문서를 좁혀볼 수 있습니다.
        </p>
      </div>

      {errorMessage ? (
        <div className="mb-4 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          뉴스레터 목록을 불러오지 못했습니다. 백엔드 실행 상태와 포트(18437)를 확인해주세요.
          <div className="mt-1 text-xs text-red-600">{errorMessage}</div>
        </div>
      ) : null}

      {detail ? (
        <div className="space-y-6">
          <NewsletterDateCalendar entries={calendarEntries} selectedSlug={detail.slug} />

          <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
            <NewsletterDetailClient newsletter={detail} initialContentHtml={initialContentHtml} />

            <div className="space-y-6">
              <NewsletterRecentList items={allItems} selectedSlug={detail.slug} />
              <NewsletterFilterBar
                current={{
                  q: params.q ?? '',
                  category: params.category ?? '',
                  tag: params.tag ?? '',
                  source_type: params.source_type ?? '',
                }}
                categories={uniqueCategories(allItems)}
                tags={uniqueTags(allItems)}
              />
              {Object.keys({
                ...(params.q ? { q: params.q } : {}),
                ...(params.category ? { category: params.category } : {}),
                ...(params.tag ? { tag: params.tag } : {}),
                ...(params.source_type ? { source_type: params.source_type } : {}),
              }).length > 0 ? (
                <section>
                  <h3 className="mb-3 text-sm font-semibold text-slate-600">검색 결과</h3>
                  <NewsletterList items={items} />
                </section>
              ) : null}
            </div>
          </div>
        </div>
      ) : (
        <NewsletterList items={items} />
      )}
    </AppShell>
  );
}
