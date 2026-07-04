import { cookies } from 'next/headers';

import { AppShell } from '@/components/layout/app-shell';
import { ServiceCard } from '@/components/dashboard/service-card';
import { NotebookLinkCard } from '@/components/dashboard/notebook-link-card';
import { fetchPublicServiceModules } from '@/lib/api';
import { resolveIsAdmin } from '@/lib/server-auth';
import { getAppTheme } from '@/lib/server-theme';
import type { ServiceModule } from '@/lib/types';

type SearchParams = {
  theme?: string;
};

const FALLBACK_MODULES: ServiceModule[] = [
  { id: 1, key: 'newsletter', title: 'Newsletter', href: '/newsletters', badge: 'Active', is_enabled: true, section: 'Newsletter', status: 'active', sort_order: 10, is_external: false, visibility: 'public' },
  { id: 2, key: 'civil-aircraft', title: 'Civil Aircraft Spec Catalog', description: 'Commercial aircraft specs & market competition analysis.', href: '/reports/civil-aircraft', badge: 'Active', is_enabled: true, section: 'Document', status: 'active', sort_order: 20, is_external: false, visibility: 'public' },
  { id: 3, key: 'document', title: 'Document', description: 'Browse HTML documents organized in folders.', href: '/documents', badge: 'Active', is_enabled: true, section: 'Document', status: 'active', sort_order: 30, is_external: false, visibility: 'public' },
  { id: 4, key: 'nsa', title: 'NSA', description: 'Access-controlled HTML documents.', href: '/nsa', badge: 'Active', is_enabled: true, section: 'Document', status: 'active', sort_order: 40, is_external: false, visibility: 'public', required_permission: 'collections.nsa.read', resource_type: 'collection', resource_id: 'nsa' },
  { id: 5, key: 'viewer', title: 'Viewer', description: '로컬 Markdown·HTML 파일을 열어 보고 편집 (서버 sanitize 미리보기).', href: '/viewer', badge: 'Active', is_enabled: true, section: 'Development', status: 'development', sort_order: 50, is_external: false, visibility: 'admin' },
  { id: 6, key: 'ai', title: 'AeroAI', description: '사내 폐쇄망 문서를 근거로 답하는 AI 어시스턴트.', href: '/ai', badge: 'Active', is_enabled: true, section: 'Development', status: 'development', sort_order: 60, is_external: false, visibility: 'admin' },
  { id: 7, key: 'open-notebook', title: 'Notebook', description: 'NotebookLM 대안 — 소스 정리·요약·벡터 검색 (별도 폐쇄망 앱).', href: '', badge: 'Active', is_enabled: true, section: 'Development', status: 'development', sort_order: 70, is_external: true, visibility: 'admin' },
  { id: 8, key: 'ladder', title: 'Ladder', description: 'Coffee-bet ladder game (사다리타기).', href: '/games/ladder', badge: 'Active', is_enabled: true, section: 'Development', status: 'development', sort_order: 80, is_external: false, visibility: 'admin' },
  { id: 9, key: 'announcement', title: 'Announcement', description: 'Company-wide announcements module.', href: '#', badge: 'Coming soon', is_enabled: false, section: 'Development', status: 'coming_soon', sort_order: 90, is_external: false, visibility: 'admin' },
  { id: 10, key: 'schedule', title: 'Schedule', description: 'Shared calendar & event tracking.', href: '#', badge: 'Coming soon', is_enabled: false, section: 'Development', status: 'coming_soon', sort_order: 100, is_external: false, visibility: 'admin' },
];

const SECTION_ORDER = ['Newsletter', 'Document', 'Development'];

function orderSections(modules: ServiceModule[]) {
  const extras = modules.map((module) => module.section).filter((section) => !SECTION_ORDER.includes(section));
  return [...SECTION_ORDER, ...Array.from(new Set(extras))];
}

async function loadModules(cookieHeader: string): Promise<{ modules: ServiceModule[]; degraded: boolean }> {
  try {
    const modules = await fetchPublicServiceModules(cookieHeader || undefined);
    return { modules, degraded: false };
  } catch {
    return { modules: FALLBACK_MODULES, degraded: true };
  }
}

export default async function HomePage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const params = await searchParams;
  const theme = await getAppTheme(params.theme);
  const cookieHeader = cookies()
    .getAll()
    .map((cookie) => `${cookie.name}=${cookie.value}`)
    .join('; ');
  const isAdmin = await resolveIsAdmin();
  const { modules, degraded } = await loadModules(cookieHeader);
  // The live SSR path is already backend-filtered per caller (visibility + required_permission +
  // resource/collection policy), so trust it as-is. Only the degraded/fallback list has no
  // per-user info, so conservatively drop operator-only (non-public) and permission-gated cards
  // for non-admins there.
  const visibleModules = degraded
    ? modules.filter((module) => isAdmin || (module.visibility === 'public' && !module.required_permission))
    : modules;
  const sortedModules = [...visibleModules].sort((a, b) => a.sort_order - b.sort_order || a.title.localeCompare(b.title));
  const activeCount = sortedModules.filter((module) => module.is_enabled).length;
  const comingCount = sortedModules.filter((module) => module.status === 'coming_soon' || !module.is_enabled).length;

  return (
    <AppShell
      title="Dashboard"
      theme={theme}
      themePath="/"
      active="dashboard"
      titleMeta={`${activeCount} active · ${comingCount} coming soon`}
    >
      <section className="flex flex-col gap-8">
        {degraded ? (
          <div className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            대시보드 모듈 DB 를 읽지 못해 내장 fallback 목록을 표시합니다. 관리자 화면에서 DB 상태와
            service_modules migration 을 확인하세요.
          </div>
        ) : null}
        {orderSections(sortedModules).map((sectionName) => {
          const sectionModules = sortedModules.filter((module) => module.section === sectionName);
          if (sectionModules.length === 0) return null;
          return (
            <div key={sectionName}>
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-ink-3">{sectionName}</h2>
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
                {sectionModules.map((module) =>
                  module.is_external ? (
                    <NotebookLinkCard
                      key={module.key}
                      title={module.title}
                      description={module.description ?? undefined}
                      badge={module.badge}
                      href={module.href}
                      active={module.is_enabled}
                    />
                  ) : (
                    <ServiceCard
                      key={module.key}
                      title={module.title}
                      description={module.description ?? undefined}
                      href={module.href}
                      badge={module.badge}
                      active={module.is_enabled}
                    />
                  ),
                )}
              </div>
            </div>
          );
        })}
      </section>
    </AppShell>
  );
}
