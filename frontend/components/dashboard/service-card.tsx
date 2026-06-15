import React from 'react';
import Link from 'next/link';

import { Icon } from '@/components/ui/icons';
import { Tag } from '@/components/ui/primitives';

// 대시보드 모듈 카드 (Claude Design 핸드오프). active 카드는 Link, coming-soon 은 정적 div.
export function ServiceCard({
  title,
  description,
  href,
  badge,
  icon,
  active = true,
  count,
  external = false,
}: {
  title: string;
  description?: string;
  href: string;
  badge: string;
  icon?: string;
  active?: boolean;
  count?: number;
  external?: boolean;
}) {
  const body = (
    <>
      <div>
        <div className="mb-3 flex items-center justify-between">
          {icon ? (
            <span
              data-testid="service-card-icon"
              className="inline-flex h-7 w-7 items-center justify-center rounded bg-accent-soft text-base text-accent"
            >
              {icon}
            </span>
          ) : (
            <span
              className={`inline-flex h-7 w-7 items-center justify-center rounded ${
                active ? 'bg-accent-soft text-accent' : 'bg-surface-sunken text-ink-3'
              }`}
            >
              <Icon.doc size={15} />
            </span>
          )}
          <Tag tone={active ? 'ok' : 'neutral'}>
            <Icon.dot size={6} /> {badge}
          </Tag>
        </div>
        <h2 className="mb-1 text-xl font-semibold tracking-tighter text-ink-1">{title}</h2>
        {description ? (
          <p data-testid="service-card-description" className="text-base text-ink-2">
            {description}
          </p>
        ) : null}
      </div>
      <div className="mt-4 flex items-baseline gap-1.5">
        {typeof count === 'number' ? (
          <>
            <span className="font-serif text-2xl font-semibold tracking-tighter">{count}</span>
            <span className="text-sm text-ink-3">issues published</span>
          </>
        ) : active ? (
          <span className="inline-flex items-center gap-1 text-sm text-accent">
            Open <Icon.chevR size={11} />
          </span>
        ) : (
          <span className="font-mono text-sm text-ink-4">—</span>
        )}
      </div>
    </>
  );

  const className = `flex min-h-[200px] flex-col justify-between rounded-lg border p-6 ${
    active
      ? 'cursor-pointer border-line bg-surface-elevated shadow-sm transition-shadow hover:shadow-md'
      : 'cursor-default border-line-subtle bg-surface-raised opacity-65'
  }`;

  if (!active) {
    return (
      <div className={className} aria-disabled>
        {body}
      </div>
    );
  }

  if (external) {
    return (
      <a href={href} target="_blank" rel="noopener noreferrer" className={className}>
        {body}
      </a>
    );
  }

  return (
    <Link href={href} className={className}>
      {body}
    </Link>
  );
}
