import { AppShell } from '@/components/layout/app-shell';
import { ServiceCard } from '@/components/dashboard/service-card';

export default function HomePage() {
  return (
    <AppShell title="서비스 대시보드">
      <section className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
        <ServiceCard
          title="뉴스레터 서비스"
          description="가장 최신 뉴스레터를 바로 보고, 발행 날짜별로 이전 뉴스레터를 탐색합니다."
          href="/newsletters"
          badge="우선 제공"
          icon="🗞"
        />
      </section>
    </AppShell>
  );
}
