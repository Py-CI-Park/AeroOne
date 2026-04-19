'use client';

import React from 'react';
import { useEffect, useMemo, useState } from 'react';

import { HtmlViewer } from '@/components/newsletter/html-viewer';
import { MarkdownViewer } from '@/components/newsletter/markdown-viewer';
import { PdfViewer } from '@/components/newsletter/pdf-viewer';
import { getNewsletterProxyPath } from '@/lib/api';
import type { AssetType, NewsletterDetail } from '@/lib/types';

type HtmlResponse = {
  asset_type: AssetType;
  content_html: string;
};

type PdfPreviewState = 'idle' | 'loading' | 'success' | 'error';
type AssetPreviewState = 'idle' | 'loading' | 'error';

export function NewsletterDetailClient({
  newsletter,
  selectedAsset,
  initialContentHtml = '',
}: {
  newsletter: NewsletterDetail;
  selectedAsset: AssetType;
  initialContentHtml?: string;
}) {
  const [contentHtml, setContentHtml] = useState(initialContentHtml);
  const [assetPreviewState, setAssetPreviewState] = useState<AssetPreviewState>('idle');
  const [pdfPreviewUrl, setPdfPreviewUrl] = useState<string | null>(null);
  const [pdfPreviewState, setPdfPreviewState] = useState<PdfPreviewState>('idle');
  const currentAsset = useMemo(
    () => newsletter.available_assets.find((asset) => asset.asset_type === selectedAsset),
    [newsletter.available_assets, selectedAsset],
  );

  useEffect(() => {
    setContentHtml(initialContentHtml);
    setAssetPreviewState('idle');
  }, [initialContentHtml, newsletter.slug]);

  useEffect(() => {
    if (!currentAsset || selectedAsset === 'pdf') {
      return;
    }
    if (selectedAsset === newsletter.default_asset_type && initialContentHtml) {
      setAssetPreviewState('idle');
      return;
    }

    const assetPath = getNewsletterProxyPath(currentAsset.content_url);
    let cancelled = false;

    void (async () => {
      try {
        setContentHtml('');
        setAssetPreviewState('loading');
        const response = await fetch(assetPath);

        if (!response.ok) {
          throw new Error(`Request failed: ${response.status}`);
        }

        const payload = (await response.json()) as HtmlResponse;
        if (cancelled) {
          return;
        }
        setContentHtml(payload.content_html);
        setAssetPreviewState('idle');
      } catch (error) {
        if (cancelled) {
          return;
        }
        setContentHtml('');
        setAssetPreviewState('error');
        console.error(`[FRONTEND][FETCH] Failed to load newsletter asset ${assetPath}`, error);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [currentAsset, initialContentHtml, newsletter.default_asset_type, selectedAsset]);

  useEffect(() => {
    let objectUrl: string | null = null;
    let cancelled = false;

    async function loadPdfPreview() {
      if (!currentAsset || selectedAsset !== 'pdf') {
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
  }, [currentAsset, selectedAsset]);

  if (!currentAsset) {
    return <p className="text-sm text-slate-500">No preview is available for this format.</p>;
  }

  if (selectedAsset === 'html') {
    if (assetPreviewState === 'loading') {
      return <p className="text-sm text-slate-500">Loading HTML preview...</p>;
    }
    if (assetPreviewState === 'error') {
      return <AssetPreviewError assetLabel="HTML" />;
    }
    return <HtmlViewer title={newsletter.title} html={contentHtml} />;
  }

  if (selectedAsset === 'markdown') {
    if (assetPreviewState === 'loading') {
      return <p className="text-sm text-slate-500">Loading Markdown preview...</p>;
    }
    if (assetPreviewState === 'error') {
      return <AssetPreviewError assetLabel="Markdown" />;
    }
    return <MarkdownViewer html={contentHtml} />;
  }

  if (pdfPreviewState === 'loading') {
    return <p className="text-sm text-slate-500">Loading PDF preview...</p>;
  }

  if (pdfPreviewState === 'success' && pdfPreviewUrl) {
    return <PdfViewer src={pdfPreviewUrl} />;
  }

  return (
    <section
      data-testid="newsletter-pdf-fallback"
      className="rounded-2xl border border-slate-200 bg-white p-10 text-center shadow-sm"
    >
      <div className="mx-auto max-w-xl">
        <p className="text-sm font-medium uppercase tracking-[0.2em] text-slate-400">PDF</p>
        <h2 className="mt-3 text-2xl font-semibold text-slate-900">PDF preview is unavailable.</h2>
        <p className="mt-3 text-sm leading-6 text-slate-600">
          Your browser cannot render this PDF inline right now. Download the file to inspect the newsletter locally.
        </p>
        <a
          href={getNewsletterProxyPath(currentAsset.download_url)}
          className="mt-6 inline-flex rounded-lg bg-slate-900 px-5 py-3 text-sm font-medium text-white"
        >
          Download PDF
        </a>
      </div>
    </section>
  );
}

function AssetPreviewError({ assetLabel }: { assetLabel: string }) {
  return (
    <section className="rounded-2xl border border-red-200 bg-red-50 p-8 text-center text-red-800">
      <h2 className="text-xl font-semibold">{assetLabel} preview is unavailable.</h2>
      <p className="mt-3 text-sm">
        The selected report format could not be loaded. Try another format or refresh the page.
      </p>
    </section>
  );
}
