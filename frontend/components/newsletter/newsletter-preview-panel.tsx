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
      className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"
    >
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Preview</p>
          <h2 className="mt-1 text-lg font-semibold text-slate-900">{title}</h2>
        </div>
        <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-600">
          {selectedAsset.toUpperCase()}
        </span>
      </div>
      {children}
    </section>
  );
}
