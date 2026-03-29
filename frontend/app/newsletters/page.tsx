import { AppShell } from '@/components/layout/app-shell';
import { NewsletterFilterBar } from '@/components/newsletter/newsletter-filter-bar';
import { NewsletterList } from '@/components/newsletter/newsletter-list';
import { fetchNewsletters } from '@/lib/api';
import type { NewsletterItem, SourceType } from '@/lib/types';

export const dynamic = 'force-dynamic';

type SearchParams = {
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
  let items: NewsletterItem[] = [];
  let allItems: NewsletterItem[] = [];
  let errorMessage = '';

  try {
    const filters: Record<string, string> = {};
    if (params.q) filters.q = params.q;
    if (params.category) filters.category = params.category;
    if (params.tag) filters.tag = params.tag;
    if (params.source_type) filters.source_type = params.source_type;

    [allItems, items] = await Promise.all([
      fetchNewsletters(),
      fetchNewsletters(Object.keys(filters).length > 0 ? filters : undefined),
    ]);
  } catch (error) {
    errorMessage = error instanceof Error ? error.message : '뉴스레터 목록을 불러오지 못했습니다.';
  }

  return (
    <AppShell title="뉴스레터 목록">
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
      {errorMessage ? (
        <div className="mb-4 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          뉴스레터 목록을 불러오지 못했습니다. 백엔드 실행 상태와 포트(18437)를 확인해주세요.
          <div className="mt-1 text-xs text-red-600">{errorMessage}</div>
        </div>
      ) : null}
      <NewsletterList items={items} />
    </AppShell>
  );
}
