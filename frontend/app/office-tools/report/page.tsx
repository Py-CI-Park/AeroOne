import React from 'react';

import { AppShell } from '@/components/layout/app-shell';
import { ReportForm } from '@/components/office-tools/report-form';
import { getAppTheme } from '@/lib/server-theme';

export const dynamic = 'force-dynamic';

const PAGE_TITLE = '보고서 스튜디오';
const PAGE_PATH = '/office-tools/report';
const PAGE_DESCRIPTION = 'Markdown 을 사내 표준 HTML 보고서로 변환합니다.';

type SearchParams = {
  theme?: string;
};

export default async function OfficeReportPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const params = await searchParams;
  const theme = await getAppTheme(params.theme);

  return (
    <AppShell title={PAGE_TITLE} theme={theme} showThemeSelector themePath={PAGE_PATH} active="none">
      <div className="flex flex-col gap-4">
        <p className="text-sm text-ink-3">{PAGE_DESCRIPTION}</p>
        <ReportForm />
      </div>
    </AppShell>
  );
}
