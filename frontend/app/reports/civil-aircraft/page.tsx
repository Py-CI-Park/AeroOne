import React from 'react';
import { cookies } from 'next/headers';

import { AppShell } from '@/components/layout/app-shell';
import { CivilAircraftReport } from '@/components/reports/civil-aircraft-report';
import { fetchCivilAircraftReport } from '@/lib/api';
import { NEWSLETTER_THEME_COOKIE, resolveNewsletterThemeFromSearchParam } from '@/lib/theme';

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
  let html = '';
  let errorMessage = '';

  try {
    const payload = await fetchCivilAircraftReport();
    html = payload.content_html;
  } catch (error) {
    errorMessage = error instanceof Error ? error.message : '보고서를 불러오지 못했습니다.';
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
    >
      {html ? (
        <CivilAircraftReport title={REPORT_TITLE} html={html} />
      ) : (
        <div className="rounded-lg border border-dashed border-line bg-surface-raised p-8 text-sm text-ink-2">
          표시할 보고서가 없습니다.
          <div className="mt-2 text-xs text-ink-3">
            _database/civil_aircraft 폴더에 HTML 보고서를 넣은 뒤 페이지를 새로고침하세요.
            {errorMessage ? <span className="ml-1">({errorMessage})</span> : null}
          </div>
        </div>
      )}
    </AppShell>
  );
}
