import React from 'react';

import { AppShell } from '@/components/layout/app-shell';
import { OfficeToolsHub, type OfficeToolKey } from '@/components/office-tools/office-tools-hub';
import { getAppTheme } from '@/lib/server-theme';

export const dynamic = 'force-dynamic';

const PAGE_TITLE = 'Office Studio';
const PAGE_PATH = '/office-tools';
const VALID_TABS: OfficeToolKey[] = ['diagram', 'chart', 'report'];

type SearchParams = {
  theme?: string;
  tab?: string;
};

export default async function OfficeToolsPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const params = await searchParams;
  const theme = await getAppTheme(params.theme);
  const initialTab = VALID_TABS.includes(params.tab as OfficeToolKey)
    ? (params.tab as OfficeToolKey)
    : 'diagram';

  return (
    <AppShell title={PAGE_TITLE} theme={theme} showThemeSelector themePath={PAGE_PATH} active="none">
      <div className="flex flex-col gap-4">
        <p className="text-sm text-ink-3">
          보고서·차트·다이어그램을 한 곳에서. 각 탭에서 &apos;예제 불러오기&apos;로 샘플 데이터를 바로 실행해 볼 수 있습니다.
        </p>
        <OfficeToolsHub initialTab={initialTab} />
      </div>
    </AppShell>
  );
}
