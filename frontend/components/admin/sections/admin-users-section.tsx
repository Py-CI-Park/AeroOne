'use client';

import { useMemo, useState } from 'react';

import { Badge, userToDraft, useAdminConsoleData } from '../admin-console-tabs';
import { PermissionCheckboxGrid } from '../widgets/permission-checkbox-grid';
import { compareText, ListFilter, ListState, matchesListQuery, normalizeListQuery, stableSort } from '../widgets/list-filter';

export function AdminUsersSection() {
  const { state, userForm, setUserForm, userDrafts, setUserDrafts, createUser, saveUser, resetPassword } = useAdminConsoleData();
  const parsePermissions = (value: string) => value.split(',').map((item) => item.trim()).filter(Boolean);
  const [search, setSearch] = useState('');
  const [sort, setSort] = useState('username-asc');
  const visibleUsers = useMemo(() => {
    const query = normalizeListQuery(search);
    const filtered = state.users.filter((user) => matchesListQuery(query, [user.username, user.email, user.role]));
    return stableSort(filtered, (a, b) => {
      if (sort === 'username-desc') return compareText(b.username, a.username) || a.id - b.id;
      if (sort === 'email-asc') return compareText(a.email, b.email) || compareText(a.username, b.username) || a.id - b.id;
      if (sort === 'role-asc') return compareText(a.role, b.role) || compareText(a.username, b.username) || a.id - b.id;
      return compareText(a.username, b.username) || a.id - b.id;
    });
  }, [search, sort, state.users]);
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <h2 className="mb-3 text-lg font-semibold">사용자/RBAC</h2>
      <div className="mb-4 grid gap-2 rounded-lg border border-slate-100 p-3 text-sm md:grid-cols-2">
        <input placeholder="username" value={userForm.username} onChange={(event) => setUserForm((current) => ({ ...current, username: event.target.value }))} className="rounded-md border border-slate-300 px-2 py-1" aria-label="new user username" />
        <input placeholder="temporary password" type="password" value={userForm.password} onChange={(event) => setUserForm((current) => ({ ...current, password: event.target.value }))} className="rounded-md border border-slate-300 px-2 py-1" aria-label="new user temporary password" />
        <input placeholder="email" value={userForm.email} onChange={(event) => setUserForm((current) => ({ ...current, email: event.target.value }))} className="rounded-md border border-slate-300 px-2 py-1" aria-label="new user email" />
        <select value={userForm.role} onChange={(event) => setUserForm((current) => ({ ...current, role: event.target.value }))} className="rounded-md border border-slate-300 px-2 py-1" aria-label="new user role"><option value="admin">admin</option><option value="user">user</option><option value="pending">pending</option></select>
        <label className="inline-flex items-center gap-2 text-xs text-slate-600"><input type="checkbox" checked={userForm.is_active} onChange={(event) => setUserForm((current) => ({ ...current, is_active: event.target.checked }))} /> active</label>
        <button type="button" disabled={state.busy === 'user-create'} onClick={() => void createUser()} className="rounded-md bg-slate-900 px-3 py-2 text-xs font-semibold text-white disabled:opacity-40">사용자 생성</button>
      </div>
      <ListFilter
        id="admin-users"
        searchLabel="사용자 검색"
        searchPlaceholder="username / email / role"
        searchValue={search}
        onSearchChange={setSearch}
        sortLabel="사용자 정렬"
        sortValue={sort}
        onSortChange={setSort}
        sortOptions={[
          { value: 'username-asc', label: 'username 오름차순' },
          { value: 'username-desc', label: 'username 내림차순' },
          { value: 'email-asc', label: 'email 오름차순' },
          { value: 'role-asc', label: 'role 오름차순' },
        ]}
        totalCount={state.users.length}
        filteredCount={visibleUsers.length}
      />
      <div className="space-y-2">
        <ListState loading={state.busy === 'refresh'} error={state.error} totalCount={state.users.length} filteredCount={visibleUsers.length} emptyMessage="등록된 사용자가 없습니다." noMatchesMessage="검색 조건에 맞는 사용자가 없습니다." />
        {visibleUsers.map((user) => {
          const draft = userDrafts[user.id] ?? userToDraft(user);
          return (
            <div key={user.id} className="rounded-lg border border-slate-100 px-3 py-2 text-sm">
              <div className="flex items-center justify-between gap-2"><span className="font-medium">{user.username}</span><Badge tone={draft.role === 'admin' ? 'green' : draft.role === 'pending' ? 'amber' : 'slate'}>{draft.role}</Badge></div>
              <div className="mt-2 grid gap-2 md:grid-cols-2">
                <input value={draft.email ?? ''} onChange={(event) => setUserDrafts((current) => ({ ...current, [user.id]: { ...draft, email: event.target.value } }))} className="rounded-md border border-slate-300 px-2 py-1" aria-label={`${user.username} email`} />
                <select value={draft.role} onChange={(event) => setUserDrafts((current) => ({ ...current, [user.id]: { ...draft, role: event.target.value } }))} className="rounded-md border border-slate-300 px-2 py-1" aria-label={`${user.username} role`}><option value="admin">admin</option><option value="user">user</option><option value="pending">pending</option></select>
              </div>
              <PermissionCheckboxGrid
                permissions={state.permissions}
                value={parsePermissions(draft.permissions_csv)}
                onChange={(permissions) => setUserDrafts((current) => ({ ...current, [user.id]: { ...draft, permissions_csv: permissions.join(', ') } }))}
                label={`${user.username} permissions`}
              />
              <label className="mt-2 inline-flex items-center gap-2 text-xs text-slate-600"><input type="checkbox" checked={draft.is_active} onChange={(event) => setUserDrafts((current) => ({ ...current, [user.id]: { ...draft, is_active: event.target.checked } }))} /> active</label>
              <div className="mt-2 flex gap-2"><button type="button" onClick={() => void saveUser(user)} className="rounded-md bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white">저장</button><button type="button" onClick={() => void resetPassword(user)} className="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-700">비밀번호 재설정</button></div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
