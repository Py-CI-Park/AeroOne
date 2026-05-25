import React, { ReactNode } from 'react';
import Link from 'next/link';

import { Icon } from '@/components/ui/icons';
import { NewsletterThemeSelector } from '@/components/newsletter/newsletter-theme-selector';
import type { NewsletterTheme } from '@/lib/theme';

type ActiveNav = 'dashboard' | 'newsletters' | 'none';

const NAV_ITEMS: { id: Exclude<ActiveNav, 'none'>; label: string; href: string }[] = [
  { id: 'dashboard', label: 'Dashboard', href: '/' },
  { id: 'newsletters', label: 'Newsletter', href: '/newsletters' },
];

export function AppShell({
  title,
  children,
  contentClassName = 'max-w-6xl',
  theme = 'light',
  showThemeSelector = true,
  themePath = '/',
  active = 'none',
  breadcrumb,
  titleMeta,
  titleActions,
}: {
  title: string;
  children: ReactNode;
  contentClassName?: string;
  theme?: NewsletterTheme;
  showThemeSelector?: boolean;
  themePath?: string;
  active?: ActiveNav;
  breadcrumb?: string[];
  titleMeta?: ReactNode;
  titleActions?: ReactNode;
}) {
  return (
    <div
      data-testid="app-shell"
      className="min-h-screen bg-surface-base text-ink-1"
      suppressHydrationWarning
    >
      <header
        data-testid="app-shell-header"
        className="flex h-[60px] flex-shrink-0 items-center gap-6 border-b border-line-subtle bg-surface-raised px-8"
      >
        <Link href="/" className="flex items-center gap-2 text-ink-1">
          <span className="text-accent">
            <Icon.logo size={20} />
          </span>
          <span className="text-md font-semibold tracking-tighter">AeroOne</span>
          <span className="ml-1.5 font-mono text-xs text-ink-3">v1.0.8</span>
        </Link>

        <nav className="ml-4 flex gap-1" aria-label="주요 메뉴">
          {NAV_ITEMS.map((item) => {
            const isActive = active === item.id;
            return (
              <Link
                key={item.id}
                href={item.href}
                aria-current={isActive ? 'page' : undefined}
                className={`rounded px-2.5 py-1.5 text-base transition-colors duration-[120ms] ${
                  isActive
                    ? 'bg-surface-sunken font-medium text-ink-1'
                    : 'font-regular text-ink-2 hover:bg-surface-sunken hover:text-ink-1'
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>

        {breadcrumb && breadcrumb.length > 0 ? (
          <div className="ml-4 flex items-center gap-2 text-base text-ink-3">
            {breadcrumb.map((crumb, index) => (
              <React.Fragment key={`${crumb}-${index}`}>
                {index > 0 ? <Icon.chevR size={10} /> : null}
                <span className={index === breadcrumb.length - 1 ? 'text-ink-2' : 'text-ink-3'}>{crumb}</span>
              </React.Fragment>
            ))}
          </div>
        ) : null}

        <div className="ml-auto flex items-center gap-2">
          <button
            type="button"
            title="검색"
            aria-label="검색"
            className="inline-flex h-[30px] w-[34px] items-center justify-center rounded border border-line-subtle text-ink-2 transition-colors hover:bg-surface-sunken"
          >
            <Icon.search size={13} />
          </button>
          {showThemeSelector ? <NewsletterThemeSelector theme={theme} currentPath={themePath} /> : null}
        </div>
      </header>

      <main className={`mx-auto px-8 py-7 ${contentClassName}`}>
        <div className="mb-6 flex items-baseline justify-between gap-3">
          <div className="flex items-baseline gap-3">
            <h1 className="text-3xl font-semibold tracking-tightest text-ink-1">{title}</h1>
            {titleMeta ? <span className="font-mono text-sm text-ink-3">{titleMeta}</span> : null}
          </div>
          {titleActions ? <div className="flex gap-2">{titleActions}</div> : null}
        </div>
        {children}
      </main>
    </div>
  );
}
