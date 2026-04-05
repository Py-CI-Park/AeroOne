'use client';

import React from 'react';
import { useEffect, useMemo, useState } from 'react';

import { NewsletterAssetSelector } from '@/components/newsletter/newsletter-asset-selector';
import { HtmlViewer } from '@/components/newsletter/html-viewer';
import { MarkdownViewer } from '@/components/newsletter/markdown-viewer';
import { NewsletterPreviewPanel } from '@/components/newsletter/newsletter-preview-panel';
import { PdfViewer } from '@/components/newsletter/pdf-viewer';
import { getNewsletterProxyPath } from '@/lib/api';
import type { AssetType, NewsletterDetail } from '@/lib/types';

type HtmlResponse = {
  asset_type: AssetType;
  content_html: string;
};

type PdfPreviewState = 'idle' | 'loading' | 'success' | 'error';

export function NewsletterDetailClient({
  newsletter,
  selectedAsset,
  initialContentHtml = '',
}: {
  newsletter: NewsletterDetail;
  selectedAsset?: AssetType;
  initialContentHtml?: string;
}) {
  const [internalSelectedAsset, setInternalSelectedAsset] = useState<AssetType>(newsletter.default_asset_type);
  const [contentHtml, setContentHtml] = useState(initialContentHtml);
  const [pdfPreviewUrl, setPdfPreviewUrl] = useState<string | null>(null);
  const [pdfPreviewState, setPdfPreviewState] = useState<PdfPreviewState>('idle');
  const resolvedSelectedAsset = selectedAsset ?? internalSelectedAsset;
  const isAssetControlled = selectedAsset !== undefined;
  const currentAsset = useMemo(
    () => newsletter.available_assets.find((asset) => asset.asset_type === resolvedSelectedAsset),
    [newsletter.available_assets, resolvedSelectedAsset],
  );

  useEffect(() => {
    if (!isAssetControlled) {
      setInternalSelectedAsset(newsletter.default_asset_type);
    }
    setContentHtml(initialContentHtml);
  }, [initialContentHtml, isAssetControlled, newsletter.default_asset_type, newsletter.slug]);

  useEffect(() => {
    if (!currentAsset || resolvedSelectedAsset === 'pdf') {
      return;
    }
    if (resolvedSelectedAsset === newsletter.default_asset_type && initialContentHtml) {
      return;
    }

    const assetPath = getNewsletterProxyPath(currentAsset.content_url);

    void (async () => {
      try {
        const response = await fetch(assetPath);

        if (!response.ok) {
          throw new Error(`Request failed: ${response.status}`);
        }

        const payload = (await response.json()) as HtmlResponse;
        setContentHtml(payload.content_html);
      } catch (error) {
        console.error(`[FRONTEND][FETCH] Failed to load newsletter asset ${assetPath}`, error);
      }
    })();
  }, [currentAsset, initialContentHtml, newsletter.default_asset_type, resolvedSelectedAsset]);

  useEffect(() => {
    let objectUrl: string | null = null;
    let cancelled = false;

    async function loadPdfPreview() {
      if (!currentAsset || resolvedSelectedAsset !== 'pdf') {
        setPdfPreviewState('idle');
        setPdfPreviewUrl(null);
        return;
      }

      const pdfPath = getNewsletterProxyPath(currentAsset.content_url);

      try {
        setPdfPreviewState('loading');
        const response = await fetch(pdfPath);
        if (!response.ok) {
          throw new Error(`Request failed: ${response.status}`);
        }
        const blob = await response.blob();
        objectUrl = URL.createObjectURL(blob);
        if (cancelled) {
          if (typeof URL.revokeObjectURL === 'function') {
            URL.revokeObjectURL(objectUrl);
          }
          return;
        }
        setPdfPreviewUrl(objectUrl);
        setPdfPreviewState('success');
      } catch (error) {
        if (cancelled) {
          return;
        }
        setPdfPreviewUrl(null);
        setPdfPreviewState('error');
        console.error(`[FRONTEND][FETCH] Failed to preview newsletter PDF ${pdfPath}`, error);
      }
    }

    void loadPdfPreview();

    return () => {
      cancelled = true;
      if (objectUrl && typeof URL.revokeObjectURL === 'function') {
        URL.revokeObjectURL(objectUrl);
      }
    };
  }, [currentAsset, resolvedSelectedAsset]);

  const previewContent = (
    <>
      {resolvedSelectedAsset === 'html' ? <HtmlViewer title={newsletter.title} html={contentHtml} /> : null}
      {resolvedSelectedAsset === 'markdown' ? <MarkdownViewer html={contentHtml} /> : null}
      {resolvedSelectedAsset === 'pdf' && currentAsset ? (
        pdfPreviewState === 'loading' ? (
          <p className="text-sm text-slate-500">PDF 미리보기를 불러오는 중입니다.</p>
        ) : pdfPreviewState === 'success' && pdfPreviewUrl ? (
          <PdfViewer src={pdfPreviewUrl} />
        ) : (
          <section
            data-testid="newsletter-pdf-fallback"
            className="rounded-2xl border border-slate-200 bg-white p-10 text-center shadow-sm"
          >
            <div className="mx-auto max-w-xl">
              <p className="text-sm font-medium uppercase tracking-[0.2em] text-slate-400">PDF</p>
              <h2 className="mt-3 text-2xl font-semibold text-slate-900">PDF 미리보기를 사용할 수 없습니다.</h2>
              <p className="mt-3 text-sm leading-6 text-slate-600">
                브라우저 환경에 따라 PDF 미리보기가 제한될 수 있습니다. 아래 버튼으로 파일을 직접 내려받아 확인하세요.
              </p>
              <a
                href={getNewsletterProxyPath(currentAsset.download_url)}
                className="mt-6 inline-flex rounded-lg bg-slate-900 px-5 py-3 text-sm font-medium text-white"
              >
                PDF 다운로드
              </a>
            </div>
          </section>
        )
      ) : null}
    </>
  );

  if (isAssetControlled) {
    return <section className="space-y-4">{previewContent}</section>;
  }

  return (
    <section className="space-y-4">
      <section data-testid="newsletter-asset-selector">
        <NewsletterAssetSelector
          availableAssetTypes={newsletter.available_assets.map((asset) => asset.asset_type)}
          selectedAsset={resolvedSelectedAsset}
          onChange={setInternalSelectedAsset}
        />
      </section>

      <section data-testid="newsletter-preview-panel">
        <NewsletterPreviewPanel title={newsletter.title} selectedAsset={resolvedSelectedAsset}>
          {previewContent}
        </NewsletterPreviewPanel>
      </section>
    </section>
  );
}
