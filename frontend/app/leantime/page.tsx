import React from 'react';

import { AppShell } from '@/components/layout/app-shell';
import { LeantimeStatus } from '@/components/office-tools/leantime-status';
import { LeantimeDashboard } from '@/components/office-tools/leantime-dashboard';
import { getAppTheme } from '@/lib/server-theme';

export const dynamic = 'force-dynamic';

const PAGE_TITLE = 'Leantime';
const PAGE_PATH = '/leantime';

type SearchParams = {
  theme?: string;
};

const SETUP_STEPS = [
  { n: 1, label: '스택 반입·설치', detail: 'AeroOne-Leantime-Stack-*.zip 을 AeroOne 형제 폴더(예: D:\\AeroOne-Leantime-Stack)에 풀고 setup-leantime-stack.bat 을 한 번 실행합니다(포터블 PHP+MariaDB, 무설치).' },
  { n: 2, label: '기동', detail: 'start-leantime-stack.bat 으로 기동합니다. scripts/run_all.bat 이 형제 폴더 스택을 자동 감지해 함께 띄울 수도 있습니다.' },
  { n: 3, label: '열기', detail: '이 화면은 대시보드에서 새 탭으로 열리며, Leantime 이 구동 중이면 이 탭이 곧바로 Leantime 으로 이동합니다. 미구동이면 이 안내가 남아 설치·기동을 돕습니다.' },
];

export default async function LeantimePage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const params = await searchParams;
  const theme = await getAppTheme(params.theme);

  return (
    <AppShell title={PAGE_TITLE} theme={theme} showThemeSelector themePath={PAGE_PATH} active="none">
      <div className="flex max-w-3xl flex-col gap-6">
        <div className="flex flex-col gap-2">
          <span className="inline-flex w-fit items-center gap-1 rounded-full bg-accent-soft px-3 py-1 text-xs font-medium text-accent">
            동거(co-deploy) 앱 · 별도 설치
          </span>
          <p className="text-sm leading-relaxed text-ink-2">
            Leantime 은 프로젝트·업무 관리 오픈소스 앱입니다. AeroOne 에 <strong>흡수하지 않고</strong> 별도 프로세스(포터블 PHP·MariaDB)로
            나란히 설치·운영하며, 대시보드는 <strong>링크로만</strong> 연결합니다. 구동 중이면 이 화면은 자동으로 새 탭에서 Leantime 으로 넘어가고, 설치·기동이 안 된 경우에만 아래 안내가 표시됩니다.
          </p>
        </div>

        <LeantimeStatus autoOpen />

        <LeantimeDashboard />

        <section className="flex flex-col gap-3 rounded-xl border border-ink-3/15 bg-surface-sunken/50 px-5 py-5">
          <h2 className="text-sm font-semibold text-ink-1">설치·기동 절차</h2>
          <ol className="flex flex-col gap-3">
            {SETUP_STEPS.map((step) => (
              <li key={step.n} className="flex items-start gap-3">
                <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-accent text-xs font-semibold text-accent-on">
                  {step.n}
                </span>
                <span className="flex flex-col">
                  <span className="text-sm font-medium text-ink-1">{step.label}</span>
                  <span className="text-xs leading-snug text-ink-3">{step.detail}</span>
                </span>
              </li>
            ))}
          </ol>
          <p className="text-xs text-ink-3">
            운영자 상세 설치 절차(포터블 스택 반입·초기화)는{' '}
            <code className="rounded bg-ink-3/10 px-1">docs/runbook/leantime-codeploy.md</code> 를 참고하세요.
          </p>
        </section>
      </div>
    </AppShell>
  );
}
