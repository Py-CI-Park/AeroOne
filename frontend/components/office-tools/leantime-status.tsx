'use client';

import React from 'react';

import { fetchLeantimeHealth } from '@/lib/api';
import type { LeantimeHealth } from '@/lib/types';
import { LeantimeLaunch } from '@/components/office-tools/leantime-launch';

type Phase = 'checking' | 'up' | 'down' | 'error';

/**
 * Leantime 동거 스택의 실시간 상태 + 열기 버튼.
 *
 * 마운트 시 백엔드 헬스(127.0.0.1:8081 TCP 프로브)를 조회해 '구동 중 / 미설치·미구동'을
 * 배지로 구분해 보여 준다. 구동 중일 때만 '열기'를 활성화해, 미설치 상태에서 눌러 빈 화면이
 * 뜨는 혼란을 없앤다(사용자 보고 대응). '다시 확인' 으로 설치 직후 재조회할 수 있다.
 */
export function LeantimeStatus() {
  const [phase, setPhase] = React.useState<Phase>('checking');
  const [health, setHealth] = React.useState<LeantimeHealth | null>(null);

  const check = React.useCallback(() => {
    setPhase('checking');
    fetchLeantimeHealth()
      .then((result) => {
        setHealth(result);
        setPhase(result.status === 'up' ? 'up' : 'down');
      })
      .catch(() => {
        setHealth(null);
        setPhase('error');
      });
  }, []);

  React.useEffect(() => {
    check();
  }, [check]);

  const port = health?.port ?? 8081;
  const target = health?.probe_target ?? '127.0.0.1:8081';

  return (
    <section
      className="flex flex-col gap-4 rounded-xl border border-ink-3/15 bg-surface-raised/40 px-5 py-5"
      data-testid="leantime-status"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <StatusBadge phase={phase} />
          <span className="text-xs text-ink-3">감지 대상 {target}</span>
        </div>
        <button
          type="button"
          onClick={check}
          disabled={phase === 'checking'}
          className="rounded-md border border-ink-3/40 px-3 py-1.5 text-xs font-medium text-ink-1 transition hover:bg-ink-3/10 disabled:opacity-50"
        >
          {phase === 'checking' ? '확인 중…' : '다시 확인'}
        </button>
      </div>

      <p className="text-sm leading-relaxed text-ink-2">
        {phase === 'up'
          ? 'Leantime 이 구동 중입니다. 아래 버튼으로 새 탭에서 엽니다.'
          : phase === 'checking'
            ? '구동 여부를 확인하는 중입니다…'
            : 'Leantime 이 아직 설치·기동되지 않았습니다. 아래 설치 절차를 마친 뒤 “다시 확인”을 누르면 활성화됩니다.'}
      </p>

      <LeantimeLaunch port={port} enabled={phase === 'up'} />
    </section>
  );
}

function StatusBadge({ phase }: { phase: Phase }) {
  if (phase === 'up') {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/15 px-3 py-1 text-xs font-semibold text-emerald-600">
        <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" /> 구동 중
      </span>
    );
  }
  if (phase === 'checking') {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-ink-3/10 px-3 py-1 text-xs font-semibold text-ink-3">
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-ink-3" /> 확인 중
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-500/15 px-3 py-1 text-xs font-semibold text-amber-600">
      <span className="h-1.5 w-1.5 rounded-full bg-amber-500" /> 미설치 · 미구동
    </span>
  );
}
