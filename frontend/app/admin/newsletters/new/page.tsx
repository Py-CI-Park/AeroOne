import { NewsletterForm } from '@/components/admin/newsletter-form';
import { AppShell } from '@/components/layout/app-shell';
import { requireAdminSession } from '@/lib/server-auth';
import { getAppTheme } from '@/lib/server-theme';

export const dynamic = 'force-dynamic';

type SearchParams = {
  theme?: string;
};

export default async function AdminNewsletterCreatePage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const params = await searchParams;
  const theme = await getAppTheme(params.theme);
  await requireAdminSession();

  return (
    <AppShell title="관리자 등록" theme={theme} themePath="/admin/newsletters/new">
      <NewsletterForm mode="create" />
    </AppShell>
  );
}
