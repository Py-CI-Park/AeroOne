import React from 'react';
import { NewsletterListItem } from '@/lib/types';
import { NewsletterCard } from '@/components/newsletter/newsletter-card';

export function NewsletterList({ items }: { items: NewsletterListItem[] }) {
  if (items.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-slate-300 bg-white p-8 text-sm text-slate-500">
        표시할 뉴스레터가 없습니다.
        <div className="mt-2 text-xs text-slate-400">
          초기 설치 직후라면 관리자 화면에서 Import / Sync를 실행하거나 setup를 다시 실행해 외부 뉴스레터를 동기화하세요.
        </div>
      </div>
    );
  }

  return <div className="grid gap-4">{items.map((item) => <NewsletterCard key={item.id} item={item} />)}</div>;
}
