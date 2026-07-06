'use client';
import type { ReactNode } from 'react';
import { useMemo, useState } from 'react';


import { describePermission } from '@/lib/permission-catalog';
import { Badge, useAdminConsoleData } from '../admin-console-tabs';
import { PermissionCheckboxGrid } from '../widgets/permission-checkbox-grid';
import { ResourceGrantForm } from '../widgets/resource-grant-form';
import { compareNumber, compareText, ListFilter, ListState, matchesListQuery, normalizeListQuery, stableSort } from '../widgets/list-filter';
import { UserGroupPicker } from '../widgets/user-group-picker';

function PermissionPill({ permissionKey, prefix, suffix }: { permissionKey: string; prefix?: string; suffix?: string }) {
  const permission = describePermission(permissionKey);
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-50 px-2 py-1 text-[11px] text-slate-700" title={permissionKey}>
      {prefix ? <span className="font-semibold text-slate-500">{prefix}</span> : null}
      <span className="font-semibold">{permission.label}</span>
      <span className="font-mono text-slate-400">{permissionKey}</span>
      {suffix ? <span className="text-slate-500">{suffix}</span> : null}
    </span>
  );
}

function PermissionGroup({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div>
      <p className="mb-1 text-[11px] font-semibold text-slate-500">{title}</p>
      <div className="flex flex-wrap gap-1">{children}</div>
    </div>
  );
}

function EmptyPermissionGroup({ title }: { title: string }) {
  return (
    <PermissionGroup title={title}>
      <span className="text-[11px] text-slate-400">없음</span>
    </PermissionGroup>
  );
}

