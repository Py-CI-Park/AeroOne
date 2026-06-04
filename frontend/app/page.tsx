import { AppShell } from '@/components/layout/app-shell';
import { ServiceCard } from '@/components/dashboard/service-card';
import { getAppTheme } from '@/lib/server-theme';

type SearchParams = {
  theme?: string;
};

const MODULES = [
  {
    id: 'newsletter',
    title: 'Newsletter',
    href: '/newsletters',
    badge: 'Active',
    active: true,
  },
  {
    id: 'civil-aircraft',
    title: 'Civil Aircraft Spec Catalog',
    description: 'Commercial aircraft specs & market competition analysis.',
    href: '/reports/civil-aircraft',
    badge: 'Active',
    active: true,
  },
  {
    id: 'announcement',
    title: 'Announcement',
    description: 'Company-wide announcements module.',
    // 비활성 모듈 — ServiceCard 가 active:false 를 비링크 div 로 렌더하므로 이동하지 않는다.
    // href 는 '/newsletters' 오인 연결 대신 무의미 앵커로 둔다.
    href: '#',
    badge: 'Coming soon',
    active: false,
  },
  {
    id: 'schedule',
    title: 'Schedule',
    description: 'Shared calendar & event tracking.',
    href: '#',
    badge: 'Coming soon',
    active: false,
  },
  {
    id: 'document',
    title: 'Document',
    description: 'Browse HTML documents organized in folders.',
    href: '/documents',
    badge: 'Active',
    active: true,
  },
] as const;

export default async function HomePage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const params = await searchParams;
  const theme = await getAppTheme(params.theme);

  // 카운트는 MODULES 에서 파생 — 카드를 늘려도 상단 요약이 자동으로 맞는다.
  const activeCount = MODULES.filter((module) => module.active).length;
  const comingCount = MODULES.length - activeCount;

  return (
    <AppShell
      title="Dashboard"
      theme={theme}
      themePath="/"
      active="dashboard"
      titleMeta={`${activeCount} active · ${comingCount} coming soon`}
    >
      <section className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        {MODULES.map((module) => (
          <ServiceCard
            key={module.id}
            title={module.title}
            description={'description' in module ? module.description : undefined}
            href={module.href}
            badge={module.badge}
            active={module.active}
          />
        ))}
      </section>
    </AppShell>
  );
}
