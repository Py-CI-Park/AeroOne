'use client';

/**
 * Casual gate, NOT authentication. The password lives in client code and the
 * backend endpoint is unauthenticated within the closed network — do not store
 * sensitive data here.
 */

import React, { useEffect, useLayoutEffect, useRef, useState } from 'react';

import { DocumentsWorkspace } from '@/components/documents/documents-workspace';
import { fetchCollectionList } from '@/lib/api';
import type { DocumentListItem } from '@/lib/types';

type CollectionPasswordGateProps = {
  collection: string;
  title?: string;
  code?: string;
  initialPath?: string;
};

const unlockedStorageKey = (collection: string) => `aeroone.collection.${collection}.unlocked`;

export function CollectionPasswordGate({
  collection,
  title,
  code = '0000',
  initialPath,
}: CollectionPasswordGateProps) {
  const [unlocked, setUnlocked] = useState(false);
  const [input, setInput] = useState('');
  const [error, setError] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  const [documents, setDocuments] = useState<DocumentListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState('');

  useEffect(() => {
    try {
      if (window.localStorage.getItem(unlockedStorageKey(collection)) === '1') {
        setUnlocked(true);
      }
    } catch {
      // localStorage 접근이 막힌 브라우저에서도 비밀번호 폼은 정상 동작해야 한다.
    }
  }, [collection]);

  useLayoutEffect(() => {
    if (unlocked) {
      return undefined;
    }
    const focusPassword = () => inputRef.current?.focus();
    focusPassword();
    const timeoutId = window.setTimeout(focusPassword, 0);
    return () => window.clearTimeout(timeoutId);
  }, [unlocked]);

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
      try {
        window.localStorage.setItem(unlockedStorageKey(collection), '1');
      } catch {
        // 저장 실패 시에도 현재 탭에서는 unlocked 상태로 진행한다.
      }
    } else {
      setError('비밀번호가 올바르지 않습니다.');
    }
  }

  function handleLockAgain() {
    setUnlocked(false);
    setInput('');
    setError('');
    setDocuments([]);
    try {
      window.localStorage.removeItem(unlockedStorageKey(collection));
    } catch {
      // 저장소 접근 실패와 무관하게 현재 탭은 다시 잠근다.
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
            ref={inputRef}
            id="nsa-gate-password"
            type="password"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            className="rounded border border-line bg-surface-raised px-3 py-2 text-base text-ink-1 focus:outline-none focus:ring-2 focus:ring-accent"
            autoComplete="off"
            autoFocus
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

  const gateStatus = (
    <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-accent-soft bg-accent-soft/40 px-3 py-2 text-sm">
      <span className="font-medium text-accent">{title ?? collection} 잠금 해제됨</span>
      <button
        type="button"
        data-testid="collection-gate-lock"
        onClick={handleLockAgain}
        className="rounded border border-line-subtle bg-surface-raised px-2.5 py-1 text-xs text-ink-2 transition-colors hover:bg-surface-sunken hover:text-ink-1"
      >
        다시 잠그기
      </button>
    </div>
  );

  let content: React.ReactNode;

  if (loading) {
    content = (
      <div
        data-testid="collection-gate-loading"
        className="rounded-lg border border-dashed border-line bg-surface-raised p-8 text-sm text-ink-3"
      >
        목록을 불러오는 중…
      </div>
    );
  } else if (loadError) {
    content = (
      <div
        data-testid="collection-gate-error"
        className="rounded-lg border border-dashed border-line bg-surface-raised p-8 text-sm text-ink-2"
      >
        목록을 불러오지 못했습니다.
        <div className="mt-2 text-xs text-ink-3">{loadError}</div>
      </div>
    );
  } else if (documents.length === 0) {
    content = (
      <div
        data-testid="collection-gate-empty"
        className="rounded-lg border border-dashed border-line bg-surface-raised p-8 text-sm text-ink-2"
      >
        표시할 문서가 없습니다.
      </div>
    );
  } else {
    content = (
      <DocumentsWorkspace
        documents={documents}
        collection={collection as 'document' | 'civil' | 'nsa'}
        initialPath={initialPath}
      />
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {gateStatus}
      {content}
    </div>
  );
}
