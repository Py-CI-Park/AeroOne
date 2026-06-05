import React from 'react';
import { cookies } from 'next/headers';

import { AppShell } from '@/components/layout/app-shell';
import { DocumentsWorkspace } from '@/components/documents/documents-workspace';
import { fetchCollectionListServer } from '@/lib/api';
import { NEWSLETTER_THEME_COOKIE, resolveNewsletterThemeFromSearchParam } from '@/lib/theme';
import type { DocumentListItem } from '@/lib/types';

export const dynamic = 'force-dynamic';

const REPORT_TITLE = 'Civil Aircraft Spec Catalog';
const REPORT_PATH = '/reports/civil-aircraft';

type SearchParams = {
  theme?: string;
};

export default async function CivilAircraftReportPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const params = await searchParams;
  let documents: DocumentListItem[] = [];
  let errorMessage = '';

  try {
    const payload = await fetchCollectionListServer('civil');
    documents = payload.documents;
  } catch (error) {
    errorMessage = error instanceof Error ? error.message : '카탈로그 목록을 불러오지 못했습니다.';
  }

  const cookieStore = await cookies();
  const cookieTheme = cookieStore.getAll().find((cookie) => cookie.name === NEWSLETTER_THEME_COOKIE)?.value;
  const theme = resolveNewsletterThemeFromSearchParam(params.theme, process.env.NEWSLETTERS_THEME, cookieTheme);

  return (
    <AppShell
      title={REPORT_TITLE}
      contentClassName="max-w-[1600px]"
      theme={theme}
      showThemeSelector
      themePath={REPORT_PATH}
      active="none"
      titleMeta={documents.length > 0 ? `${documents.length} catalogs` : undefined}
    >
      {documents.length > 0 ? (
        <DocumentsWorkspace documents={documents} collection="civil" />
      ) : (
        <div className="rounded-lg border border-dashed border-line bg-surface-raised p-8 text-sm text-ink-2">
          표시할 카탈로그가 없습니다.
          <div className="mt-2 text-xs text-ink-3">
            _database/civil_aircraft 폴더에 HTML 카탈로그를 넣은 뒤 새로고침하세요.
            {errorMessage ? <span className="ml-1">({errorMessage})</span> : null}
          </div>
        </div>
      )}
    </AppShell>
  );
}
