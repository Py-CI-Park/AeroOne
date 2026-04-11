import React from 'react';

import type { AssetType } from '@/lib/types';

export function NewsletterPreviewPanel({
  title,
  selectedAsset,
  children,
}: {
  title: string;
  selectedAsset: AssetType;
  children: React.ReactNode;
}) {
  return (
    <section
      data-testid="newsletters-preview-panel"
      className="rounded-xl border border-slate-800 bg-slate-900/95 p-4 text-slate-100 shadow-sm"
    >
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Preview</p>
          <h2 className="mt-1 text-lg font-semibold text-slate-100">{title}</h2>
          <p className="mt-1 text-xs text-slate-400">선택한 형식을 아래 큰 미리보기 표면에서 확인합니다.</p>
        </div>
        <span className="rounded-full border border-slate-700 bg-slate-950 px-3 py-1 text-xs font-medium text-slate-300">
          {selectedAsset.toUpperCase()}
        </span>
      </div>
      {children}
    </section>
  );
}
