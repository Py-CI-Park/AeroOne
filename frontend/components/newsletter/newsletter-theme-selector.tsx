import React from 'react';
import Link from 'next/link';

import type { NewsletterTheme } from '@/lib/theme';

function buildThemeHref(theme: NewsletterTheme, currentPath = '/newsletters') {
  const params = new URLSearchParams();
  params.set('theme', theme);
  params.set('next', currentPath);

  return `/theme?${params.toString()}`;
}

export function NewsletterThemeSelector({
  theme,
  currentPath,
  className = '',
}: {
  theme: NewsletterTheme;
  currentPath?: string;
  className?: string;
}) {
  const nextTheme: NewsletterTheme = theme === 'dark' ? 'light' : 'dark';
  const label = nextTheme === 'dark' ? '다크 테마로 전환' : '라이트 테마로 전환';
  const icon = nextTheme === 'dark' ? '☾' : '☀';

  return (
    <span data-testid="newsletter-theme-selector" className={`inline-flex items-center ${className}`}>
      <Link
        href={buildThemeHref(nextTheme, currentPath)}
        aria-label={label}
        className="inline-flex h-7 w-7 items-center justify-center rounded-full border border-slate-200 bg-white text-xs leading-none text-slate-600 transition hover:border-blue-200 hover:bg-blue-50 hover:text-blue-700"
      >
        {icon}
      </Link>
    </span>
  );
}
