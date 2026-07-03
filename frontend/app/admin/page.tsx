import { AdminHomeConsole } from '@/components/admin/admin-home-console';
import { AppShell } from '@/components/layout/app-shell';
import { requireAdminSession } from '@/lib/server-auth';
import { getAppTheme } from '@/lib/server-theme';

export const dynamic = 'force-dynamic';

type SearchParams = {
  theme?: string;
};

export default async function AdminHomePage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const params = await searchParams;
  const theme = await getAppTheme(params.theme);
  await requireAdminSession();

  return (
    <AppShell title="관리자 콘솔" theme={theme} themePath="/admin" active="admin" contentClassName="max-w-7xl">
      <AdminHomeConsole />
    </AppShell>
  );
}
