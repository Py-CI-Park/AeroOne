import React from 'react';

import type { NewsletterTheme } from '@/lib/theme';
import type { AssetType } from '@/lib/types';

export type NewsletterDateNavigation = {
  previous?: {
    label: string;
    href: string;
  };
  next?: {
    label: string;
    href: string;
  };
};

export function NewsletterPreviewPanel({
  title,
  selectedAsset,
  children,
  displayDate,
  dateNavigation,
  theme: _theme = 'light',
}: {
  title: string;
  selectedAsset: AssetType;
  children: React.ReactNode;
  displayDate?: string;
  dateNavigation?: NewsletterDateNavigation;
  theme?: NewsletterTheme;
}) {
  const navLinkClass =
    'rounded border border-line-subtle bg-surface-elevated px-3 py-1.5 text-xs font-medium text-ink-2 transition-colors hover:bg-surface-sunken hover:text-ink-1';
  const disabledNavClass =
    'rounded border border-line-subtle bg-surface-elevated px-3 py-1.5 text-xs font-medium text-ink-4 opacity-50';

  return (
    <section
      data-testid="newsletters-preview-panel"
      className="rounded-lg border border-line-subtle bg-surface-raised p-4 text-ink-1"
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="font-mono text-xs uppercase tracking-wide text-ink-3">Preview</p>
          <h2 className="mt-0.5 text-xl font-semibold tracking-tight text-ink-1">
            {title}
            {displayDate ? <span className="ml-2 font-mono text-sm font-normal text-ink-3">{displayDate}</span> : null}
          </h2>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2">
          {dateNavigation?.previous ? (
            <a href={dateNavigation.previous.href} className={navLinkClass}>
              {dateNavigation.previous.label}
            </a>
          ) : (
            <span aria-disabled="true" className={disabledNavClass}>
              이전 날짜
            </span>
          )}
          {dateNavigation?.next ? (
            <a href={dateNavigation.next.href} className={navLinkClass}>
              {dateNavigation.next.label}
            </a>
          ) : (
            <span aria-disabled="true" className={disabledNavClass}>
              다음 날짜
            </span>
          )}
          <span className="rounded border border-line-subtle bg-surface-elevated px-3 py-1 font-mono text-xs font-medium text-ink-2">
            {selectedAsset.toUpperCase()}
          </span>
        </div>
      </div>
      {children}
    </section>
  );
}
