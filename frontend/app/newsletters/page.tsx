import { AppShell } from '@/components/layout/app-shell';
import { NewsletterList } from '@/components/newsletter/newsletter-list';
import { fetchNewsletters } from '@/lib/api';
import type { NewsletterItem } from '@/lib/types';

export const dynamic = 'force-dynamic';

export default async function NewslettersPage() {
  let items: NewsletterItem[] = [];
  let errorMessage = '';

  try {
    items = await fetchNewsletters();
  } catch (error) {
    errorMessage = error instanceof Error ? error.message : '뉴스레터 목록을 불러오지 못했습니다.';
  }

  return (
    <AppShell title="뉴스레터 목록">
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
