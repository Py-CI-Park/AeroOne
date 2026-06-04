import React from 'react';

import { AppShell } from '@/components/layout/app-shell';
import { DocumentsWorkspace } from '@/components/documents/documents-workspace';
import { fetchDocumentList } from '@/lib/api';
import { getAppTheme } from '@/lib/server-theme';
import type { DocumentListItem } from '@/lib/types';

export const dynamic = 'force-dynamic';

const PAGE_TITLE = 'Document';
const PAGE_PATH = '/documents';

type SearchParams = {
  theme?: string;
};

export default async function DocumentsPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const params = await searchParams;
  const theme = await getAppTheme(params.theme);

  let documents: DocumentListItem[] = [];
  let errorMessage = '';
  try {
    const payload = await fetchDocumentList();
    documents = payload.documents;
  } catch (error) {
    errorMessage = error instanceof Error ? error.message : '문서 목록을 불러오지 못했습니다.';
  }

  return (
    <AppShell
      title={PAGE_TITLE}
      contentClassName="max-w-[1600px]"
      theme={theme}
      showThemeSelector
      themePath={PAGE_PATH}
      active="documents"
      titleMeta={documents.length > 0 ? `${documents.length} documents` : undefined}
    >
      {documents.length > 0 ? (
        <DocumentsWorkspace documents={documents} />
      ) : (
        <div className="rounded-lg border border-dashed border-line bg-surface-raised p-8 text-sm text-ink-2">
          표시할 문서가 없습니다.
          <div className="mt-2 text-xs text-ink-3">
            _database/document 폴더에 HTML 문서를 넣은 뒤 페이지를 새로고침하세요. 하위 폴더로 분류해 넣으면 폴더 트리로 구분됩니다.
            {errorMessage ? <span className="ml-1">({errorMessage})</span> : null}
          </div>
        </div>
      )}
    </AppShell>
  );
}
