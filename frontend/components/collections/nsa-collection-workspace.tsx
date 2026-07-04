'use client';

import React, { useEffect, useState } from 'react';

import { DocumentsWorkspace } from '@/components/documents/documents-workspace';
import { ApiError, fetchCollectionList } from '@/lib/api';
import type { DocumentListItem } from '@/lib/types';

const NSA_ACCESS_DENIED = 'NSA 자료는 권한이 있는 계정만 이용할 수 있습니다. 관리자에게 접근 권한을 요청하세요.';

type NsaCollectionWorkspaceProps = {
  initialPath?: string;
};

function isAccessDenied(error: unknown): boolean {
  return error instanceof ApiError && (error.status === 401 || error.status === 403);
}

export function NsaCollectionWorkspace({ initialPath }: NsaCollectionWorkspaceProps) {
  const [documents, setDocuments] = useState<DocumentListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError('');
    fetchCollectionList('nsa')
      .then((payload) => {
        if (!cancelled) {
          setDocuments(payload.documents);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setDocuments([]);
          setError(isAccessDenied(err) ? NSA_ACCESS_DENIED : err instanceof Error ? err.message : '목록을 불러오지 못했습니다.');
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
  }, []);

  if (loading) {
    return (
      <div data-testid="nsa-collection-loading" className="rounded-lg border border-dashed border-line bg-surface-raised p-8 text-sm text-ink-3">
        목록을 불러오는 중…
      </div>
    );
  }

  if (error) {
    return (
      <div data-testid="nsa-collection-error" className="rounded-lg border border-dashed border-line bg-surface-raised p-8 text-sm text-ink-2">
        {error}
      </div>
    );
  }

  if (documents.length === 0) {
    return (
      <div data-testid="nsa-collection-empty" className="rounded-lg border border-dashed border-line bg-surface-raised p-8 text-sm text-ink-2">
        표시할 문서가 없습니다.
      </div>
    );
  }

  return <DocumentsWorkspace documents={documents} collection="nsa" initialPath={initialPath} />;
}

export { NSA_ACCESS_DENIED };
