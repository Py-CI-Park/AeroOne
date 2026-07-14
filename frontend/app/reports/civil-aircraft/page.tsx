import { cookies } from 'next/headers';

import { AppShell } from '@/components/layout/app-shell';
import { NEWSLETTER_THEME_COOKIE, resolveNewsletterThemeFromSearchParam } from '@/lib/theme';

export const dynamic = 'force-dynamic';

const REPORT_TITLE = 'Civil Aircraft Spec Catalog';
const REPORT_PATH = '/reports/civil-aircraft';
// Same-origin proxy entry for the bundled interactive v1.7 dashboard. Relative links
// inside the bundle (assets/, apps/, data/) resolve under this base and are proxied
// back to the backend static-app route, which enforces a self-only CSP.
const APP_SRC = '/api/frontend/reports/civil-aircraft/app/';

type SearchParams = {
  theme?: string;
};

export default async function CivilAircraftReportPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const params = await searchParams;
  const cookieStore = await cookies();
  const cookieTheme = cookieStore.getAll().find((cookie) => cookie.name === NEWSLETTER_THEME_COOKIE)?.value;
  const theme = resolveNewsletterThemeFromSearchParam(params.theme, process.env.NEWSLETTERS_THEME, cookieTheme);

  return (
    <AppShell
      title={REPORT_TITLE}
      contentClassName="max-w-[1600px]"
      theme={theme}
      showThemeSelector
      themePath={REPORT_PATH}
      active="none"
      titleMeta="v1.7 Encyclopedia · Comparison · Sources"
    >
      <div className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-ink-2">
            민간 항공기 백과 · 비교 대시보드 · 출처 아카이브 (v1.7). 아래에서 바로 탐색하거나 새 창으로 크게 볼 수 있습니다.
          </p>
          <a
            href={APP_SRC}
            target="_blank"
            rel="noopener noreferrer"
            className="shrink-0 rounded-md border border-line bg-surface-raised px-3 py-1.5 text-sm font-medium text-ink-1 hover:bg-surface"
          >
            새 창으로 열기 ↗
          </a>
        </div>
        <iframe
          title="Civil Aircraft Data Portal v1.7"
          src={APP_SRC}
          className="h-[calc(100dvh-11rem)] min-h-[600px] w-full rounded-lg border border-line bg-white"
          sandbox="allow-scripts allow-same-origin allow-popups allow-downloads allow-modals allow-forms"
        />
      </div>
    </AppShell>
  );
}
