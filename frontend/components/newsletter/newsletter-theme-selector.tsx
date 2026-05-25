import React from 'react';

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
      {/* 일부러 일반 <a> (풀 내비게이션). /theme 가 쿠키를 바꾼 뒤 풀 로드되어야
          루트 layout 이 <html data-theme> 를 새 테마로 다시 렌더한다. <Link> 면
          클라이언트 내비라 문서가 리로드되지 않아 테마가 즉시 반영되지 않는다. */}
      <a
        href={buildThemeHref(nextTheme, currentPath)}
        aria-label={label}
        className="inline-flex items-center gap-1.5 rounded border border-line-subtle bg-surface-elevated px-2.5 py-1 text-sm leading-none text-ink-2 transition-colors duration-[120ms] hover:bg-surface-sunken hover:text-ink-1"
      >
        <span className="text-[13px] leading-none">{icon}</span>
        <span className="font-mono text-[10px] uppercase tracking-wide">{nextTheme}</span>
      </a>
    </span>
  );
}
