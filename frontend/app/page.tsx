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
          title="뉴스레터 서비스"
          description="가장 최신 뉴스레터를 바로 열고, 발행 날짜별로 이전 뉴스레터를 탐색합니다."
          href="/newsletters"
          badge="활성 서비스"
        />
      </section>
    </AppShell>
  );
}
