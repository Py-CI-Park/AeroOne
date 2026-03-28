import React from 'react';
import { NewsletterListItem } from '@/lib/types';
import { NewsletterCard } from '@/components/newsletter/newsletter-card';

export function NewsletterList({ items }: { items: NewsletterListItem[] }) {
  if (items.length === 0) {
    return <div className="rounded-xl border border-dashed border-slate-300 bg-white p-8 text-sm text-slate-500">표시할 뉴스레터가 없습니다.</div>;
  }

  return <div className="grid gap-4">{items.map((item) => <NewsletterCard key={item.id} item={item} />)}</div>;
}
