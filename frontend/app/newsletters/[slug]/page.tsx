import React from 'react';
import { cookies } from 'next/headers';

import { AppShell } from '@/components/layout/app-shell';
import { NewslettersWorkspace } from '@/components/newsletter/newsletters-workspace';
import { fetchNewsletterAssetContent, fetchNewsletterDetail } from '@/lib/api';
import { NEWSLETTER_THEME_COOKIE, resolveNewsletterThemeFromSearchParam } from '@/lib/theme';

export const dynamic = 'force-dynamic';

export default async function NewsletterDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ slug: string }>;
  searchParams: Promise<{ theme?: string }>;
}) {
  const { slug } = await params;
  const query = await searchParams;
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

  const cookieStore = await cookies();
  const cookieTheme = cookieStore.getAll().find((cookie) => cookie.name === NEWSLETTER_THEME_COOKIE)?.value;
  const newsletterTheme = resolveNewsletterThemeFromSearchParam(query.theme, process.env.NEWSLETTERS_THEME, cookieTheme);
  const themePath = `/newsletters?slug=${detail.slug}`;

  return (
    <AppShell title={detail.title} theme={newsletterTheme} showThemeSelector themePath={themePath}>
      <NewslettersWorkspace
        key={detail.slug}
        newsletter={detail}
        initialContentHtml={initialContentHtml}
        theme={newsletterTheme}
      />
    </AppShell>
  );
}