export function AdminRbacSection() {
  const { state, groupForm, setGroupForm, saveGroup, removeResourceGrant } = useAdminConsoleData();
  const parsePermissions = (value: string) => value.split(',').map((item) => item.trim()).filter(Boolean);
  const [groupSearch, setGroupSearch] = useState('');
  const [groupSort, setGroupSort] = useState('name-asc');
  const [grantSearch, setGrantSearch] = useState('');
  const [grantSort, setGrantSort] = useState('subject-asc');
  const visibleGroups = useMemo(() => {
    const query = normalizeListQuery(groupSearch);
    const filtered = state.groups.filter((group) => matchesListQuery(query, [group.key, group.name, group.description, group.permissions.join(' ')]));
    return stableSort(filtered, (a, b) => {
      if (groupSort === 'key-asc') return compareText(a.key, b.key) || a.id - b.id;
      if (groupSort === 'name-desc') return compareText(b.name, a.name) || a.id - b.id;
      return compareText(a.name, b.name) || compareText(a.key, b.key) || a.id - b.id;
    });
  }, [groupSearch, groupSort, state.groups]);
  const visibleGrants = useMemo(() => {
    const query = normalizeListQuery(grantSearch);
    const filtered = state.resourceGrants.filter((grant) => matchesListQuery(query, [grant.subject_type, grant.subject_id, grant.resource_type, grant.resource_id, grant.permission_key]));
    return stableSort(filtered, (a, b) => {
      if (grantSort === 'resource-asc') return compareText(a.resource_type, b.resource_type) || compareText(a.resource_id, b.resource_id) || compareText(a.permission_key, b.permission_key) || compareNumber(a.id, b.id);
      if (grantSort === 'permission-asc') return compareText(a.permission_key, b.permission_key) || compareText(a.resource_type, b.resource_type) || compareNumber(a.id, b.id);
      return compareText(a.subject_type, b.subject_type) || compareNumber(a.subject_id, b.subject_id) || compareNumber(a.id, b.id);
    });
  }, [grantSearch, grantSort, state.resourceGrants]);
  return (
    <section className="space-y-6">
      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <h2 className="mb-3 text-lg font-semibold">그룹/RBAC 권한</h2>
        <p className="mb-3 text-xs text-slate-500">사용 가능 권한 {state.permissions.length}개: {state.permissions.slice(0, 5).map((permission) => permission.key).join(', ')}{state.permissions.length > 5 ? ' ...' : ''}</p>
        <div className="grid gap-2 rounded-lg border border-slate-100 p-3 text-sm md:grid-cols-2">
          <input placeholder="group key" value={groupForm.key} onChange={(event) => setGroupForm((current) => ({ ...current, key: event.target.value }))} className="rounded-md border border-slate-300 px-2 py-1" aria-label="group key" />
          <input placeholder="group name" value={groupForm.name} onChange={(event) => setGroupForm((current) => ({ ...current, name: event.target.value }))} className="rounded-md border border-slate-300 px-2 py-1" aria-label="group name" />
          <input placeholder="description" value={groupForm.description} onChange={(event) => setGroupForm((current) => ({ ...current, description: event.target.value }))} className="rounded-md border border-slate-300 px-2 py-1 md:col-span-2" aria-label="group description" />
          <PermissionCheckboxGrid
            permissions={state.permissions}
            value={parsePermissions(groupForm.permissions_csv)}
            onChange={(permissions) => setGroupForm((current) => ({ ...current, permissions_csv: permissions.join(', ') }))}
            label="group permissions"
          />
          <label className="inline-flex items-center gap-2 text-xs text-slate-600"><input type="checkbox" checked={groupForm.is_active} onChange={(event) => setGroupForm((current) => ({ ...current, is_active: event.target.checked }))} /> active</label>
          <button type="button" disabled={state.busy === 'group-save'} onClick={() => void saveGroup()} className="rounded-md bg-slate-900 px-3 py-2 text-xs font-semibold text-white disabled:opacity-40">그룹 저장</button>
        </div>
        <ListFilter
          id="admin-groups"
          searchLabel="그룹 검색"
          searchPlaceholder="group key / name / permission"
          searchValue={groupSearch}
          onSearchChange={setGroupSearch}
          sortLabel="그룹 정렬"
          sortValue={groupSort}
          onSortChange={setGroupSort}
          sortOptions={[
            { value: 'name-asc', label: 'name 오름차순' },
            { value: 'name-desc', label: 'name 내림차순' },
            { value: 'key-asc', label: 'key 오름차순' },
          ]}
          totalCount={state.groups.length}
          filteredCount={visibleGroups.length}
        />
        <div className="mt-3 space-y-2">
          <ListState loading={state.busy === 'refresh'} error={state.error} totalCount={state.groups.length} filteredCount={visibleGroups.length} emptyMessage="등록된 그룹이 없습니다." noMatchesMessage="검색 조건에 맞는 그룹이 없습니다." />
          {visibleGroups.map((group) => <div key={group.id} className="rounded-lg border border-slate-100 px-3 py-2 text-sm"><div className="flex justify-between"><strong>{group.name}</strong><Badge tone={group.is_active ? 'green' : 'amber'}>{group.key}</Badge></div><p className="mt-1 font-mono text-xs text-slate-500">{group.permissions.join(', ') || '권한 없음'}</p></div>)}
        </div>
      </div>
      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <h2 className="mb-3 text-lg font-semibold">RBAC 매트릭스 / 리소스 권한</h2>
        <ResourceGrantForm />
        <UserGroupPicker />
        <ListFilter
          id="admin-resource-grants"
          searchLabel="리소스 권한 검색"
          searchPlaceholder="subject / resource / permission"
          searchValue={grantSearch}
          onSearchChange={setGrantSearch}
          sortLabel="리소스 권한 정렬"
          sortValue={grantSort}
          onSortChange={setGrantSort}
          sortOptions={[
            { value: 'subject-asc', label: 'subject 오름차순' },
            { value: 'resource-asc', label: 'resource 오름차순' },
            { value: 'permission-asc', label: 'permission 오름차순' },
          ]}
          totalCount={state.resourceGrants.length}
          filteredCount={visibleGrants.length}
        />
        <div className="mb-4 space-y-2"><ListState loading={state.busy === 'refresh'} error={state.error} totalCount={state.resourceGrants.length} filteredCount={visibleGrants.length} emptyMessage="등록된 리소스 권한이 없습니다." noMatchesMessage="검색 조건에 맞는 리소스 권한이 없습니다." />{visibleGrants.map((grant) => <div key={grant.id} className="flex items-center justify-between rounded-lg border border-slate-100 px-3 py-2 text-xs"><span><strong>{grant.subject_type}:{grant.subject_id}</strong> → {grant.resource_type}/{grant.resource_id} · {grant.permission_key}</span><button type="button" onClick={() => void removeResourceGrant(grant)} className="rounded-md border border-red-200 px-2 py-1 font-semibold text-red-700">삭제</button></div>)}</div>
        <div className="space-y-3">
          {state.rbacMatrix.map((row) => {
            const hasAdminPermission = row.effective_permissions.some((item) => item.key.startsWith('admin.'));
            return (
              <div key={row.user_id} className="rounded-lg border border-slate-100 p-3 text-xs">
                <div className="mb-2 flex flex-wrap items-center gap-2">
                  <strong>{row.username}</strong>
                  <Badge tone={row.role === 'admin' ? 'green' : 'slate'}>{row.role}</Badge>
                  <span className="text-slate-400">id {row.user_id}</span>
                  <span className="text-slate-500">유효 권한 {row.effective_permissions.length}개 · 관리자 권한 {hasAdminPermission ? '보유' : '없음'}</span>
                </div>
                <div className="grid gap-3 md:grid-cols-2">
                  {row.role_permissions.length > 0 ? (
                    <PermissionGroup title="역할 권한">
                      {row.role_permissions.map((key) => <PermissionPill key={key} permissionKey={key} />)}
                    </PermissionGroup>
                  ) : <EmptyPermissionGroup title="역할 권한" />}
                  {row.direct_permissions.length > 0 ? (
                    <PermissionGroup title="직접 권한">
                      {row.direct_permissions.map((key) => <PermissionPill key={key} permissionKey={key} />)}
                    </PermissionGroup>
                  ) : <EmptyPermissionGroup title="직접 권한" />}
                  {row.group_permissions.length > 0 ? (
                    <PermissionGroup title="그룹 권한">
                      {row.group_permissions.map((item) => <PermissionPill key={`${item.group}:${item.key}`} permissionKey={item.key} prefix={item.group} />)}
                    </PermissionGroup>
                  ) : <EmptyPermissionGroup title="그룹 권한" />}
                  {row.effective_permissions.length > 0 ? (
                    <PermissionGroup title="유효 권한">
                      {row.effective_permissions.map((item) => <PermissionPill key={item.key} permissionKey={item.key} suffix={`출처 ${item.sources.join(', ')}`} />)}
                    </PermissionGroup>
                  ) : <EmptyPermissionGroup title="유효 권한" />}
                  {row.resource_grants.length > 0 ? (
                    <PermissionGroup title="리소스 권한">
                      {row.resource_grants.map((item) => (
                        <PermissionPill
                          key={`${item.resource_type}/${item.resource_id}:${item.permission_key}:${item.source}`}
                          permissionKey={item.permission_key}
                          prefix={`${item.resource_type}/${item.resource_id}`}
                          suffix={`출처 ${item.source}`}
                        />
                      ))}
                    </PermissionGroup>
                  ) : <EmptyPermissionGroup title="리소스 권한" />}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
