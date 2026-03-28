import { AppShell } from '@/components/layout/app-shell';
import { NewsletterList } from '@/components/newsletter/newsletter-list';
import { fetchNewsletters } from '@/lib/api';

export const dynamic = 'force-dynamic';

export default async function NewslettersPage() {
  const items = await fetchNewsletters().catch(() => []);
  return (
    <AppShell title="뉴스레터 목록">
      <NewsletterList items={items} />
    </AppShell>
  );
}
