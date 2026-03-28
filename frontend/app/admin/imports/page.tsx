import { AppShell } from '@/components/layout/app-shell';
import { ImportPanel } from '@/components/admin/import-panel';

export default function AdminImportsPage() {
  return (
    <AppShell title="Import / Sync">
      <ImportPanel />
    </AppShell>
  );
}
