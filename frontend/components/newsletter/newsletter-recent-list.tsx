import React from 'react';
import Link from 'next/link';

import type { NewsletterItem } from '@/lib/types';

function formatPublishedAt(value?: string | null) {
  return value ? value.slice(0, 10) : '발행일 없음';
}

export function NewsletterRecentList({
  items,
  selectedSlug,
}: {
  items: NewsletterItem[];
  selectedSlug?: string;
}) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-4">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">최근 발행</p>
        <h2 className="mt-1 text-xl font-semibold text-slate-900">뉴스레터 빠른 이동</h2>
      </div>

      <div className="space-y-3">
        {items.slice(0, 10).map((item) => {
          const isSelected = item.slug === selectedSlug;
          return (
            <Link
              key={item.slug}
              href={`/newsletters?slug=${item.slug}`}
              className={`block rounded-xl border px-4 py-3 transition ${
                isSelected ? 'border-slate-900 bg-slate-900 text-white shadow-sm' : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50'
              }`}
            >
              <div className="mb-2 flex items-center justify-between gap-2">
                <span className={`rounded-full px-2 py-1 text-[11px] font-semibold uppercase ${isSelected ? 'bg-white/15 text-slate-100' : 'bg-slate-100 text-slate-600'}`}>
                  {item.source_type}
                </span>
                <span className={`text-xs ${isSelected ? 'text-slate-200' : 'text-slate-400'}`}>{formatPublishedAt(item.published_at)}</span>
              </div>
              <div className={`line-clamp-2 text-sm font-medium ${isSelected ? 'text-white' : 'text-slate-900'}`}>{item.title}</div>
              {item.description ? <p className={`mt-1 line-clamp-2 text-xs ${isSelected ? 'text-slate-200' : 'text-slate-500'}`}>{item.description}</p> : null}
            </Link>
          );
        })}
      </div>
    </section>
  );
}
