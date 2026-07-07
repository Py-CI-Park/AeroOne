'use client';

import { useEffect, useMemo, useState } from 'react';

import { Badge, useAdminConsoleData } from '../admin-console-tabs';
import { compareDate, compareNumber, compareText, ListFilter, ListPagination, ListState, matchesListQuery, normalizeListQuery, paginate, stableSort } from '../widgets/list-filter';
import { formatRelativeTime } from '@/lib/relative-time';

function loginEventTone(status: string): 'green' | 'red' | 'blue' | 'slate' {
  if (status === 'success') return 'green';
  if (status === 'failure') return 'red';
  if (status === 'logout') return 'blue';
  return 'slate';
}

export function AdminSessionsSection() {
  const { state, refresh, purgeSessionMetadata } = useAdminConsoleData();
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [activeSearch, setActiveSearch] = useState('');
  const [activeSort, setActiveSort] = useState('last-seen-desc');
  const [loginSearch, setLoginSearch] = useState('');
  const [loginSort, setLoginSort] = useState('created-desc');
  const [loginPage, setLoginPage] = useState(0);
  const [lastRefreshedAt, setLastRefreshedAt] = useState('');
  const activeSessions = state.connectedUsers?.active_sessions ?? [];
  const loginEvents = state.connectedUsers?.recent_login_events ?? [];

  const visibleActiveSessions = useMemo(() => {
    const query = normalizeListQuery(activeSearch);
    const filtered = activeSessions.filter((session) => matchesListQuery(query, [session.username, session.user_id, session.last_seen_at]));
    return stableSort(filtered, (a, b) => {
      if (activeSort === 'username-asc') return compareText(a.username, b.username) || compareNumber(a.user_id, b.user_id) || compareDate(b.last_seen_at, a.last_seen_at);
      if (activeSort === 'last-seen-asc') return compareDate(a.last_seen_at, b.last_seen_at) || compareText(a.username, b.username) || compareNumber(a.user_id, b.user_id);
      return compareDate(b.last_seen_at, a.last_seen_at) || compareText(a.username, b.username) || compareNumber(a.user_id, b.user_id);
    });
  }, [activeSearch, activeSort, activeSessions]);

  const visibleLoginEvents = useMemo(() => {
    const query = normalizeListQuery(loginSearch);
    const filtered = loginEvents.filter((event) => matchesListQuery(query, [event.username, event.status, event.ip_address, event.created_at]));
    return stableSort(filtered, (a, b) => {
      if (loginSort === 'username-asc') return compareText(a.username, b.username) || compareDate(b.created_at, a.created_at) || compareNumber(a.id, b.id);
      if (loginSort === 'status-asc') return compareText(a.status, b.status) || compareText(a.username, b.username) || compareNumber(a.id, b.id);
      return compareDate(b.created_at, a.created_at) || compareNumber(a.id, b.id);
    });
  }, [loginSearch, loginSort, loginEvents]);
  const loginPageSize = 10;
  const pagedLoginEvents = paginate(visibleLoginEvents, loginPage, loginPageSize);

  useEffect(() => {
    if (!autoRefresh) return undefined;
    const intervalId = window.setInterval(() => {
      void refresh(['connectedUsers']);
    }, 15000);
    return () => window.clearInterval(intervalId);
  }, [autoRefresh, refresh]);

  useEffect(() => {
    if (state.connectedUsers) setLastRefreshedAt(new Date().toLocaleTimeString('ko-KR'));
  }, [state.connectedUsers]);

  useEffect(() => {
    setLoginPage(0);
  }, [loginSearch]);

  useEffect(() => {
    if (pagedLoginEvents.page !== loginPage) setLoginPage(pagedLoginEvents.page);
  }, [loginPage, pagedLoginEvents.page]);


  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h2 className="text-lg font-semibold">접속자/세션</h2>
          <p className="text-sm text-slate-500">로그인·로그아웃 이벤트, 세션 활동, 익명 IP 읽음 집계를 함께 확인합니다.</p>
          {lastRefreshedAt ? <p className="text-xs text-slate-400">마지막 갱신 {lastRefreshedAt}</p> : null}
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 text-sm font-semibold text-slate-600">
            <input type="checkbox" checked={autoRefresh} onChange={(event) => setAutoRefresh(event.target.checked)} aria-label="세션 자동 새로고침" className="h-4 w-4 rounded border-slate-300" />
            자동 새로고침(15초)
          </label>
          <button type="button" onClick={() => void purgeSessionMetadata()} disabled={state.busy === 'sessions-purge'} className="rounded-md border border-red-200 px-3 py-2 text-sm font-semibold text-red-700 disabled:opacity-50">오래된 세션/로그 정리</button>
        </div>
      </div>
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.35fr)_minmax(260px,0.8fr)]">
        <div className="min-h-[24rem] rounded-lg border border-slate-100 p-3">
          <p className="text-xs font-semibold uppercase text-slate-500">활성 세션</p>
          <p className="mt-1 text-2xl font-semibold">{state.connectedUsers?.active_count ?? 0}</p>
          <ListFilter
            id="admin-active-sessions"
            searchLabel="활성 세션 검색"
            searchPlaceholder="사용자명"
            searchValue={activeSearch}
            onSearchChange={setActiveSearch}
            sortLabel="활성 세션 정렬"
            sortValue={activeSort}
            onSortChange={setActiveSort}
            sortOptions={[{ value: 'last-seen-desc', label: '최근 활동 최신순' }, { value: 'last-seen-asc', label: '최근 활동 오래된순' }, { value: 'username-asc', label: '사용자명 오름차순' }]}
            totalCount={activeSessions.length}
            filteredCount={visibleActiveSessions.length}
          />
          <div className="mt-3 max-h-72 space-y-2 overflow-auto text-sm">
            <ListState loading={state.busy === 'refresh'} error={state.error} totalCount={activeSessions.length} filteredCount={visibleActiveSessions.length} emptyMessage="활성 로그인 세션 없음" noMatchesMessage="검색 조건에 맞는 활성 세션이 없습니다." />
            {visibleActiveSessions.map((session) => {
              const absoluteLastSeen = new Date(session.last_seen_at).toLocaleString('ko-KR');
              const relativeLastSeen = formatRelativeTime(session.last_seen_at);
              return <div key={`${session.user_id}-${session.last_seen_at}`} className="flex items-center justify-between gap-2 rounded-md bg-slate-50 px-2 py-1.5"><span className="font-medium text-slate-700">{session.username}</span><span className="text-xs text-slate-500">{relativeLastSeen ? `${relativeLastSeen} · ${absoluteLastSeen}` : absoluteLastSeen}</span></div>;
            })}
          </div>
        </div>
        <div className="min-h-[24rem] rounded-lg border border-slate-100 p-3">
          <p className="text-xs font-semibold uppercase text-slate-500">최근 로그인/로그아웃 이벤트</p>
          <p className="mt-1 text-sm text-slate-600">실패 {state.connectedUsers?.login_failure_count ?? 0}건</p>
          <ListFilter
            id="admin-login-events"
            searchLabel="로그인 이벤트 검색"
            searchPlaceholder="사용자명 / 상태 / IP / 날짜"
            searchValue={loginSearch}
            onSearchChange={setLoginSearch}
            sortLabel="로그인 이벤트 정렬"
            sortValue={loginSort}
            onSortChange={setLoginSort}
            sortOptions={[{ value: 'created-desc', label: '생성일 최신순' }, { value: 'username-asc', label: '사용자명 오름차순' }, { value: 'status-asc', label: '상태 오름차순' }]}
            totalCount={loginEvents.length}
            filteredCount={visibleLoginEvents.length}
          />
          <div className="mt-3 max-h-96 space-y-2 overflow-auto text-sm">
            <ListState loading={state.busy === 'refresh'} error={state.error} totalCount={loginEvents.length} filteredCount={visibleLoginEvents.length} emptyMessage="로그인 이벤트가 없습니다." noMatchesMessage="검색 조건에 맞는 로그인 이벤트가 없습니다." />
            {pagedLoginEvents.pageItems.map((event) => {
              const absoluteCreated = new Date(event.created_at).toLocaleString('ko-KR');
              const relativeCreated = formatRelativeTime(event.created_at);
              return <div key={event.id} className="grid grid-cols-[minmax(0,1fr)_auto_auto] items-center gap-2 rounded-md bg-slate-50 px-2 py-1.5"><span>{event.username}</span><span className="text-xs text-slate-500">{relativeCreated ? `${relativeCreated} · ${absoluteCreated}` : absoluteCreated}</span><Badge tone={loginEventTone(event.status)}>{event.status}</Badge></div>;
            })}
          </div>
          {visibleLoginEvents.length > 0 ? <ListPagination id="admin-login-events" page={pagedLoginEvents.page} totalPages={pagedLoginEvents.totalPages} onPageChange={setLoginPage} /> : null}
        </div>
        <div className="min-h-[24rem] rounded-lg border border-slate-100 p-3"><p className="text-xs font-semibold uppercase text-slate-500">익명 읽음 추적</p><p className="mt-1 text-2xl font-semibold">{state.connectedUsers?.read_tracking_summary.total_reads ?? 0}</p><p className="text-sm text-slate-500">IP/뉴스레터 집계 행 {state.connectedUsers?.read_tracking_summary.rows ?? 0}개</p></div>
      </div>
    </section>
  );
}
