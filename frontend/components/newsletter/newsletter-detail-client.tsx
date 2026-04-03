'use client';

import React from 'react';
import { useEffect, useMemo, useState } from 'react';
import { getNewsletterProxyPath } from '@/lib/api';
import type { AssetType, NewsletterDetail } from '@/lib/types';
import { HtmlViewer } from '@/components/newsletter/html-viewer';
import { MarkdownViewer } from '@/components/newsletter/markdown-viewer';

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
    setSelectedAsset(newsletter.default_asset_type);
    setContentHtml(initialContentHtml);
  }, [newsletter.slug, newsletter.default_asset_type, initialContentHtml]);

  useEffect(() => {
    if (!currentAsset || selectedAsset === 'pdf') {
      return;
    }
    if (selectedAsset === newsletter.default_asset_type && initialContentHtml) {
      return;
    }
    void fetch(getNewsletterProxyPath(currentAsset.content_url))
      .then((response) => response.json() as Promise<HtmlResponse>)
      .then((payload) => setContentHtml(payload.content_html));
  }, [currentAsset, initialContentHtml, newsletter.default_asset_type, selectedAsset]);

  return (
    <section className="space-y-6">
      <header className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-wrap items-center gap-2">
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
        </div>
      </header>

      {selectedAsset === 'pdf' && currentAsset ? (
        <section className="rounded-2xl border border-slate-200 bg-white p-10 text-center shadow-sm">
          <div className="mx-auto max-w-xl">
            <p className="text-sm font-medium uppercase tracking-[0.2em] text-slate-400">PDF</p>
            <h2 className="mt-3 text-2xl font-semibold text-slate-900">브라우저 내 보기 대신 파일 다운로드로 제공합니다.</h2>
            <p className="mt-3 text-sm leading-6 text-slate-600">
              내부 브라우저의 이중 스크롤을 줄이기 위해 PDF는 다운로드 후 외부 PDF 뷰어에서 확인하는 흐름으로 단순화했습니다.
            </p>
            <a
              href={getNewsletterProxyPath(currentAsset.download_url)}
              className="mt-6 inline-flex rounded-lg bg-slate-900 px-5 py-3 text-sm font-medium text-white"
            >
              PDF 다운로드
            </a>
          </div>
        </section>
      ) : null}
      {selectedAsset === 'html' ? <HtmlViewer title={newsletter.title} html={contentHtml} /> : null}
      {selectedAsset === 'markdown' ? <MarkdownViewer html={contentHtml} /> : null}
    </section>
  );
}
