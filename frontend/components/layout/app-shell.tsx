import React from 'react';
import Link from 'next/link';
import { ReactNode } from 'react';

import type { NewsletterTheme } from '@/lib/theme';

export function AppShell({
  title,
  children,
  contentClassName = 'max-w-6xl',
  theme = 'light',
}: {
  title: string;
  children: ReactNode;
  contentClassName?: string;
  theme?: NewsletterTheme;
}) {
  const dark = theme === 'dark';

  return (
    <div
      data-testid="app-shell"
      className={`min-h-screen ${dark ? 'bg-slate-950' : 'bg-slate-100'}`}
      suppressHydrationWarning
    >
      <header
        data-testid="app-shell-header"
        className={`border-b ${dark ? 'border-slate-800 bg-slate-950' : 'border-slate-200 bg-white'}`}
      >
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div>
            <Link href="/" className={`text-lg font-semibold ${dark ? 'text-slate-100' : 'text-slate-900'}`}>
              AeroOne
            </Link>
            <p className={`text-sm ${dark ? 'text-slate-400' : 'text-slate-500'}`}>
              사내 뉴스레터 / 문서 플랫폼
            </p>
          </div>
          <nav className={`flex gap-4 text-sm ${dark ? 'text-slate-300' : 'text-slate-600'}`}>
            <Link href="/">대시보드</Link>
            <Link href="/newsletters">뉴스레터</Link>
            <Link href="/admin/newsletters">관리자</Link>
            <Link href="/login">로그인</Link>
          </nav>
        </div>
      </header>
      <main className={`mx-auto px-6 py-8 ${contentClassName}`}>
        <h1 className={`mb-6 text-2xl font-semibold ${dark ? 'text-slate-100' : 'text-slate-900'}`}>
          {title}
        </h1>
        {children}
      </main>
    </div>
  );
}
