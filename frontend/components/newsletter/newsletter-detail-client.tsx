'use client';

import React from 'react';
import { useEffect, useMemo, useState } from 'react';
import { getBrowserApiBase } from '@/lib/api';
import type { AssetType, NewsletterDetail } from '@/lib/types';
import { HtmlViewer } from '@/components/newsletter/html-viewer';
import { MarkdownViewer } from '@/components/newsletter/markdown-viewer';
import { PdfViewer } from '@/components/newsletter/pdf-viewer';

type HtmlResponse = {
  asset_type: AssetType;
  content_html: string;
};

export function NewsletterDetailClient({
  newsletter,
  initialContentHtml = '',
}: {
  newsletter: NewsletterDetail;
  initialContentHtml?: string;
}) {
  const [selectedAsset, setSelectedAsset] = useState<AssetType>(newsletter.default_asset_type);
  const [contentHtml, setContentHtml] = useState(initialContentHtml);
  const currentAsset = useMemo(
    () => newsletter.available_assets.find((asset) => asset.asset_type === selectedAsset),
    [newsletter.available_assets, selectedAsset],
  );

  useEffect(() => {
    if (!currentAsset || selectedAsset === 'pdf') {
      return;
    }
    if (selectedAsset === newsletter.default_asset_type && initialContentHtml) {
      return;
    }
    void fetch(`${getBrowserApiBase()}${currentAsset.content_url}`)
      .then((response) => response.json() as Promise<HtmlResponse>)
      .then((payload) => setContentHtml(payload.content_html));
  }, [currentAsset, initialContentHtml, newsletter.default_asset_type, selectedAsset]);

  return (
    <section className="space-y-6">
      <header className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-3 flex flex-wrap gap-2 text-xs text-slate-500">
          <span className="rounded bg-slate-100 px-2 py-1 font-medium uppercase">{newsletter.source_type}</span>
          {newsletter.category ? <span>{newsletter.category.name}</span> : null}
        </div>
        <h1 className="text-3xl font-semibold text-slate-900">{newsletter.title}</h1>
        <p className="mt-3 text-sm leading-6 text-slate-600">{newsletter.description ?? '설명이 없습니다.'}</p>
        <div className="mt-4 flex flex-wrap gap-2">
          {newsletter.available_assets.map((asset) => (
            <button
              key={asset.asset_type}
              type="button"
              onClick={() => setSelectedAsset(asset.asset_type)}
              className={`rounded-md px-3 py-2 text-sm font-medium ${selectedAsset === asset.asset_type ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-700'}`}
            >
              {asset.asset_type.toUpperCase()}
            </button>
          ))}
          {currentAsset ? (
            <a href={`${getBrowserApiBase()}${currentAsset.download_url}`} className="rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white">
              다운로드
            </a>
          ) : null}
        </div>
      </header>

      {selectedAsset === 'pdf' && currentAsset ? <PdfViewer src={`${getBrowserApiBase()}${currentAsset.content_url}`} /> : null}
      {selectedAsset === 'html' ? <HtmlViewer title={newsletter.title} html={contentHtml} /> : null}
      {selectedAsset === 'markdown' ? <MarkdownViewer html={contentHtml} /> : null}
    </section>
  );
}
