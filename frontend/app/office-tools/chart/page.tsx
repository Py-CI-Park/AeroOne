import React from 'react';

import { AppShell } from '@/components/layout/app-shell';
import { ChartForm } from '@/components/office-tools/chart-form';
import { getAppTheme } from '@/lib/server-theme';

export const dynamic = 'force-dynamic';

const PAGE_TITLE = '차트 스튜디오';
const PAGE_PATH = '/office-tools/chart';
const PAGE_DESCRIPTION = 'CSV·표 데이터를 ECharts 차트로 시각화합니다.';

type SearchParams = {
  theme?: string;
};

export default async function OfficeChartPage({
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
        <ChartForm />
      </div>
    </AppShell>
  );
}
