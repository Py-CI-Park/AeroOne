import React from 'react';

import { AppShell } from '@/components/layout/app-shell';
import { CollectionPasswordGate } from '@/components/collections/collection-password-gate';
import { getAppTheme } from '@/lib/server-theme';

export const dynamic = 'force-dynamic';

const PAGE_TITLE = 'NSA';
const PAGE_PATH = '/nsa';

type SearchParams = {
  theme?: string;
};

export default async function NsaPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const params = await searchParams;
  const theme = await getAppTheme(params.theme);

  return (
    <AppShell
      title={PAGE_TITLE}
      contentClassName="max-w-[1600px]"
      theme={theme}
      showThemeSelector
      themePath={PAGE_PATH}
      active="none"
    >
      <CollectionPasswordGate collection="nsa" title="NSA" />
    </AppShell>
  );
}
