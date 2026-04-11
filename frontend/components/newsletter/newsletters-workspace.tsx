'use client';

import React, { ReactNode, useMemo, useState } from 'react';

import { NewsletterAssetSelector } from '@/components/newsletter/newsletter-asset-selector';
import { NewsletterDetailClient } from '@/components/newsletter/newsletter-detail-client';
import { NewsletterPreviewPanel } from '@/components/newsletter/newsletter-preview-panel';
import type { NewsletterDetail } from '@/lib/types';

export function NewslettersWorkspace({
  calendarPanel,
  newsletter,
  initialContentHtml = '',
}: {
  calendarPanel?: ReactNode;
  newsletter: NewsletterDetail;
  initialContentHtml?: string;
}) {
  const availableAssetTypes = useMemo(
    () => newsletter.available_assets.map((asset) => asset.asset_type),
    [newsletter.available_assets],
  );
  const [selectedAsset, setSelectedAsset] = useState(newsletter.default_asset_type);

  return (
    <div data-testid="newsletters-workspace" className="space-y-3">
      <div
        data-testid="newsletters-control-grid"
        className={`grid gap-3 ${calendarPanel ? 'lg:grid-cols-[minmax(0,1.45fr)_minmax(18rem,0.8fr)]' : ''}`}
      >
        {calendarPanel}
        <NewsletterAssetSelector
          availableAssetTypes={availableAssetTypes}
          selectedAsset={selectedAsset}
          onChange={setSelectedAsset}
        />
      </div>

      <NewsletterPreviewPanel title={newsletter.title} selectedAsset={selectedAsset}>
        <NewsletterDetailClient
          newsletter={newsletter}
          selectedAsset={selectedAsset}
          initialContentHtml={initialContentHtml}
        />
      </NewsletterPreviewPanel>
    </div>
  );
}
