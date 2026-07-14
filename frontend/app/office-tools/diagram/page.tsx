import React from 'react';

import { AppShell } from '@/components/layout/app-shell';
import { DiagramForm } from '@/components/office-tools/diagram-form';
import { getAppTheme } from '@/lib/server-theme';

export const dynamic = 'force-dynamic';

const PAGE_TITLE = '다이어그램 스튜디오';
const PAGE_PATH = '/office-tools/diagram';
const PAGE_DESCRIPTION = '설명을 Mermaid 다이어그램으로 생성합니다.';

type SearchParams = {
  theme?: string;
};

export default async function OfficeDiagramPage({
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
        <DiagramForm />
      </div>
    </AppShell>
  );
}
