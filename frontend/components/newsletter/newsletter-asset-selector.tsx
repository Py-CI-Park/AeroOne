import React from 'react';

import type { NewsletterTheme } from '@/lib/theme';
import type { AssetType } from '@/lib/types';

// 시각 라벨(짧음)과 접근성 라벨(전체 이름)을 분리 — 한 이슈의 자산 탭.
const assetShortLabels: Record<AssetType, string> = {
  html: 'HTML',
  markdown: 'MD',
  pdf: 'PDF',
};

const assetFullLabels: Record<AssetType, string> = {
  html: 'HTML',
  markdown: 'MARKDOWN',
  pdf: 'PDF',
};

const assetSubLabels: Record<AssetType, string> = {
  html: 'web',
  markdown: 'notes',
  pdf: 'print',
};

export function NewsletterAssetSelector({
  availableAssetTypes,
  selectedAsset,
  onChange,
  theme: _theme = 'light',
}: {
  availableAssetTypes: AssetType[];
  selectedAsset: AssetType;
  onChange: (asset: AssetType) => void;
  theme?: NewsletterTheme;
}) {
  return (
    <section
      data-testid="newsletters-format-panel"
      className="flex h-full flex-col gap-2 rounded-lg border border-line-subtle bg-surface-raised p-3 text-ink-1"
    >
      <p className="font-mono text-xs uppercase tracking-wide text-ink-3">Report format</p>
      <div className="flex flex-wrap items-center gap-1.5">
        {availableAssetTypes.map((assetType) => {
          const active = assetType === selectedAsset;
          return (
            <button
              key={assetType}
              type="button"
              aria-pressed={active}
              aria-label={assetFullLabels[assetType] ?? assetType.toUpperCase()}
              onClick={() => onChange(assetType)}
              className={`inline-flex items-center gap-1.5 rounded border px-3 py-1.5 text-sm transition-colors ${
                active
                  ? 'border-line bg-surface-elevated text-ink-1 shadow-xs'
                  : 'border-transparent text-ink-3 hover:bg-surface-sunken hover:text-ink-1'
              }`}
            >
              <span className="font-mono font-medium tracking-wide">{assetShortLabels[assetType] ?? assetType.toUpperCase()}</span>
              <span className="text-xs text-ink-3">{assetSubLabels[assetType] ?? ''}</span>
            </button>
          );
        })}
      </div>
    </section>
  );
}
