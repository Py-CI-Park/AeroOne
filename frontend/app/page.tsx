import { AppShell } from '@/components/layout/app-shell';
import { ServiceCard } from '@/components/dashboard/service-card';

export default function HomePage() {
  return (
    <AppShell title="서비스 대시보드">
      <section className="mb-8 rounded-2xl bg-gradient-to-r from-slate-900 via-slate-800 to-slate-700 p-8 text-white shadow-lg">
        <p className="text-sm font-medium uppercase tracking-[0.2em] text-slate-300">AeroOne Internal Platform</p>
        <h2 className="mt-3 text-3xl font-semibold">사내 문서형 서비스 시작점</h2>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-200">
          현재는 뉴스레터 서비스부터 시작합니다. 향후 공지, 일정, 문서 발행, 내부 도구 서비스가 같은 대시보드에 차례로 추가될 예정입니다.
        </p>
      </section>

      <section className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
        <ServiceCard
          title="뉴스레터 서비스"
          description="가장 최신 뉴스레터를 바로 열고, 발행 날짜별로 이전 뉴스레터를 탐색합니다."
          href="/newsletters"
          badge="활성 서비스"
          icon="📰"
        />
      </section>
    </AppShell>
  );
}
