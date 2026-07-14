'use client';

import React from 'react';

import { fetchLeantimeHealth } from '@/lib/api';
import type { LeantimeHealth } from '@/lib/types';
import { LeantimeLaunch } from '@/components/office-tools/leantime-launch';

type Phase = 'checking' | 'ready' | 'unhealthy' | 'starting' | 'absent' | 'error';

/**
 * Leantime 동거 스택의 실시간 상태 + 열기 버튼.
 *
 * 마운트 시 백엔드 헬스(HTTP 기반 준비성 + 앱 식별)를 조회해 5가지 상태(구동 중 / 기동 중 /
 * 응답 이상 / 미설치·미구동 / 확인 실패)를 배지로 구분해 보여 준다. 'ready' 일 때만 '열기'를
 * 활성화해, 아직 뜨지 않은 화면으로 이동하는 혼란을 없앤다. '다시 확인' 으로 재조회할 수 있다.
 */
export function LeantimeStatus() {
  const [phase, setPhase] = React.useState<Phase>('checking');
  const [health, setHealth] = React.useState<LeantimeHealth | null>(null);

  const check = React.useCallback(() => {
    setPhase('checking');
    fetchLeantimeHealth()
      .then((result) => {
        setHealth(result);
        setPhase(result.status);
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
  const detail = health?.detail;
  const latency = health?.latency_ms;

  const guidance = (() => {
    switch (phase) {
      case 'ready':
        return 'Leantime 이 구동 중입니다. 아래 버튼으로 새 탭에서 엽니다.';
      case 'checking':
        return '구동 여부를 확인하는 중입니다…';
      case 'starting':
        return 'Leantime 이 기동 중인 것으로 보입니다. 잠시 후 “다시 확인”을 눌러 주세요.';
      case 'unhealthy':
        return 'Leantime 응답이 정상이 아닙니다. 아래 상세 사유를 확인한 뒤 “다시 확인”을 눌러 주세요.';
      case 'error':
        return '상태 확인에 실패했습니다. 네트워크 또는 백엔드 설정을 확인한 뒤 “다시 확인”을 눌러 주세요.';
      case 'absent':
      default:
        return 'Leantime 이 아직 설치·기동되지 않았습니다. 아래 설치 절차를 마친 뒤 “다시 확인”을 누르면 활성화됩니다.';
    }
  })();

  return (
    <section
      className="flex flex-col gap-4 rounded-xl border border-ink-3/15 bg-surface-raised/40 px-5 py-5"
      data-testid="leantime-status"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <StatusBadge phase={phase} />
          <span className="text-xs text-ink-3">감지 대상 {target}</span>
          {typeof latency === 'number' && (
            <span className="text-xs text-ink-3">({latency}ms)</span>
          )}
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

      <p className="text-sm leading-relaxed text-ink-2">{guidance}</p>

      {detail && (phase === 'unhealthy' || phase === 'error' || phase === 'starting') && (
        <p className="text-xs leading-relaxed text-ink-3">사유: {detail}</p>
      )}

      <LeantimeLaunch port={port} enabled={phase === 'ready'} launchUrl={health?.launch_url} />
    </section>
  );
}

function StatusBadge({ phase }: { phase: Phase }) {
  if (phase === 'ready') {
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
  if (phase === 'starting') {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-sky-500/15 px-3 py-1 text-xs font-semibold text-sky-600">
        <span className="h-1.5 w-1.5 rounded-full bg-sky-500" /> 기동 중
      </span>
    );
  }
  if (phase === 'unhealthy') {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-500/15 px-3 py-1 text-xs font-semibold text-amber-600">
        <span className="h-1.5 w-1.5 rounded-full bg-amber-500" /> 응답 이상
      </span>
    );
  }
  if (phase === 'error') {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-rose-500/15 px-3 py-1 text-xs font-semibold text-rose-600">
        <span className="h-1.5 w-1.5 rounded-full bg-rose-500" /> 확인 실패
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-ink-3/10 px-3 py-1 text-xs font-semibold text-ink-3">
      <span className="h-1.5 w-1.5 rounded-full bg-ink-3/60" /> 미설치 · 미구동
    </span>
  );
}
