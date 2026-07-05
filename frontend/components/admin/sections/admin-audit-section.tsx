'use client';

import { useMemo, useState } from 'react';

import type { AuditEvent } from '@/lib/types';
import { Badge, useAdminConsoleData } from '../admin-console-tabs';
import { compareDate, compareText, ListFilter, ListState, matchesListQuery, normalizeListQuery, stableSort } from '../widgets/list-filter';

const CSV_HEADER = 'id,actor_username,actor_role,action,target_type,target_id,status,ip_address,created_at';

function csvField(value: string | number | null | undefined) {
  const text = value == null ? '' : String(value);
  if (/[,"\n\r]/.test(text)) return `"${text.replaceAll('"', '""')}"`;
  return text;
}

export function buildAuditCsv(events: AuditEvent[]): string {
  const rows = events.map((event) => [
    event.id,
    event.actor_username,
    event.actor_role,
    event.action,
    event.target_type,
    event.target_id,
    event.status,
    event.ip_address,
    event.created_at,
  ].map(csvField).join(','));
  return [CSV_HEADER, ...rows].join('\n');
}

function datePrefix(value: string | null | undefined) {
  return String(value ?? '').slice(0, 10);
}

export function AdminAuditSection() {
  const { state } = useAdminConsoleData();
  const [search, setSearch] = useState('');
  const [sort, setSort] = useState('created-desc');
  const [status, setStatus] = useState('');
  const [fromDate, setFromDate] = useState('');
  const [toDate, setToDate] = useState('');

  const statuses = useMemo(() => {
    return stableSort(Array.from(new Set(state.audits.map((event) => event.status).filter(Boolean))), compareText);
  }, [state.audits]);

  const visibleAudits = useMemo(() => {
    const query = normalizeListQuery(search);
    const filtered = state.audits.filter((event) => {
      const eventDate = datePrefix(event.created_at);
      return matchesListQuery(query, [event.actor_username, event.actor_role, event.action, event.target_type, event.target_id, event.status, event.ip_address])
        && (!status || event.status === status)
        && (!fromDate || eventDate >= fromDate)
        && (!toDate || eventDate <= toDate);
    });
    return stableSort(filtered, (a, b) => {
      if (sort === 'created-asc') return compareDate(a.created_at, b.created_at) || a.id - b.id;
      if (sort === 'action-asc') return compareText(a.action, b.action) || a.id - b.id;
      if (sort === 'status-asc') return compareText(a.status, b.status) || a.id - b.id;
      return compareDate(b.created_at, a.created_at) || a.id - b.id;
    });
  }, [fromDate, search, sort, state.audits, status, toDate]);

  function exportCsv() {
    const csv = buildAuditCsv(visibleAudits);
    if (typeof window === 'undefined' || typeof document === 'undefined' || typeof Blob === 'undefined' || !window.URL?.createObjectURL) return;
    const url = window.URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = 'admin-audit-events.csv';
    if (!navigator.userAgent.includes('jsdom')) anchor.click();
    anchor.remove();
    window.URL.revokeObjectURL?.(url);
  }

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">감사 로그</h2>
          <p className="text-sm text-slate-500">운영 이벤트를 검색·필터링하고 CSV로 내보냅니다.</p>
        </div>
        <button type="button" onClick={exportCsv} className="rounded-md border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700">CSV 내보내기</button>
      </div>
      <ListFilter
        id="admin-audits"
        searchLabel="감사 검색"
        searchPlaceholder="actor / role / action / target / status / ip"
        searchValue={search}
        onSearchChange={setSearch}
        sortLabel="감사 정렬"
        sortValue={sort}
        onSortChange={setSort}
        sortOptions={[{ value: 'created-desc', label: 'created 최신순' }, { value: 'created-asc', label: 'created 오래된순' }, { value: 'action-asc', label: 'action 오름차순' }, { value: 'status-asc', label: 'status 오름차순' }]}
        totalCount={state.audits.length}
        filteredCount={visibleAudits.length}
      />
      <div className="mb-3 grid gap-2 rounded-lg border border-slate-100 bg-slate-50 p-3 text-sm md:grid-cols-3">
        <label className="grid gap-1 text-xs font-semibold text-slate-600">
          상태
          <select aria-label="감사 상태 필터" value={status} onChange={(event) => setStatus(event.target.value)} className="rounded-md border border-slate-300 bg-white px-2 py-1 text-sm font-normal text-slate-900">
            <option value="">전체</option>
            {statuses.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </label>
        <label className="grid gap-1 text-xs font-semibold text-slate-600">
          시작
          <input type="date" aria-label="감사 기간 시작" value={fromDate} onChange={(event) => setFromDate(event.target.value)} className="rounded-md border border-slate-300 bg-white px-2 py-1 text-sm font-normal text-slate-900" />
        </label>
        <label className="grid gap-1 text-xs font-semibold text-slate-600">
          끝
          <input type="date" aria-label="감사 기간 끝" value={toDate} onChange={(event) => setToDate(event.target.value)} className="rounded-md border border-slate-300 bg-white px-2 py-1 text-sm font-normal text-slate-900" />
        </label>
      </div>
      <div className="space-y-2">
        <ListState loading={state.busy === 'refresh'} error={state.error} totalCount={state.audits.length} filteredCount={visibleAudits.length} emptyMessage="감사 이벤트가 아직 없습니다." noMatchesMessage="검색 조건에 맞는 감사 이벤트가 없습니다." />
        {visibleAudits.map((event) => <div key={event.id} className="rounded-lg border border-slate-100 px-3 py-2 text-sm"><div className="flex items-center justify-between gap-2"><span className="font-mono text-xs text-slate-500">{event.action}</span><Badge>{event.status}</Badge></div><p className="mt-1 text-slate-600">{event.actor_username ?? 'system'} → {event.target_type} {event.target_id ?? ''}</p><p className="mt-1 text-xs text-slate-400">{event.created_at}</p></div>)}
      </div>
    </section>
  );
}
