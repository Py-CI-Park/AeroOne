import { AppShell } from '@/components/layout/app-shell';
import { AdminNewsletterList } from '@/components/admin/admin-newsletter-list';

export default function AdminNewslettersPage() {
  return (
    <AppShell title="관리자 뉴스레터 목록">
      <AdminNewsletterList />
    </AppShell>
  );
}
