import { AppShell } from '@/components/layout/app-shell';
import { NewsletterDetailClient } from '@/components/newsletter/newsletter-detail-client';
import { fetchNewsletterDetail, getServerApiBase } from '@/lib/api';
import type { AssetType } from '@/lib/types';

export const dynamic = 'force-dynamic';

export default async function NewsletterDetailPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const detail = await fetchNewsletterDetail(slug);

  let initialContentHtml = '';
  if (detail.default_asset_type !== 'pdf') {
    const asset = detail.available_assets.find((item) => item.asset_type === detail.default_asset_type);
    if (asset) {
      const response = await fetch(`${getServerApiBase()}${asset.content_url}`, { cache: 'no-store' });
      if (response.ok) {
        const payload = (await response.json()) as { asset_type: AssetType; content_html: string };
        initialContentHtml = payload.content_html;
      }
    }
  }

  return (
    <AppShell title={detail.title}>
      <NewsletterDetailClient newsletter={detail} initialContentHtml={initialContentHtml} />
    </AppShell>
  );
}
