import { AppShell } from '@/components/layout/app-shell';
import { ServiceCard } from '@/components/dashboard/service-card';
import { getAppTheme } from '@/lib/server-theme';

type SearchParams = {
  theme?: string;
};

export default async function HomePage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const params = await searchParams;
  const theme = await getAppTheme(params.theme);

  return (
    <AppShell title="서비스 대시보드" theme={theme} themePath="/">
      <section className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
        <ServiceCard
          title="Newsletter"
          description="Open the latest issue and browse previous issues by date."
          href="/newsletters"
          badge="활성 서비스"
        />
      </section>
    </AppShell>
  );
}
