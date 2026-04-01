import { AppShell } from '@/components/layout/app-shell';
import { ImportPanel } from '@/components/admin/import-panel';
import { requireAdminSession } from '@/lib/server-auth';

export const dynamic = 'force-dynamic';

export default async function AdminImportsPage() {
  await requireAdminSession();
  return (
    <AppShell title="Import / Sync">
      <ImportPanel />
    </AppShell>
  );
}
