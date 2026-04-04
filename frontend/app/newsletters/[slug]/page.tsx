import React from 'react';
import { AppShell } from '@/components/layout/app-shell';
import { NewsletterDetailClient } from '@/components/newsletter/newsletter-detail-client';
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
      <NewsletterDetailClient newsletter={detail} initialContentHtml={initialContentHtml} />
    </AppShell>
  );
}
