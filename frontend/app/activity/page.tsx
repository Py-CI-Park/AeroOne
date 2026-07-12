import React from 'react';

import { ActivityWorkspace } from '@/components/activity/activity-workspace';
import { AppShell } from '@/components/layout/app-shell';
import { getAppTheme } from '@/lib/server-theme';

export const dynamic = 'force-dynamic';

const PAGE_TITLE = '내 활동';
const PAGE_PATH = '/activity';

type SearchParams = {
  theme?: string;
};

export default async function ActivityPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const params = await searchParams;
  const theme = await getAppTheme(params.theme);

  return (
    <AppShell
      title={PAGE_TITLE}
      contentClassName="max-w-4xl"
      theme={theme}
      showThemeSelector
      themePath={PAGE_PATH}
      active="none"
    >
      <ActivityWorkspace />
    </AppShell>
  );
}
