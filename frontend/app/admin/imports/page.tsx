import { ImportPanel } from '@/components/admin/import-panel';
import { AppShell } from '@/components/layout/app-shell';
import { requireAdminSession } from '@/lib/server-auth';
import { getAppTheme } from '@/lib/server-theme';

export const dynamic = 'force-dynamic';

type SearchParams = {
  theme?: string;
};

export default async function AdminImportsPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const params = await searchParams;
  const theme = await getAppTheme(params.theme);
  await requireAdminSession();

  return (
    <AppShell title="Import / Sync" theme={theme} themePath="/admin/imports">
      <ImportPanel />
    </AppShell>
  );
}
