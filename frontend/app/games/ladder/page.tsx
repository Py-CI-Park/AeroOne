import React from 'react';

import { AppShell } from '@/components/layout/app-shell';
import { LadderGame } from '@/components/games/ladder-game';
import { getAppTheme } from '@/lib/server-theme';

export const dynamic = 'force-dynamic';

const PAGE_TITLE = '사다리 게임';
const PAGE_PATH = '/games/ladder';

type SearchParams = {
  theme?: string;
};

export default async function LadderPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const params = await searchParams;
  const theme = await getAppTheme(params.theme);

  return (
    <AppShell
      title={PAGE_TITLE}
      contentClassName="max-w-3xl"
      theme={theme}
      showThemeSelector
      themePath={PAGE_PATH}
      active="none"
    >
      <LadderGame />
    </AppShell>
  );
}
