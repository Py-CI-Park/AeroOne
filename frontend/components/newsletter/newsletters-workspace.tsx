'use client';

import React, { useEffect, useMemo, useState } from 'react';

import { NewsletterAssetSelector } from '@/components/newsletter/newsletter-asset-selector';
import { NewsletterDetailClient } from '@/components/newsletter/newsletter-detail-client';
import { NewsletterPreviewPanel } from '@/components/newsletter/newsletter-preview-panel';
import type { NewsletterDetail } from '@/lib/types';

export function NewslettersWorkspace({
  newsletter,
  initialContentHtml = '',
}: {
  newsletter: NewsletterDetail;
  initialContentHtml?: string;
}) {
  const availableAssetTypes = useMemo(
    () => newsletter.available_assets.map((asset) => asset.asset_type),
    [newsletter.available_assets],
  );
  const [selectedAsset, setSelectedAsset] = useState(newsletter.default_asset_type);

  useEffect(() => {
    setSelectedAsset(newsletter.default_asset_type);
  }, [newsletter.default_asset_type, newsletter.slug]);

  return (
    <div data-testid="newsletters-workspace" className="space-y-6">
      <NewsletterAssetSelector
        availableAssetTypes={availableAssetTypes}
        selectedAsset={selectedAsset}
        onChange={setSelectedAsset}
      />

      <NewsletterPreviewPanel title={newsletter.title} selectedAsset={selectedAsset}>
        <NewsletterDetailClient
          key={`${newsletter.slug}:${selectedAsset}`}
          newsletter={newsletter}
          selectedAsset={selectedAsset}
          initialContentHtml={initialContentHtml}
        />
      </NewsletterPreviewPanel>
    </div>
  );
}
