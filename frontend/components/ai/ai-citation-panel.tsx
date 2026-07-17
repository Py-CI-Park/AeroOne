'use client';

import React from 'react';

import type { AiCitation } from '@/lib/types';

import { citationKey } from '@/components/ai/ai-collection-key';
import { SafeViewerLink } from '@/components/ai/ai-viewer-link';

interface AiCitationPanelProps {
  citations: AiCitation[];
  onPreview: (citation: AiCitation) => void;
  previewCitation: AiCitation | null;
  previewHtml: string;
  previewLoading: boolean;
  previewError: string;
  previewExpanded: boolean;
  onTogglePreviewExpanded: () => void;
  onClosePreview: () => void;
}

export function AiCitationPanel({
  citations,
  onPreview,
  previewCitation,
  previewHtml,
  previewLoading,
  previewError,
  previewExpanded,
  onTogglePreviewExpanded,
  onClosePreview,
}: AiCitationPanelProps) {
  return (
    <>
      {citations.length > 0 ? (
        <div data-testid="ai-citations" className="mb-4 rounded-lg border border-line-subtle bg-surface-elevated p-3">
          <h3 className="mb-2 text-sm font-semibold text-ink-1">답변 근거</h3>
          <div className="flex flex-col gap-2">
            {citations.map((citation) => (
              <div key={citationKey(citation)} className="flex items-center justify-between gap-2">
                <SafeViewerLink
                  navigationUrl={citation.navigation_url}
                  className="min-w-0 flex-1 truncate text-sm text-accent hover:underline"
                  title={`${citation.collection}/${citation.folder ? `${citation.folder}/` : ''}${citation.name}`}
                >
                  {citation.collection} · {citation.folder ? `${citation.folder}/` : ''}{citation.name}
                </SafeViewerLink>
                <button
                  type="button"
                  onClick={() => onPreview(citation)}
                  className="shrink-0 rounded border border-line-subtle px-2 py-0.5 text-xs text-ink-2 hover:bg-surface-sunken"
                >
                  미리보기
                </button>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {previewCitation ? (
        <div
          data-testid="ai-citation-preview"
          className={
            previewExpanded
              ? 'fixed inset-4 z-[80] flex flex-col rounded-2xl border border-accent bg-surface-raised p-4 shadow-2xl'
              : 'mb-4 rounded-lg border border-accent bg-surface-elevated p-3'
          }
        >
          <div className="mb-2 flex items-center justify-between gap-2">
            <h3 className="min-w-0 truncate text-sm font-semibold text-ink-1">미리보기 · {previewCitation.name}</h3>
            <div className="flex shrink-0 items-center gap-2">
              <SafeViewerLink navigationUrl={previewCitation.navigation_url} className="text-xs text-accent hover:underline">새 탭에서 열기</SafeViewerLink>
              <button
                type="button"
                onClick={onTogglePreviewExpanded}
                className="text-xs text-accent hover:underline"
              >
                {previewExpanded ? '패널로 보기' : '전체 보기'}
              </button>
              <button
                type="button"
                onClick={onClosePreview}
                className="text-xs text-ink-3 hover:text-ink-1"
              >
                닫기
              </button>
            </div>
          </div>
          {previewLoading ? <p className="text-sm text-ink-3">문서를 불러오는 중…</p> : null}
          {previewError ? <p role="alert" className="rounded bg-danger-soft px-2 py-1 text-sm text-danger">{previewError}</p> : null}
          {!previewLoading && !previewError ? (
            <iframe
              title={`citation-preview-${previewCitation.name}`}
              sandbox=""
              srcDoc={previewHtml}
              className={`${previewExpanded ? 'min-h-0 flex-1' : 'h-[64dvh] min-h-[420px] max-h-[760px]'} w-full rounded border border-line-subtle bg-white`}
            />
          ) : null}
        </div>
      ) : null}
    </>
  );
}
