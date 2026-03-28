import { AppShell } from '@/components/layout/app-shell';
import { AdminNewsletterEditClient } from '@/components/admin/newsletter-edit-client';

export default async function AdminNewsletterEditPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <AppShell title="관리자 수정">
      <AdminNewsletterEditClient newsletterId={Number(id)} />
    </AppShell>
  );
}
