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
    <section
      data-testid="newsletter-theme-selector"
      className={`mb-3 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white p-3 shadow-sm ${className}`}
    >
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Theme</p>
        <h2 className="mt-1 text-sm font-semibold text-slate-900">화면 테마 선택</h2>
      </div>
      <div className="flex gap-2">
        {(['light', 'dark'] as const).map((item) => {
          const active = item === theme;
          return (
            <Link
              key={item}
              href={buildThemeHref(item, slug)}
              aria-current={active ? 'true' : undefined}
              className={`rounded-lg border px-3 py-2 text-sm font-medium transition ${
                active
                  ? 'border-slate-900 bg-slate-900 text-white'
                  : 'border-slate-200 bg-slate-50 text-slate-700 hover:border-blue-200 hover:bg-blue-50'
              }`}
            >
              {item === 'light' ? 'Light' : 'Dark'}
            </Link>
          );
        })}
      </div>
    </section>
  );
}
