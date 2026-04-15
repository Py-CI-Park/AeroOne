import React from 'react';

import type { NewsletterTheme } from '@/lib/theme';
import type { AssetType } from '@/lib/types';

const assetLabels: Record<AssetType, { label: string; shortLabel: string }> = {
  html: { label: 'HTML', shortLabel: 'HT' },
  markdown: { label: 'MARKDOWN', shortLabel: 'MD' },
  pdf: { label: 'PDF', shortLabel: 'PDF' },
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
      className={`rounded-xl border p-3 shadow-sm ${
        dark ? 'border-slate-800 bg-slate-900/95 text-slate-100' : 'border-slate-200 bg-white text-slate-900'
      }`}
    >
      <div className="mb-3">
        <p className={`text-xs font-semibold uppercase tracking-[0.2em] ${dark ? 'text-slate-500' : 'text-slate-400'}`}>Report format</p>
        <h2 className={`mt-1 text-lg font-semibold ${dark ? 'text-slate-100' : 'text-slate-900'}`}>HTML / Markdown / PDF 선택</h2>
        <p className={`mt-1 text-xs ${dark ? 'text-slate-400' : 'text-slate-500'}`}>미리보기 영역에 표시할 보고서 형식을 선택합니다.</p>
      </div>
      <div className="grid grid-cols-3 gap-2">
        {availableAssetTypes.map((assetType) => {
          const active = assetType === selectedAsset;
          const label = assetLabels[assetType] ?? { label: assetType.toUpperCase(), shortLabel: assetType.toUpperCase() };
          const buttonClass = active
            ? dark
              ? 'border-blue-500/40 bg-blue-950/30 text-slate-50'
              : 'border-slate-900 bg-slate-900 text-white'
            : dark
              ? 'border-slate-800 bg-slate-950 text-slate-300 hover:border-slate-700 hover:bg-slate-900'
              : 'border-slate-200 bg-slate-50 text-slate-700 hover:border-blue-200 hover:bg-blue-50';
          const badgeClass = active
            ? dark
              ? 'border-slate-700 bg-slate-900 text-white'
              : 'border-slate-700 bg-slate-800 text-white'
            : dark
              ? 'border-slate-700 bg-slate-900 text-slate-300'
              : 'border-slate-200 bg-white text-slate-700';

          return (
            <button
              key={assetType}
              type="button"
              aria-pressed={active}
              onClick={() => onChange(assetType)}
              className={`rounded-xl border p-3 text-center transition ${buttonClass}`}
            >
              <span className={`mx-auto flex h-10 w-10 items-center justify-center rounded-lg border text-xs font-bold tracking-wide ${badgeClass}`}>
                {label.shortLabel}
              </span>
              <span className="mt-2 block text-xs font-medium">{label.label}</span>
            </button>
          );
        })}
      </div>
    </section>
  );
}
