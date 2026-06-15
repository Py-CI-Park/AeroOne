import { AppShell } from '@/components/layout/app-shell';
import { ServiceCard } from '@/components/dashboard/service-card';
import { NotebookLinkCard } from '@/components/dashboard/notebook-link-card';
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
    section: 'Newsletter',
  },
  {
    id: 'civil-aircraft',
    title: 'Civil Aircraft Spec Catalog',
    description: 'Commercial aircraft specs & market competition analysis.',
    href: '/reports/civil-aircraft',
    badge: 'Active',
    active: true,
    section: 'Document',
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
    section: 'Document',
  },
  {
    id: 'nsa',
    title: 'NSA',
    description: 'Password-protected HTML documents.',
    href: '/nsa',
    badge: 'Active',
    active: true,
    section: 'Document',
  },
  {
    id: 'ai',
    title: 'AeroAI',
    description: '사내 폐쇄망 문서를 근거로 답하는 AI 어시스턴트.',
    href: '/ai',
    badge: 'Active',
    active: true,
    section: 'AeroAI',
  },
  {
    id: 'open-notebook',
    title: 'Notebook',
    description: 'NotebookLM 대안 — 소스 정리·요약·벡터 검색 (별도 폐쇄망 앱).',
    // href 는 NotebookLinkCard 가 window.location.hostname 으로 직접 생성하므로 비워 둔다(external 분기에서 module.href 미사용).
    href: '',
    badge: 'Active',
    active: true,
    section: 'AeroAI',
    external: true,
  },
  {
    id: 'ladder',
    title: 'Ladder',
    description: 'Coffee-bet ladder game (사다리타기).',
    href: '/games/ladder',
    badge: 'Active',
    active: true,
    section: 'etc',
  },
] as const;

const ACTIVE_SECTION_ORDER = ['Newsletter', 'Document', 'AeroAI', 'etc'] as const;

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
  const activeModules = MODULES.filter((module) => module.active);
  const comingModules = MODULES.filter((module) => !module.active);

  return (
    <AppShell
      title="Dashboard"
      theme={theme}
      themePath="/"
      active="dashboard"
      titleMeta={`${activeCount} active · ${comingCount} coming soon`}
    >
      <section className="flex flex-col gap-8">
        {ACTIVE_SECTION_ORDER.map((sectionName) => {
          const sectionModules = activeModules.filter((module) => module.section === sectionName);
          if (sectionModules.length === 0) return null;
          return (
            <div key={sectionName}>
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-ink-3">{sectionName}</h2>
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
                {sectionModules.map((module) =>
                  'external' in module && module.external ? (
                    <NotebookLinkCard
                      key={module.id}
                      title={module.title}
                      description={'description' in module ? module.description : undefined}
                      badge={module.badge}
                    />
                  ) : (
                    <ServiceCard
                      key={module.id}
                      title={module.title}
                      description={'description' in module ? module.description : undefined}
                      href={module.href}
                      badge={module.badge}
                      active={module.active}
                    />
                  ),
                )}
              </div>
            </div>
          );
        })}

        {comingModules.length > 0 ? (
          <div>
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-ink-3">Coming soon</h2>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
              {comingModules.map((module) => (
                <ServiceCard
                  key={module.id}
                  title={module.title}
                  description={'description' in module ? module.description : undefined}
                  href={module.href}
                  badge={module.badge}
                  active={module.active}
                />
              ))}
            </div>
          </div>
        ) : null}
      </section>
    </AppShell>
  );
}
