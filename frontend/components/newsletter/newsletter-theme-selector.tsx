import React from 'react';
import Link from 'next/link';

import type { NewsletterTheme } from '@/lib/theme';

function buildThemeHref(theme: NewsletterTheme, slug?: string) {
  const params = new URLSearchParams();
  if (slug) {
    params.set('slug', slug);
  }
  params.set('theme', theme);

  return `/newsletters?${params.toString()}`;
}

export function NewsletterThemeSelector({
  theme,
  slug,
  className = '',
}: {
  theme: NewsletterTheme;
  slug?: string;
  className?: string;
}) {
  return (
    <span data-testid="newsletter-theme-selector" className={`inline-flex items-center gap-1 ${className}`}>
      {(['light', 'dark'] as const).map((item) => {
        const active = item === theme;
        return (
          <Link
            key={item}
            href={buildThemeHref(item, slug)}
            aria-label={item === 'light' ? '라이트 테마' : '다크 테마'}
            aria-current={active ? 'true' : undefined}
            className={`inline-flex h-7 w-7 items-center justify-center rounded-full border text-xs leading-none transition ${
              active
                ? 'border-slate-900 bg-slate-900 text-white'
                : 'border-slate-200 bg-white text-slate-500 hover:border-blue-200 hover:bg-blue-50 hover:text-blue-700'
            }`}
          >
            {item === 'light' ? '☀' : '☾'}
          </Link>
        );
      })}
    </span>
  );
}
