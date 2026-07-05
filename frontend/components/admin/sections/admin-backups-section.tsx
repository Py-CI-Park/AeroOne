'use client';

import { useMemo, useState } from 'react';

import { Badge, useAdminConsoleData } from '../admin-console-tabs';
import { compareDate, compareNumber, compareText, ListFilter, ListState, matchesListQuery, normalizeListQuery, stableSort } from '../widgets/list-filter';

export function AdminBackupsSection() {
  const { state, runBackup, runValidate, runRestoreDryRun } = useAdminConsoleData();
  const [search, setSearch] = useState('');
  const [sort, setSort] = useState('created-desc');

  const visibleBackups = useMemo(() => {
    const query = normalizeListQuery(search);
    const filtered = state.backups.filter((backup) => matchesListQuery(query, [backup.filename, backup.created_at, backup.status, backup.sha256]));
    return stableSort(filtered, (a, b) => {
      if (sort === 'created-asc') return compareDate(a.created_at, b.created_at) || a.id - b.id;
      if (sort === 'filename-asc') return compareText(a.filename, b.filename) || a.id - b.id;
      if (sort === 'size-desc') return compareNumber(b.file_size, a.file_size) || compareText(a.filename, b.filename) || a.id - b.id;
      return compareDate(b.created_at, a.created_at) || a.id - b.id;
    });
  }, [search, sort, state.backups]);

  return (
    <section className="grid gap-6 xl:grid-cols-2">
      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="mb-3 flex items-center justify-between"><h2 className="text-lg font-semibold">백업</h2><button type="button" disabled={state.busy === 'backup'} onClick={() => void runBackup()} className="rounded-md bg-blue-600 px-3 py-2 text-sm font-semibold text-white disabled:opacity-40">백업 생성</button></div>
        <ListFilter
          id="admin-backups"
          searchLabel="백업 검색"
          searchPlaceholder="filename / date / status"
          searchValue={search}
          onSearchChange={setSearch}
          sortLabel="백업 정렬"
          sortValue={sort}
          onSortChange={setSort}
          sortOptions={[{ value: 'created-desc', label: 'created 최신순' }, { value: 'created-asc', label: 'created 오래된순' }, { value: 'filename-asc', label: 'filename 오름차순' }, { value: 'size-desc', label: 'size 내림차순' }]}
          totalCount={state.backups.length}
          filteredCount={visibleBackups.length}
        />
        <div className="space-y-2">
          <ListState loading={state.busy === 'refresh'} error={state.error} totalCount={state.backups.length} filteredCount={visibleBackups.length} emptyMessage="아직 생성된 백업이 없습니다." noMatchesMessage="검색 조건에 맞는 백업이 없습니다." />
          {visibleBackups.map((backup) => <div key={backup.id} className="flex items-center justify-between gap-3 rounded-lg border border-slate-100 px-3 py-2 text-sm"><div><p className="font-medium">{backup.filename}</p><p className="font-mono text-xs text-slate-500">{backup.sha256.slice(0, 16)} · {backup.file_size} bytes · {backup.status}</p></div><div className="flex gap-2"><button type="button" onClick={() => void runValidate(backup.id)} className="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-700">검증</button><button type="button" onClick={() => void runRestoreDryRun(backup.id)} className="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-700">복원 점검</button><a href={`/api/frontend/admin/backups/${backup.id}/download`} className="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-700">다운로드</a></div></div>)}
        </div>
      </div>
      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <h2 className="mb-3 text-lg font-semibold">최근 감사 로그</h2>
        <div className="space-y-2">{state.audits.map((event) => <div key={event.id} className="rounded-lg border border-slate-100 px-3 py-2 text-sm"><div className="flex items-center justify-between gap-2"><span className="font-mono text-xs text-slate-500">{event.action}</span><Badge>{event.status}</Badge></div><p className="mt-1 text-slate-600">{event.actor_username ?? 'system'} → {event.target_type} {event.target_id ?? ''}</p><p className="mt-1 text-xs text-slate-400">{event.created_at}</p></div>)}{state.audits.length === 0 ? <p className="text-sm text-slate-500">감사 이벤트가 아직 없습니다.</p> : null}</div>
      </div>
    </section>
  );
}
