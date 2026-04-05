import React from 'react';
import { AppShell } from '@/components/layout/app-shell';
import { NewslettersWorkspace } from '@/components/newsletter/newsletters-workspace';
import { fetchNewsletterAssetContent, fetchNewsletterDetail } from '@/lib/api';

export const dynamic = 'force-dynamic';

export default async function NewsletterDetailPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const detail = await fetchNewsletterDetail(slug);

  let initialContentHtml = '';
  if (detail.default_asset_type !== 'pdf') {
    const asset = detail.available_assets.find((item) => item.asset_type === detail.default_asset_type);
    if (asset) {
      try {
        const payload = await fetchNewsletterAssetContent(asset.content_url);
        initialContentHtml = payload.content_html;
      } catch {
        initialContentHtml = '';
      }
    }
  }

  return (
    <AppShell title={detail.title}>
      <NewslettersWorkspace key={detail.slug} newsletter={detail} initialContentHtml={initialContentHtml} />
    </AppShell>
  );
}
