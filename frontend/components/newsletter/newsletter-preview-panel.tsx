import React from 'react';

import type { NewsletterTheme } from '@/lib/theme';
import type { AssetType } from '@/lib/types';

export function NewsletterPreviewPanel({
  title,
  selectedAsset,
  children,
  theme = 'light',
}: {
  title: string;
  selectedAsset: AssetType;
  children: React.ReactNode;
  theme?: NewsletterTheme;
}) {
  const dark = theme === 'dark';

  return (
    <section
      data-testid="newsletters-preview-panel"
      className={`rounded-xl border p-4 shadow-sm ${
        dark ? 'border-slate-800 bg-slate-900/95 text-slate-100' : 'border-slate-200 bg-white text-slate-900'
      }`}
    >
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <p className={`text-xs font-semibold uppercase tracking-[0.2em] ${dark ? 'text-slate-500' : 'text-slate-400'}`}>Preview</p>
          <h2 className={`mt-1 text-lg font-semibold ${dark ? 'text-slate-100' : 'text-slate-900'}`}>{title}</h2>
          <p className={`mt-1 text-xs ${dark ? 'text-slate-400' : 'text-slate-500'}`}>선택한 형식을 아래 큰 미리보기 표면에서 확인합니다.</p>
        </div>
        <span className={`rounded-full border px-3 py-1 text-xs font-medium ${
          dark ? 'border-slate-700 bg-slate-950 text-slate-300' : 'border-slate-200 bg-slate-50 text-slate-600'
        }`}
        >
          {selectedAsset.toUpperCase()}
        </span>
      </div>
      {children}
    </section>
  );
}
