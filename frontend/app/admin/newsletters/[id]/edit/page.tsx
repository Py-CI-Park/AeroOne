import { AppShell } from '@/components/layout/app-shell';
import { AdminNewsletterEditClient } from '@/components/admin/newsletter-edit-client';
import { requireAdminSession } from '@/lib/server-auth';

export const dynamic = 'force-dynamic';

export default async function AdminNewsletterEditPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  await requireAdminSession();
  return (
    <AppShell title="관리자 수정">
      <AdminNewsletterEditClient newsletterId={Number(id)} />
    </AppShell>
  );
}
