import { AppShell } from '@/components/layout/app-shell';
import { NewsletterForm } from '@/components/admin/newsletter-form';
import { requireAdminSession } from '@/lib/server-auth';

export const dynamic = 'force-dynamic';

export default async function AdminNewsletterCreatePage() {
  await requireAdminSession();
  return (
    <AppShell title="관리자 등록">
      <NewsletterForm mode="create" />
    </AppShell>
  );
}
