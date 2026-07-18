'use client';

import React from 'react';

import type { CollectionSearchResult } from '@/lib/types';

import { citationKey } from '@/components/ai/ai-collection-key';
import { SafeViewerLink } from '@/components/ai/ai-viewer-link';

interface AiSearchPanelProps {
  searchQuery: string;
  onSearchQueryChange: (value: string) => void;
  onSearchSubmit: (event: React.FormEvent<HTMLFormElement>) => void;
  searchPending: boolean;
  searchError: string;
  searchDegraded: string;
  searchResults: CollectionSearchResult[];
  selectedRefs: Array<{ collection: 'document' | 'civil' | 'nsa'; path: string }>;
  onClearSelectedRefs: () => void;
  isRefSelected: (result: CollectionSearchResult) => boolean;
  onToggleRef: (result: CollectionSearchResult) => void;
}

export function AiSearchPanel({
  searchQuery,
  onSearchQueryChange,
  onSearchSubmit,
  searchPending,
  searchError,
  searchDegraded,
  searchResults,
  selectedRefs,
  onClearSelectedRefs,
  isRefSelected,
  onToggleRef,
}: AiSearchPanelProps) {
  return (
    <>
      <h2 className="text-lg font-semibold text-ink-1">HTML 본문 검색</h2>
      <p className="mb-3 text-sm text-ink-3">_database 의 Document/Civil HTML 본문을 빠르게 검색하고 파일로 바로 이동합니다.</p>
      <form onSubmit={onSearchSubmit} className="mb-3 flex gap-2">
        <input
          data-testid="ai-search-input"
          value={searchQuery}
          onChange={(event) => onSearchQueryChange(event.target.value)}
          placeholder="문서 내용 검색"
          className="min-w-0 flex-1 rounded border border-line-subtle bg-surface-elevated px-3 py-2 text-base text-ink-1 placeholder:text-ink-3"
        />
        <button type="submit" disabled={searchPending} className="rounded-md bg-accent px-4 py-2 text-base font-medium text-accent-on disabled:opacity-60">
          {searchPending ? '검색 중' : '검색'}
        </button>
      </form>
      {searchPending ? <p data-testid="ai-search-pending" className="text-sm text-ink-3">본문 검색 중…</p> : null}
      {searchDegraded ? <p className="rounded bg-warn-soft px-3 py-2 text-sm text-warn">{searchDegraded}</p> : null}
      {searchError ? <p role="alert" className="rounded bg-danger-soft px-3 py-2 text-sm text-danger">{searchError}</p> : null}
      {selectedRefs.length > 0 ? (
        <p className="mb-2 text-xs text-ink-2">
          선택한 문서 {selectedRefs.length}건을 다음 질문의 근거로 사용합니다.{' '}
          <button type="button" onClick={onClearSelectedRefs} className="text-accent underline">
            선택 해제
          </button>
        </p>
      ) : null}
      <div data-testid="ai-search-results" className="flex flex-col gap-2">
        {searchResults.map((result) => (
          <div
            key={citationKey(result)}
            className={`flex items-start gap-2 rounded-lg border p-3 transition ${
              isRefSelected(result) ? 'border-accent bg-accent-soft' : 'border-line-subtle bg-surface-elevated'
            }`}
          >
            <input
              type="checkbox"
              className="mt-1"
              aria-label={`근거로 선택: ${result.name}`}
              checked={isRefSelected(result)}
              onChange={() => onToggleRef(result)}
            />
            <SafeViewerLink
              navigationUrl={result.navigation_url}
              className="min-w-0 flex-1 rounded hover:bg-surface-sunken"
              disabledElement="div"
            >
              <div className="text-sm font-semibold text-ink-1">{result.collection} · {result.folder ? `${result.folder}/` : ''}{result.name}</div>
              <div className="mt-1 text-sm text-ink-2">{result.snippet || result.path}</div>
              <div className="mt-1 text-xs text-accent">파일 열기</div>
            </SafeViewerLink>
          </div>
        ))}
      </div>
    </>
  );
}
