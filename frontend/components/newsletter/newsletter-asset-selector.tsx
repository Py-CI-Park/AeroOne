import React from 'react';

import type { NewsletterTheme } from '@/lib/theme';
import type { AssetType } from '@/lib/types';

const assetLabels: Record<AssetType, string> = {
  html: 'HTML',
  markdown: 'MD',
  pdf: 'PDF',
};

export function NewsletterAssetSelector({
  availableAssetTypes,
  selectedAsset,
  onChange,
  theme = 'light',
}: {
  availableAssetTypes: AssetType[];
  selectedAsset: AssetType;
  onChange: (asset: AssetType) => void;
  theme?: NewsletterTheme;
}) {
  const dark = theme === 'dark';

  return (
    <section
      data-testid="newsletters-format-panel"
      className={`flex h-full flex-col rounded-xl border p-3 shadow-sm ${
        dark ? 'border-slate-800 bg-slate-900/95 text-slate-100' : 'border-slate-200 bg-white text-slate-900'
      }`}
    >
      <p className={`mb-2 text-xs font-semibold uppercase tracking-[0.2em] ${dark ? 'text-slate-500' : 'text-slate-400'}`}>Report format</p>
      <div className="flex flex-wrap items-center gap-2">
        {availableAssetTypes.map((assetType) => {
          const active = assetType === selectedAsset;
          const label = assetLabels[assetType] ?? assetType.toUpperCase();
          const buttonClass = active
            ? dark
              ? 'border-blue-500/40 bg-blue-950/30 text-slate-50'
              : 'border-slate-900 bg-slate-900 text-white'
            : dark
              ? 'border-slate-800 bg-slate-950 text-slate-300 hover:border-slate-700 hover:bg-slate-900'
              : 'border-slate-200 bg-slate-50 text-slate-700 hover:border-blue-200 hover:bg-blue-50';

          return (
            <button
              key={assetType}
              type="button"
              aria-pressed={active}
              onClick={() => onChange(assetType)}
              title={label}
              className={`inline-flex h-9 min-w-[3rem] items-center justify-center rounded-lg border px-3 text-xs font-semibold tracking-wide transition ${buttonClass}`}
            >
              {label}
            </button>
          );
        })}
      </div>
    </section>
  );
}
