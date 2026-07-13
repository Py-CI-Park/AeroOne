'use client';

import { useEffect, useMemo, useState } from 'react';

import type { AdminUser } from '@/lib/types';
import { Badge, userToDraft, useAdminConsoleData } from '../admin-console-tabs';
import { PermissionCheckboxGrid } from '../widgets/permission-checkbox-grid';
import { compareText, ListFilter, ListPagination, ListState, matchesListQuery, normalizeListQuery, paginate, stableSort } from '../widgets/list-filter';

type AdminUserWithActivity = AdminUser & { created_at?: string | null; last_login_at?: string | null };

function formatUserTimestamp(value: string | null | undefined) {
  return value ? new Date(value).toLocaleString('ko-KR') : '기록 없음';
}

export function AdminUsersSection() {
  const { state, userForm, setUserForm, userDrafts, setUserDrafts, createUser, saveUser, resetPassword } = useAdminConsoleData();
  const parsePermissions = (value: string) => value.split(',').map((item) => item.trim()).filter(Boolean);
  const [search, setSearch] = useState('');
  const [sort, setSort] = useState('username-asc');
  const [editingPermissionsUserId, setEditingPermissionsUserId] = useState<number | null>(null);
  const [page, setPage] = useState(0);
  const visibleUsers = useMemo(() => {
    const query = normalizeListQuery(search);
    const filtered = state.users.filter((user) => matchesListQuery(query, [user.username, user.display_name, user.email, user.role]));
    return stableSort(filtered, (a, b) => {
      if (sort === 'username-desc') return compareText(b.username, a.username) || a.id - b.id;
      if (sort === 'name-asc') return compareText(a.display_name, b.display_name) || compareText(a.username, b.username) || a.id - b.id;
      if (sort === 'email-asc') return compareText(a.email, b.email) || compareText(a.username, b.username) || a.id - b.id;
      if (sort === 'role-asc') return compareText(a.role, b.role) || compareText(a.username, b.username) || a.id - b.id;
      return compareText(a.username, b.username) || a.id - b.id;
    });
  }, [search, sort, state.users]);
  const pageSize = 10;
  const pagedUsers = paginate(visibleUsers, page, pageSize);

  useEffect(() => {
    setPage(0);
  }, [search, sort]);

  useEffect(() => {
    if (pagedUsers.page !== page) setPage(pagedUsers.page);
  }, [page, pagedUsers.page]);

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="mb-4">
        <h2 className="text-lg font-semibold">사용자/RBAC</h2>
        <p className="text-sm text-slate-500">접속 아이디와 비밀번호만 있으면 계정을 만들 수 있고, 이름과 이메일은 선택 입력입니다.</p>
      </div>

      <div className="mb-5 rounded-lg border border-slate-100 bg-slate-50 p-3 text-sm">
        <div className="mb-3 flex items-center justify-between gap-2">
          <div>
            <h3 className="text-sm font-semibold text-slate-900">계정 등록</h3>
            <p className="text-xs text-slate-500">필수: 접속 아이디, 임시 비밀번호 · 선택: 이름, 사용자 이메일</p>
          </div>
          <Badge tone="blue">ID/PW 필수</Badge>
        </div>
        <div className="grid gap-3 md:grid-cols-2">
          <label className="grid gap-1 text-xs font-semibold text-slate-600">
            접속 아이디 *
            <input placeholder="예: analyst01" value={userForm.username} onChange={(event) => setUserForm((current) => ({ ...current, username: event.target.value }))} className="rounded-md border border-slate-300 bg-white px-2 py-1 text-sm font-normal text-slate-900" aria-label="new user login id" />
          </label>
          <label className="grid gap-1 text-xs font-semibold text-slate-600">
            임시 비밀번호 *
            <input placeholder="초기 접속 비밀번호" type="password" value={userForm.password} onChange={(event) => setUserForm((current) => ({ ...current, password: event.target.value }))} className="rounded-md border border-slate-300 bg-white px-2 py-1 text-sm font-normal text-slate-900" aria-label="new user login password" />
          </label>
          <label className="grid gap-1 text-xs font-semibold text-slate-600">
            이름 <span className="font-normal text-slate-400">(선택)</span>
            <input placeholder="예: 홍길동" value={userForm.display_name} onChange={(event) => setUserForm((current) => ({ ...current, display_name: event.target.value }))} className="rounded-md border border-slate-300 bg-white px-2 py-1 text-sm font-normal text-slate-900" aria-label="new user display name" />
          </label>
          <label className="grid gap-1 text-xs font-semibold text-slate-600">
            사용자 이메일 <span className="font-normal text-slate-400">(선택)</span>
            <input placeholder="user@example.local" value={userForm.email} onChange={(event) => setUserForm((current) => ({ ...current, email: event.target.value }))} className="rounded-md border border-slate-300 bg-white px-2 py-1 text-sm font-normal text-slate-900" aria-label="new user email" />
          </label>
          <label className="grid gap-1 text-xs font-semibold text-slate-600">
            역할
            <select value={userForm.role} onChange={(event) => setUserForm((current) => ({ ...current, role: event.target.value }))} className="rounded-md border border-slate-300 bg-white px-2 py-1 text-sm font-normal text-slate-900" aria-label="new user role"><option value="admin">admin</option><option value="user">user</option><option value="pending">pending</option></select>
          </label>
          <div className="flex items-end justify-between gap-3">
            <label className="inline-flex items-center gap-2 text-xs font-semibold text-slate-600"><input type="checkbox" checked={userForm.is_active} onChange={(event) => setUserForm((current) => ({ ...current, is_active: event.target.checked }))} /> active</label>
            <button type="button" disabled={state.busy === 'user-create'} onClick={() => void createUser()} className="rounded-md bg-slate-900 px-3 py-2 text-xs font-semibold text-white disabled:opacity-40">사용자 생성</button>
          </div>
        </div>
      </div>

      <ListFilter
        id="admin-users"
        searchLabel="사용자 검색"
        searchPlaceholder="아이디 / 이름 / 이메일 / 역할"
        searchValue={search}
        onSearchChange={setSearch}
        sortLabel="사용자 정렬"
        sortValue={sort}
        onSortChange={setSort}
        sortOptions={[
          { value: 'username-asc', label: '아이디 오름차순' },
          { value: 'username-desc', label: '아이디 내림차순' },
          { value: 'name-asc', label: '이름 오름차순' },
          { value: 'email-asc', label: '이메일 오름차순' },
          { value: 'role-asc', label: '역할 오름차순' },
        ]}
        totalCount={state.users.length}
        filteredCount={visibleUsers.length}
      />

      <div className="space-y-2">
        <ListState loading={state.busy === 'refresh'} error={state.error} totalCount={state.users.length} filteredCount={visibleUsers.length} emptyMessage="등록된 사용자가 없습니다." noMatchesMessage="검색 조건에 맞는 사용자가 없습니다." />
        {pagedUsers.pageItems.map((rawUser) => {
          const user = rawUser as AdminUserWithActivity;
          const draft = userDrafts[user.id] ?? userToDraft(user);
          const editingPermissions = editingPermissionsUserId === user.id;
          return (
            <div key={user.id} className="rounded-lg border border-slate-100 px-3 py-3 text-sm">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-semibold text-slate-900">{user.username}</span>
                    {user.display_name ? <span className="text-slate-500">({user.display_name})</span> : null}
                    <Badge tone={draft.role === 'admin' ? 'green' : draft.role === 'pending' ? 'amber' : 'slate'}>{draft.role}</Badge>
                    <Badge tone={draft.is_active ? 'green' : 'red'}>{draft.is_active ? 'active' : 'inactive'}</Badge>
                  </div>
                  <p className="mt-1 text-xs text-slate-500">{draft.email || '이메일 없음'} · 직접 권한 {parsePermissions(draft.permissions_csv).length}개</p>
                  <p className="mt-1 text-xs text-slate-400">가입일 {formatUserTimestamp(user.created_at)} · 마지막 로그인 {formatUserTimestamp(user.last_login_at)}</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button type="button" onClick={() => setEditingPermissionsUserId(editingPermissions ? null : user.id)} className="rounded-md border border-blue-200 px-3 py-1.5 text-xs font-semibold text-blue-700">
                    {editingPermissions ? '권한 닫기' : '권한 수정'}
                  </button>
                  <button type="button" onClick={() => void resetPassword(user)} className="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-700">비밀번호 재설정</button>
                  <button type="button" onClick={() => void saveUser(user)} className="rounded-md bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white">저장</button>
                </div>
              </div>

              <div className="mt-3 grid gap-2 md:grid-cols-3">
                <label className="grid gap-1 text-xs font-semibold text-slate-600">
                  이름
                  <input value={draft.display_name ?? ''} onChange={(event) => setUserDrafts((current) => ({ ...current, [user.id]: { ...draft, display_name: event.target.value } }))} className="rounded-md border border-slate-300 px-2 py-1 text-sm font-normal text-slate-900" aria-label={`${user.username} display name`} />
                </label>
                <label className="grid gap-1 text-xs font-semibold text-slate-600">
                  사용자 이메일
                  <input value={draft.email ?? ''} onChange={(event) => setUserDrafts((current) => ({ ...current, [user.id]: { ...draft, email: event.target.value } }))} className="rounded-md border border-slate-300 px-2 py-1 text-sm font-normal text-slate-900" aria-label={`${user.username} email`} />
                </label>
                <label className="grid gap-1 text-xs font-semibold text-slate-600">
                  역할
                  <select value={draft.role} onChange={(event) => setUserDrafts((current) => ({ ...current, [user.id]: { ...draft, role: event.target.value } }))} className="rounded-md border border-slate-300 px-2 py-1 text-sm font-normal text-slate-900" aria-label={`${user.username} role`}><option value="admin">admin</option><option value="user">user</option><option value="pending">pending</option></select>
                </label>
              </div>
              <label className="mt-2 inline-flex items-center gap-2 text-xs font-semibold text-slate-600"><input type="checkbox" checked={draft.is_active} onChange={(event) => setUserDrafts((current) => ({ ...current, [user.id]: { ...draft, is_active: event.target.checked } }))} /> active</label>

              {editingPermissions ? (
                <div className="mt-3 rounded-lg border border-blue-100 bg-blue-50 p-3">
                  <div className="mb-2 flex items-center justify-between gap-2">
                    <div>
                      <p className="text-sm font-semibold text-blue-950">{user.username} 권한 수정</p>
                      <p className="text-xs text-blue-700">체크 후 저장을 누르면 해당 사용자 세션 권한이 즉시 갱신됩니다.</p>
                    </div>
                    <Badge tone="blue">{parsePermissions(draft.permissions_csv).length}개 선택</Badge>
                  </div>
                  <PermissionCheckboxGrid
                    permissions={state.permissions}
                    value={parsePermissions(draft.permissions_csv)}
                    onChange={(permissions) => setUserDrafts((current) => ({ ...current, [user.id]: { ...draft, permissions_csv: permissions.join(', ') } }))}
                    label={`${user.username} permissions`}
                  />
                </div>
              ) : null}
            </div>
          );
        })}
        {visibleUsers.length > 0 ? <ListPagination id="admin-users" page={pagedUsers.page} totalPages={pagedUsers.totalPages} onPageChange={setPage} /> : null}
      </div>
    </section>
  );
}
