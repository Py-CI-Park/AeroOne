'use client';

import { useMemo, useState } from 'react';

import { Badge, useAdminConsoleData } from '../admin-console-tabs';
import { compareDate, compareNumber, compareText, ListFilter, ListState, matchesListQuery, normalizeListQuery, stableSort } from '../widgets/list-filter';

export function AdminSessionsSection() {
  const { state, purgeSessionMetadata } = useAdminConsoleData();
  const [activeSearch, setActiveSearch] = useState('');
  const [activeSort, setActiveSort] = useState('last-seen-desc');
  const [loginSearch, setLoginSearch] = useState('');
  const [loginSort, setLoginSort] = useState('created-desc');
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

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between gap-3"><div><h2 className="text-lg font-semibold">접속자/세션</h2><p className="text-sm text-slate-500">로그인 세션 활동과 익명 IP 읽음 집계를 함께 확인합니다.</p></div><button type="button" onClick={() => void purgeSessionMetadata()} disabled={state.busy === 'sessions-purge'} className="rounded-md border border-red-200 px-3 py-2 text-sm font-semibold text-red-700 disabled:opacity-50">오래된 세션/로그 정리</button></div>
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="rounded-lg border border-slate-100 p-3">
          <p className="text-xs font-semibold uppercase text-slate-500">Active sessions</p>
          <p className="mt-1 text-2xl font-semibold">{state.connectedUsers?.active_count ?? 0}</p>
          <ListFilter
            id="admin-active-sessions"
            searchLabel="활성 세션 검색"
            searchPlaceholder="username"
            searchValue={activeSearch}
            onSearchChange={setActiveSearch}
            sortLabel="활성 세션 정렬"
            sortValue={activeSort}
            onSortChange={setActiveSort}
            sortOptions={[{ value: 'last-seen-desc', label: 'last seen 최신순' }, { value: 'last-seen-asc', label: 'last seen 오래된순' }, { value: 'username-asc', label: 'username 오름차순' }]}
            totalCount={activeSessions.length}
            filteredCount={visibleActiveSessions.length}
          />
          <div className="mt-3 space-y-2 text-sm">
            <ListState loading={state.busy === 'refresh'} error={state.error} totalCount={activeSessions.length} filteredCount={visibleActiveSessions.length} emptyMessage="활성 로그인 세션 없음" noMatchesMessage="검색 조건에 맞는 활성 세션이 없습니다." />
            {visibleActiveSessions.map((session) => <div key={`${session.user_id}-${session.last_seen_at}`} className="flex items-center justify-between gap-2"><span className="font-medium text-slate-700">{session.username}</span><span className="text-xs text-slate-500">{new Date(session.last_seen_at).toLocaleString('ko-KR')}</span></div>)}
          </div>
        </div>
        <div className="rounded-lg border border-slate-100 p-3">
          <p className="text-xs font-semibold uppercase text-slate-500">Recent login events</p>
          <p className="mt-1 text-sm text-slate-600">실패 {state.connectedUsers?.login_failure_count ?? 0}건</p>
          <ListFilter
            id="admin-login-events"
            searchLabel="로그인 이벤트 검색"
            searchPlaceholder="username / status"
            searchValue={loginSearch}
            onSearchChange={setLoginSearch}
            sortLabel="로그인 이벤트 정렬"
            sortValue={loginSort}
            onSortChange={setLoginSort}
            sortOptions={[{ value: 'created-desc', label: 'created 최신순' }, { value: 'username-asc', label: 'username 오름차순' }, { value: 'status-asc', label: 'status 오름차순' }]}
            totalCount={loginEvents.length}
            filteredCount={visibleLoginEvents.length}
          />
          <div className="mt-3 max-h-40 space-y-2 overflow-auto text-sm">
            <ListState loading={state.busy === 'refresh'} error={state.error} totalCount={loginEvents.length} filteredCount={visibleLoginEvents.length} emptyMessage="로그인 이벤트가 없습니다." noMatchesMessage="검색 조건에 맞는 로그인 이벤트가 없습니다." />
            {visibleLoginEvents.map((event) => <div key={event.id} className="flex items-center justify-between gap-2"><span>{event.username}</span><Badge tone={event.status === 'success' ? 'green' : 'red'}>{event.status}</Badge></div>)}
          </div>
        </div>
        <div className="rounded-lg border border-slate-100 p-3"><p className="text-xs font-semibold uppercase text-slate-500">Anonymous read tracking</p><p className="mt-1 text-2xl font-semibold">{state.connectedUsers?.read_tracking_summary.total_reads ?? 0}</p><p className="text-sm text-slate-500">IP/뉴스레터 집계 행 {state.connectedUsers?.read_tracking_summary.rows ?? 0}개</p></div>
      </div>
    </section>
  );
}
