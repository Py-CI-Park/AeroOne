'use client';

import { useEffect, useState } from 'react';

import { AppShell } from '@/components/layout/app-shell';
import { HtmlViewer } from '@/components/newsletter/html-viewer';
import { MarkdownViewer } from '@/components/newsletter/markdown-viewer';
import { PdfViewer } from '@/components/newsletter/pdf-viewer';
import { getBrowserApiBase, getHtmlContent, getNewsletterDetail } from '@/lib/api';
import type { NewsletterDetail } from '@/lib/types';

export default function NewsletterDetailPage({ params }: { params: Promise<{ slug: string }> }) {
  const [detail, setDetail] = useState<NewsletterDetail | null>(null);
  const [contentHtml, setContentHtml] = useState('');
  const [activeType, setActiveType] = useState<'html' | 'pdf' | 'markdown'>('html');

  useEffect(() => {
    params.then(async ({ slug }) => {
      const data = await getNewsletterDetail(slug);
      setDetail(data);
      setActiveType(data.default_asset_type);
    });
  }, [params]);

  useEffect(() => {
    if (!detail) return;
    const asset = detail.available_assets.find((item) => item.asset_type === activeType);
    if (!asset || asset.asset_type === 'pdf') return;
    getHtmlContent(asset.content_url).then((response) => setContentHtml(response.html));
  }, [detail, activeType]);

  return (
    <AppShell title={detail?.title ?? '뉴스레터 상세'}>
      {!detail ? <p>로딩 중...</p> : null}
      {detail ? (
        <div className="space-y-4">
          <div className="flex flex-wrap gap-2">
            {detail.available_assets.map((asset) => (
              <button key={asset.asset_type} type="button" className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-sm" onClick={() => setActiveType(asset.asset_type)}>
                {asset.asset_type.toUpperCase()}
              </button>
            ))}
          </div>
          {activeType === 'pdf' ? <PdfViewer src={`${getBrowserApiBase()}${detail.available_assets.find((asset) => asset.asset_type === 'pdf')?.content_url ?? ''}`} /> : null}
          {activeType === 'html' ? <HtmlViewer title={detail.title} html={contentHtml} /> : null}
          {activeType === 'markdown' ? <MarkdownViewer html={contentHtml} /> : null}
        </div>
      ) : null}
    </AppShell>
  );
}
