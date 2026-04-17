import { AdminNewsletterEditClient } from '@/components/admin/newsletter-edit-client';
import { AppShell } from '@/components/layout/app-shell';
import { requireAdminSession } from '@/lib/server-auth';
import { getAppTheme } from '@/lib/server-theme';

export const dynamic = 'force-dynamic';

type SearchParams = {
  theme?: string;
};

export default async function AdminNewsletterEditPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<SearchParams>;
}) {
  const { id } = await params;
  const query = await searchParams;
  const theme = await getAppTheme(query.theme);
  await requireAdminSession();

  return (
    <AppShell title="관리자 수정" theme={theme} themePath={`/admin/newsletters/${id}/edit`}>
      <AdminNewsletterEditClient newsletterId={Number(id)} />
    </AppShell>
  );
}
