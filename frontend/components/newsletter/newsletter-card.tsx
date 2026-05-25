import React from 'react';
import Link from 'next/link';

import { Tag, Thumb } from '@/components/ui/primitives';
import { NewsletterListItem } from '@/lib/types';

export function NewsletterCard({ item }: { item: NewsletterListItem }) {
  const formats = item.available_assets.map((asset) => asset.asset_type.toUpperCase());
  const publishedDate = item.published_at ? item.published_at.slice(0, 10) : null;

  return (
    <article className="flex flex-col gap-2 rounded border border-line-subtle bg-surface-elevated p-3 transition-shadow hover:shadow-sm">
      <Thumb seed={item.id} height={88} label={formats.join(' · ') || undefined} />

      <div className="flex items-center gap-1.5 text-xs text-ink-3">
        {publishedDate ? <span className="font-mono">{publishedDate}</span> : null}
        {publishedDate && item.category ? <span className="h-0.5 w-0.5 rounded-full bg-ink-4" /> : null}
        {item.category ? <span>{item.category.name}</span> : null}
        <span className="ml-auto font-mono uppercase">{item.source_type}</span>
      </div>

      <h2 className="text-base font-semibold leading-snug tracking-tight text-ink-1 line-clamp-2">
        <Link href={`/newsletters/${item.slug}`}>{item.title}</Link>
      </h2>

      {item.description ? <p className="text-sm text-ink-2 line-clamp-2">{item.description}</p> : null}

      {item.tags.length > 0 ? (
        <div className="mt-auto flex flex-wrap gap-1 pt-1">
          {item.tags.map((tag) => (
            <Tag key={tag.id}>#{tag.name}</Tag>
          ))}
        </div>
      ) : null}
    </article>
  );
}
