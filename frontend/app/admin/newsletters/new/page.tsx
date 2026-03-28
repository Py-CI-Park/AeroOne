import { AppShell } from '@/components/layout/app-shell';
import { NewsletterForm } from '@/components/admin/newsletter-form';

export default function AdminNewsletterCreatePage() {
  return (
    <AppShell title="관리자 등록">
      <NewsletterForm mode="create" />
    </AppShell>
  );
}
