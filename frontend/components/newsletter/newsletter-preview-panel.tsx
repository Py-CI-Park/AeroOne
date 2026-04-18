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
  theme = 'light',
}: {
  title: string;
  selectedAsset: AssetType;
  children: React.ReactNode;
  displayDate?: string;
  dateNavigation?: NewsletterDateNavigation;
  theme?: NewsletterTheme;
}) {
  const dark = theme === 'dark';
  const metaClass = `text-xs ${dark ? 'text-slate-400' : 'text-slate-500'}`;
  const navLinkClass = `rounded-lg border px-3 py-1.5 text-xs font-medium transition ${
    dark
      ? 'border-slate-700 bg-slate-950 text-slate-200 hover:border-slate-600 hover:bg-slate-900'
      : 'border-slate-200 bg-slate-50 text-slate-700 hover:border-blue-200 hover:bg-blue-50'
  }`;
  const disabledNavClass = `rounded-lg border px-3 py-1.5 text-xs font-medium opacity-40 ${
    dark ? 'border-slate-800 bg-slate-950 text-slate-500' : 'border-slate-200 bg-slate-50 text-slate-400'
  }`;

  return (
    <section
      data-testid="newsletters-preview-panel"
      className={`rounded-xl border p-4 shadow-sm ${
        dark ? 'border-slate-800 bg-slate-900/95 text-slate-100' : 'border-slate-200 bg-white text-slate-900'
      }`}
    >
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className={`text-xs font-semibold uppercase tracking-[0.2em] ${dark ? 'text-slate-500' : 'text-slate-400'}`}>Preview</p>
          {displayDate ? <p className={metaClass}>{displayDate}</p> : null}
          <h2 className={`mt-1 text-lg font-semibold ${dark ? 'text-slate-100' : 'text-slate-900'}`}>{title}</h2>
          <p className={metaClass}>선택한 형식을 아래 큰 미리보기 표면에서 확인합니다.</p>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2">
          {dateNavigation?.previous ? (
            <a href={dateNavigation.previous.href} className={navLinkClass}>{dateNavigation.previous.label}</a>
          ) : (
            <span aria-disabled="true" className={disabledNavClass}>이전 날짜</span>
          )}
          {dateNavigation?.next ? (
            <a href={dateNavigation.next.href} className={navLinkClass}>{dateNavigation.next.label}</a>
          ) : (
            <span aria-disabled="true" className={disabledNavClass}>다음 날짜</span>
          )}
          <span className={`rounded-full border px-3 py-1 text-xs font-medium ${
            dark ? 'border-slate-700 bg-slate-950 text-slate-300' : 'border-slate-200 bg-slate-50 text-slate-600'
          }`}
          >
            {selectedAsset.toUpperCase()}
          </span>
        </div>
      </div>
      {children}
    </section>
  );
}
