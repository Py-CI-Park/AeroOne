import React from 'react';

import type { AssetType } from '@/lib/types';

export function NewsletterAssetSelector({
  availableAssetTypes,
  selectedAsset,
  onChange,
}: {
  availableAssetTypes: AssetType[];
  selectedAsset: AssetType;
  onChange: (asset: AssetType) => void;
}) {
  return (
    <section
      data-testid="newsletters-format-panel"
      className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"
    >
      <div className="mb-3">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Format</p>
        <h2 className="mt-1 text-lg font-semibold text-slate-900">형식 선택</h2>
      </div>
      <div className="flex flex-wrap gap-2">
        {availableAssetTypes.map((assetType) => {
          const active = assetType === selectedAsset;

          return (
            <button
              key={assetType}
              type="button"
              aria-pressed={active}
              onClick={() => onChange(assetType)}
              className={`rounded-md px-3 py-2 text-sm font-medium ${
                active ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-700'
              }`}
            >
              {assetType.toUpperCase()}
            </button>
          );
        })}
      </div>
    </section>
  );
}
