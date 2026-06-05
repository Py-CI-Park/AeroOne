'use client';

/**
 * Casual gate, NOT authentication. The password lives in client code and the
 * backend endpoint is unauthenticated within the closed network — do not store
 * sensitive data here.
 */

import React, { useEffect, useState } from 'react';

import { DocumentsWorkspace } from '@/components/documents/documents-workspace';
import { fetchCollectionList } from '@/lib/api';
import type { DocumentListItem } from '@/lib/types';

type CollectionPasswordGateProps = {
  collection: string;
  title?: string;
  code?: string;
};

export function CollectionPasswordGate({
  collection,
  title,
  code = '0000',
}: CollectionPasswordGateProps) {
  const [unlocked, setUnlocked] = useState(false);
  const [input, setInput] = useState('');
  const [error, setError] = useState('');

  const [documents, setDocuments] = useState<DocumentListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState('');

  useEffect(() => {
    if (!unlocked) {
      return;
    }
    let cancelled = false;
    setLoading(true);
    setLoadError('');
    fetchCollectionList(collection)
      .then((payload) => {
        if (!cancelled) {
          setDocuments(payload.documents);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setLoadError(err instanceof Error ? err.message : '목록을 불러오지 못했습니다.');
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [unlocked, collection]);

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (input === code) {
      setUnlocked(true);
    } else {
      setError('비밀번호가 올바르지 않습니다.');
    }
  }

  if (!unlocked) {
    return (
      <div data-testid="collection-password-gate-form" className="flex flex-col items-center gap-4 py-16">
        {title ? (
          <h2 className="text-lg font-semibold text-ink-1">{title}</h2>
        ) : null}
        <form onSubmit={handleSubmit} className="flex flex-col gap-3 w-72">
          <label htmlFor="nsa-gate-password" className="text-sm font-medium text-ink-2">
            비밀번호
          </label>
          <input
            id="nsa-gate-password"
            type="password"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            className="rounded border border-line bg-surface-raised px-3 py-2 text-base text-ink-1 focus:outline-none focus:ring-2 focus:ring-accent"
            autoComplete="off"
          />
          {error ? (
            <p role="alert" className="text-sm text-red-500">
              {error}
            </p>
          ) : null}
          <button
            type="submit"
            className="rounded-md bg-accent px-4 py-2 text-base font-medium text-accent-on transition-colors hover:bg-accent-hover"
          >
            확인
          </button>
        </form>
      </div>
    );
  }

  if (loading) {
    return (
      <div
        data-testid="collection-gate-loading"
        className="rounded-lg border border-dashed border-line bg-surface-raised p-8 text-sm text-ink-3"
      >
        목록을 불러오는 중…
      </div>
    );
  }

  if (loadError) {
    return (
      <div
        data-testid="collection-gate-error"
        className="rounded-lg border border-dashed border-line bg-surface-raised p-8 text-sm text-ink-2"
      >
        목록을 불러오지 못했습니다.
        <div className="mt-2 text-xs text-ink-3">{loadError}</div>
      </div>
    );
  }

  if (documents.length === 0) {
    return (
      <div
        data-testid="collection-gate-empty"
        className="rounded-lg border border-dashed border-line bg-surface-raised p-8 text-sm text-ink-2"
      >
        표시할 문서가 없습니다.
      </div>
    );
  }

  return (
    <DocumentsWorkspace
      documents={documents}
      collection={collection as 'document' | 'civil' | 'nsa'}
    />
  );
}
