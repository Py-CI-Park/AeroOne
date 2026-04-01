import React from 'react';
import Link from 'next/link';

import { NewsletterListItem } from '@/lib/types';

export function NewsletterCard({ item }: { item: NewsletterListItem }) {
  return (
    <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-3 flex items-center gap-2 text-xs text-slate-500">
        <span className="rounded-full bg-slate-100 px-2 py-1 uppercase">{item.source_type}</span>
        {item.category ? <span>{item.category.name}</span> : null}
      </div>
      <h2 className="mb-2 text-lg font-semibold text-slate-900">
        <Link href={`/newsletters/${item.slug}`}>{item.title}</Link>
      </h2>
      {item.description ? <p className="text-sm text-slate-600">{item.description}</p> : null}
      <div className="mt-3 flex flex-wrap gap-2">
        {item.tags.map((tag) => (
          <span key={tag.id} className="rounded-full bg-blue-50 px-2.5 py-1 text-xs text-blue-700">#{tag.name}</span>
        ))}
      </div>
    </article>
  );
}
