import React from 'react';

import { AppShell } from '@/components/layout/app-shell';
import { ViewerEditor } from '@/components/viewer/viewer-editor';
import { getAppTheme } from '@/lib/server-theme';

export const dynamic = 'force-dynamic';

const PAGE_TITLE = 'Viewer';
const PAGE_PATH = '/viewer';

type SearchParams = {
  theme?: string;
};

export default async function ViewerPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const params = await searchParams;
  const theme = await getAppTheme(params.theme);

  return (
    <AppShell
      title={PAGE_TITLE}
      theme={theme}
      showThemeSelector
      themePath={PAGE_PATH}
      active="none"
    >
      <ViewerEditor />
    </AppShell>
  );
}
