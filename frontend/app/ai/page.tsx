import React from 'react';

import { AiChatWorkspace } from '@/components/ai/ai-chat-workspace';
import { AppShell } from '@/components/layout/app-shell';
import { getAppTheme } from '@/lib/server-theme';

export const dynamic = 'force-dynamic';

const PAGE_TITLE = 'AeroAI';
const PAGE_PATH = '/ai';

type SearchParams = {
  theme?: string;
};

export default async function AiPage({
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
      titleMeta="사내 폐쇄망 AI"
    >
      <AiChatWorkspace />
    </AppShell>
  );
}
