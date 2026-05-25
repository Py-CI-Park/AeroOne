import React from 'react';
import { NewsletterListItem } from '@/lib/types';
import { NewsletterCard } from '@/components/newsletter/newsletter-card';

export function NewsletterList({ items }: { items: NewsletterListItem[] }) {
  if (items.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-line bg-surface-raised p-8 text-sm text-ink-2">
        표시할 뉴스레터가 없습니다.
        <div className="mt-2 text-xs text-ink-3">
          초기 설치 직후라면 관리자 화면에서 Import / Sync를 실행하거나 setup를 다시 실행해 외부 뉴스레터를 동기화하세요.
        </div>
      </div>
    );
  }

  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
      {items.map((item) => (
        <NewsletterCard key={item.id} item={item} />
      ))}
    </div>
  );
}
