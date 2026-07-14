'use client';

import React from 'react';

import {
  ApiError,
  fetchLeantimeCalendar,
  fetchLeantimeProjects,
  fetchLeantimeTasks,
} from '@/lib/api';
import type {
  LeantimeCalendarEntry,
  LeantimeProject,
  LeantimeReadResponse,
  LeantimeTask,
} from '@/lib/types';
import { formatRelativeTime } from '@/lib/relative-time';

const CALENDAR_WINDOW_DAYS = 30;


type ResourceState<T> =
  | { status: 'loading' }
  | { status: 'ready'; data: LeantimeReadResponse<T> }
  | { status: 'forbidden' }
  | { status: 'unauthorized' }
  | { status: 'error'; message: string };

const REASON_GUIDANCE: Record<string, string> = {
  not_configured: 'Leantime 연동이 아직 구성되지 않았습니다. 관리자에게 설정을 요청하세요.',
  credential_error: 'Leantime 접속 자격 증명에 문제가 있습니다. 관리자에게 문의하세요.',
  auth_failed: 'Leantime 인증에 실패했습니다. 관리자에게 문의하세요.',
  upstream_unavailable: 'Leantime 서버에 연결할 수 없습니다. 잠시 후 다시 시도하세요.',
};

function reasonGuidance(reason: string | null): string {
  if (!reason) return '일부 정보가 정상적으로 반영되지 않았을 수 있습니다.';
  return REASON_GUIDANCE[reason] ?? `일부 정보가 정상적으로 반영되지 않았을 수 있습니다. (사유: ${reason})`;
}

function toDateOnly(date: Date): string {
  return date.toISOString().slice(0, 10);
}

