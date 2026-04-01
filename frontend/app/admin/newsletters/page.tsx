import { AppShell } from '@/components/layout/app-shell';
import { AdminNewsletterList } from '@/components/admin/admin-newsletter-list';
import { requireAdminSession } from '@/lib/server-auth';

export const dynamic = 'force-dynamic';

export default async function AdminNewslettersPage() {
  await requireAdminSession();
  return (
    <AppShell title="관리자 뉴스레터 목록">
      <AdminNewsletterList />
    </AppShell>
  );
}