function useLeantimeResource<T>(
  loader: () => Promise<LeantimeReadResponse<T>>,
  deps: React.DependencyList,
): [ResourceState<T>, () => void] {
  const [state, setState] = React.useState<ResourceState<T>>({ status: 'loading' });
  const [nonce, setNonce] = React.useState(0);

  React.useEffect(() => {
    let cancelled = false;
    setState({ status: 'loading' });
    loader()
      .then((data) => {
        if (cancelled) return;
        setState({ status: 'ready', data });
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        if (error instanceof ApiError && error.status === 403) {
          setState({ status: 'forbidden' });
          return;
        }
        if (error instanceof ApiError && error.status === 401) {
          setState({ status: 'unauthorized' });
          return;
        }
        const message = error instanceof Error ? error.message : '알 수 없는 오류가 발생했습니다.';
        setState({ status: 'error', message });
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nonce, ...deps]);

  const refresh = React.useCallback(() => setNonce((n) => n + 1), []);
  return [state, refresh];
}

/**
 * Leantime 프로젝트/담당 작업/기간 일정을 same-origin 읽기 프록시로 받아 네이티브로 그린다.
 *
 * iframe/DOM 스크래핑을 쓰지 않고, 자원별로 독립적으로 로딩·403(권한 없음)·401(세션 만료)·
 * degraded(200, 사유별 안내)를 처리한다. 상단에는 원본 Leantime 을 새 탭으로 여는 LAN-안전
 * 딥링크를 둔다(현재 접속 호스트 기준, iframe 이 아니라 별도 앱을 여는 링크일 뿐).
 */
export function LeantimeDashboard({ port = 8081 }: { port?: number }) {
  const calendarRange = React.useMemo(() => {
    const now = new Date();
    const end = new Date(now.getTime());
    end.setDate(end.getDate() + CALENDAR_WINDOW_DAYS);
    return { start: toDateOnly(now), end: toDateOnly(end) };
  }, []);

  const [projectsState, refreshProjects] = useLeantimeResource<LeantimeProject>(
    () => fetchLeantimeProjects(),
    [],
  );
  const [tasksState, refreshTasks] = useLeantimeResource<LeantimeTask>(() => fetchLeantimeTasks(), []);
  const [calendarState, refreshCalendar] = useLeantimeResource<LeantimeCalendarEntry>(
    () => fetchLeantimeCalendar(calendarRange.start, calendarRange.end),
    [calendarRange.start, calendarRange.end],
  );

  const [deepLinkUrl, setDeepLinkUrl] = React.useState(`http://localhost:${port}`);
  React.useEffect(() => {
    if (typeof window !== 'undefined') {
      setDeepLinkUrl(`${window.location.protocol}//${window.location.hostname}:${port}`);
    }
  }, [port]);

  const refreshAll = React.useCallback(() => {
    refreshProjects();
    refreshTasks();
    refreshCalendar();
  }, [refreshProjects, refreshTasks, refreshCalendar]);

  return (
    <section
      className="flex flex-col gap-4 rounded-xl border border-ink-3/15 bg-surface-raised/40 px-5 py-5"
      data-testid="leantime-dashboard"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h2 className="text-sm font-semibold text-ink-1">Leantime 대시보드</h2>
          <p className="text-xs text-ink-3">프로젝트·담당 작업·기간 일정을 요약해 보여 줍니다(읽기 전용).</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={refreshAll}
            className="rounded-md border border-ink-3/40 px-3 py-1.5 text-xs font-medium text-ink-1 transition hover:bg-ink-3/10"
          >
            새로고침
          </button>
          <a
            href={deepLinkUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-xs font-semibold text-accent-on transition hover:bg-accent-hover"
          >
            원본 Leantime 새 탭으로 열기
          </a>
        </div>
      </div>

      <ResourceSection
        title="프로젝트"
        state={projectsState}
        emptyLabel="표시할 프로젝트가 없습니다."
        renderItem={(project: LeantimeProject) => (
          <li key={project.id} className="flex flex-col gap-0.5 rounded-md border border-ink-3/10 px-3 py-2">
            <span className="text-sm font-medium text-ink-1">{project.name}</span>
            <span className="text-xs text-ink-3">
              {project.state ?? '상태 미상'}
              {project.client_name ? ` · ${project.client_name}` : ''}
            </span>
          </li>
        )}
      />

      <ResourceSection
        title="담당 작업"
        state={tasksState}
        emptyLabel="표시할 담당 작업이 없습니다."
        renderItem={(task: LeantimeTask) => (
          <li key={task.id} className="flex flex-col gap-0.5 rounded-md border border-ink-3/10 px-3 py-2">
            <span className="text-sm font-medium text-ink-1">{task.headline}</span>
            <span className="text-xs text-ink-3">
              {task.status ?? '상태 미상'}
              {task.date_to_finish ? ` · 마감 ${task.date_to_finish}` : ''}
            </span>
          </li>
        )}
      />

      <ResourceSection
        title="기간 일정"
        state={calendarState}
        emptyLabel="표시할 기간 일정이 없습니다."
        renderItem={(entry: LeantimeCalendarEntry) => (
          <li key={entry.id} className="flex flex-col gap-0.5 rounded-md border border-ink-3/10 px-3 py-2">
            <span className="text-sm font-medium text-ink-1">{entry.name}</span>
            <span className="text-xs text-ink-3">
              {entry.date_start ?? '?'} ~ {entry.date_end ?? '?'}
            </span>
          </li>
        )}
      />
    </section>
  );
}

function ResourceSection<T>({
  title,
  state,
  emptyLabel,
  renderItem,
}: {
  title: string;
  state: ResourceState<T>;
  emptyLabel: string;
  renderItem: (item: T) => React.ReactNode;
}) {
  return (
    <section className="flex flex-col gap-2 rounded-lg border border-ink-3/10 bg-surface-sunken/40 px-4 py-4">
      <h3 className="text-sm font-semibold text-ink-1">{title}</h3>

      {state.status === 'loading' && (
        <p role="status" className="text-xs text-ink-3">
          불러오는 중…
        </p>
      )}

      {state.status === 'forbidden' && (
        <p role="alert" className="text-xs leading-relaxed text-rose-600">
          권한 없음 — leantime.read 권한이 없어 {title} 정보를 볼 수 없습니다. 관리자에게 권한을 요청하세요.
        </p>
      )}

      {state.status === 'unauthorized' && (
        <p role="alert" className="text-xs leading-relaxed text-rose-600">
          세션이 만료되었습니다. 다시 로그인한 뒤 새로고침해 주세요.
        </p>
      )}

      {state.status === 'error' && (
        <p role="alert" className="text-xs leading-relaxed text-rose-600">
          {title} 정보를 불러오지 못했습니다. ({state.message})
        </p>
      )}

      {state.status === 'ready' && (
        <>
          {state.data.degraded && (
            <p role="alert" className="text-xs leading-relaxed text-amber-600">
              {reasonGuidance(state.data.reason)}
            </p>
          )}

          {state.data.items.length === 0 ? (
            <p className="text-xs text-ink-3">{emptyLabel}</p>
          ) : (
            <ul role="list" className="flex flex-col gap-2">
              {state.data.items.map((item) => renderItem(item))}
            </ul>
          )}

          <p role="status" className="text-xs text-ink-3">
            갱신: {formatRelativeTime(state.data.fetched_at) || '방금'} ({state.data.fetched_at})
          </p>
        </>
      )}
    </section>
  );
}
