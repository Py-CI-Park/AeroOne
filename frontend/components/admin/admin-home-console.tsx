'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';

import {
  addUserGroup,
  createAdminUser,
  createBackup,
  changeOwnPassword,
  createResourceGrant,
  createServiceModule,
  deleteResourceGrant,
  deleteServiceModule,
  createCategory,
  createTag,
  dryRunRestoreBackup,
  fetchAdminAiStatus,
  fetchAdminGroups,
  fetchAdminPermissions,
  getBrowserApiBase,
  fetchAdminSummary,
  fetchAdminUsers,
  fetchRbacMatrix,
  fetchAssetHealth,
  fetchConfigHealth,
  fetchConnectedUsers,
  fetchAuditEvents,
  fetchBackups,
  fetchCategories,
  fetchServiceModulesAdmin,
  fetchTags,
  listResourceGrants,
  purgeSessions,
  fetchUnifiedSearch,
  removeUserGroup,
  resetAdminUserPassword,
  updateAdminUser,
  updateCategory,
  updateServiceModule,
  updateTag,
  upsertAdminGroup,
  validateBackup,
} from '@/lib/api';
import { getCsrfCookie } from '@/lib/cookies';
import type {
  AdminGroup,
  AdminSummary,
  AdminUser,
  AiAdminStatus,
  AssetHealthResponse,
  ConfigHealthResponse,
  ConnectedUsersResponse,
  AuditEvent,
  BackupRecord,
  Category,
  Permission,
  RbacMatrixUser,
  ResourceGrant,
  ServiceModule,
  Tag,
  UnifiedSearchResult,
} from '@/lib/types';

type ModuleDraft = Pick<ServiceModule, 'title' | 'description' | 'href' | 'section' | 'status' | 'badge' | 'sort_order' | 'is_enabled' | 'is_external' | 'visibility'>;
type UserDraft = Pick<AdminUser, 'email' | 'role' | 'is_active'> & { permissions_csv: string };
type TaxonomyDraft = { name: string; description?: string | null; sort_order: number; is_active: boolean };

type PanelState = {
  summary?: AdminSummary;
  ai?: AiAdminStatus;
  users: AdminUser[];
  connectedUsers?: ConnectedUsersResponse;
  permissions: Permission[];
  groups: AdminGroup[];
  rbacMatrix: RbacMatrixUser[];
  resourceGrants: ResourceGrant[];
  audits: AuditEvent[];
  modules: ServiceModule[];
  health?: AssetHealthResponse;
  configHealth?: ConfigHealthResponse;
  backups: BackupRecord[];
  categories: Category[];
  tags: Tag[];
  searchResults: UnifiedSearchResult[];
  error?: string;
  message?: string;
  busy?: string;
};

const initialState: PanelState = {
  users: [],
  permissions: [],
  groups: [],
  rbacMatrix: [],
  resourceGrants: [],
  audits: [],
  modules: [],
  backups: [],
  categories: [],
  tags: [],
  searchResults: [],
};

function Badge({ children, tone = 'slate' }: { children: React.ReactNode; tone?: 'slate' | 'green' | 'amber' | 'red' | 'blue' }) {
  const classes = {
    slate: 'border-slate-200 bg-slate-50 text-slate-700',
    green: 'border-emerald-200 bg-emerald-50 text-emerald-700',
    amber: 'border-amber-200 bg-amber-50 text-amber-800',
    red: 'border-red-200 bg-red-50 text-red-700',
    blue: 'border-blue-200 bg-blue-50 text-blue-700',
  }[tone];
  return <span className={`rounded-full border px-2 py-0.5 text-xs font-semibold ${classes}`}>{children}</span>;
}

function parseCsv(value: string): string[] {
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
}

function moduleToDraft(module: ServiceModule): ModuleDraft {
  return {
    title: module.title,
    description: module.description ?? '',
    href: module.href,
    section: module.section,
    status: module.status,
    badge: module.badge,
    sort_order: module.sort_order,
    is_enabled: module.is_enabled,
    is_external: module.is_external,
    visibility: module.visibility ?? 'admin',
  };
}

function userToDraft(user: AdminUser): UserDraft {
  return {
    email: user.email ?? '',
    role: user.role,
    is_active: user.is_active,
    permissions_csv: user.permissions.join(', '),
  };
}

function categoryToDraft(category: Category): TaxonomyDraft {
  return {
    name: category.name,
    description: category.description ?? '',
    sort_order: category.sort_order ?? 0,
    is_active: category.is_active ?? true,
  };
}

function tagToDraft(tag: Tag): TaxonomyDraft {
  return {
    name: tag.name,
    sort_order: tag.sort_order ?? 0,
    is_active: tag.is_active ?? true,
  };
}

export function AdminHomeConsole() {
  const [state, setState] = useState<PanelState>(initialState);
  const [moduleDrafts, setModuleDrafts] = useState<Record<number, ModuleDraft>>({});
  const [userDrafts, setUserDrafts] = useState<Record<number, UserDraft>>({});
  const [categoryDrafts, setCategoryDrafts] = useState<Record<number, TaxonomyDraft>>({});
  const [tagDrafts, setTagDrafts] = useState<Record<number, TaxonomyDraft>>({});
  const [userForm, setUserForm] = useState({ username: '', password: '', email: '', role: 'user', is_active: true });
  const [groupForm, setGroupForm] = useState({ key: '', name: '', description: '', is_active: true, permissions_csv: '' });
  const [grantForm, setGrantForm] = useState({ subject_type: 'user' as 'user' | 'group', subject_id: '', resource_type: 'collection', resource_id: 'nsa', permission_key: 'collections.nsa.read' });
  const [membershipForm, setMembershipForm] = useState({ user_id: '', group_id: '' });
  const [categoryForm, setCategoryForm] = useState({ name: '', description: '', sort_order: 0, is_active: true });
  const [tagForm, setTagForm] = useState({ name: '', sort_order: 0, is_active: true });
  const [searchForm, setSearchForm] = useState({ q: '', includeNsa: false });
  const [moduleForm, setModuleForm] = useState({ key: '', title: '', section: 'Development', status: 'development', href: '', description: '', sort_order: 0, is_external: false, visibility: 'admin' });
  const [passwordForm, setPasswordForm] = useState({ current: '', next: '', confirm: '' });

  async function refresh() {
    try {
      const [summary, users, connectedUsers, permissions, groups, rbacMatrix, resourceGrants, audits, modules, health, configHealth, backups, categories, tags, ai] = await Promise.all([
        fetchAdminSummary(),
        fetchAdminUsers(),
        fetchConnectedUsers(),
        fetchAdminPermissions(),
        fetchAdminGroups(),
        fetchRbacMatrix(),
        listResourceGrants(),
        fetchAuditEvents(),
        fetchServiceModulesAdmin(),
        fetchAssetHealth(),
        fetchConfigHealth(),
        fetchBackups(),
        fetchCategories(),
        fetchTags(),
        fetchAdminAiStatus(),
      ]);
      setState((current) => ({ ...current, summary, users, connectedUsers, permissions, groups, rbacMatrix, resourceGrants, audits, modules, health, configHealth, backups, categories, tags, ai, error: undefined }));
      setModuleDrafts(Object.fromEntries(modules.map((module) => [module.id, moduleToDraft(module)])));
      setUserDrafts(Object.fromEntries(users.map((user) => [user.id, userToDraft(user)])));
      setCategoryDrafts(Object.fromEntries(categories.map((category) => [category.id, categoryToDraft(category)])));
      setTagDrafts(Object.fromEntries(tags.map((tag) => [tag.id, tagToDraft(tag)])));
    } catch (error) {
      setState((current) => ({ ...current, error: error instanceof Error ? error.message : '관리자 정보를 불러오지 못했습니다.' }));
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function runBusy(label: string, action: () => Promise<void>) {
    setState((current) => ({ ...current, busy: label, message: undefined }));
    try {
      await action();
      await refresh();
    } finally {
      setState((current) => ({ ...current, busy: undefined }));
    }
  }

  async function saveModule(module: ServiceModule) {
    const draft = moduleDrafts[module.id] ?? moduleToDraft(module);
    await runBusy(`module-${module.id}`, async () => {
      await updateServiceModule(module.id, draft, getCsrfCookie());
      setState((current) => ({ ...current, message: `${draft.title} 모듈을 저장했습니다.` }));
    });
  }

  async function toggleModule(module: ServiceModule) {
    const draft = moduleDrafts[module.id] ?? moduleToDraft(module);
    await runBusy(`module-${module.id}`, async () => {
      await updateServiceModule(module.id, { is_enabled: !draft.is_enabled }, getCsrfCookie());
      setState((current) => ({ ...current, message: `${module.title} 모듈 상태를 변경했습니다.` }));
    });
  }

  async function createModule() {
    if (!moduleForm.key.trim() || !moduleForm.title.trim()) return;
    await runBusy('module-create', async () => {
      await createServiceModule({ ...moduleForm, description: moduleForm.description || null }, getCsrfCookie());
      setModuleForm({ key: '', title: '', section: 'Development', status: 'development', href: '', description: '', sort_order: 0, is_external: false, visibility: 'admin' });
      setState((current) => ({ ...current, message: '대시보드 모듈을 추가했습니다.' }));
    });
  }

  async function removeModule(module: ServiceModule) {
    if (typeof window !== 'undefined' && !window.confirm(`${module.key} 모듈을 삭제할까요?`)) return;
    await runBusy(`module-${module.id}`, async () => {
      await deleteServiceModule(module.id, getCsrfCookie());
      setState((current) => ({ ...current, message: `${module.title} 모듈을 삭제했습니다.` }));
    });
  }

  async function changePassword() {
    if (!passwordForm.current || !passwordForm.next) return;
    if (passwordForm.next !== passwordForm.confirm) {
      setState((current) => ({ ...current, error: '새 비밀번호와 확인 값이 일치하지 않습니다.' }));
      return;
    }
    await runBusy('password-change', async () => {
      await changeOwnPassword(passwordForm.current, passwordForm.next, getCsrfCookie());
      setPasswordForm({ current: '', next: '', confirm: '' });
      setState((current) => ({ ...current, message: '관리자 비밀번호를 변경했습니다.' }));
    });
  }

  async function createUser() {
    if (!userForm.username.trim() || !userForm.password.trim()) return;
    await runBusy('user-create', async () => {
      await createAdminUser({ ...userForm, email: userForm.email || null }, getCsrfCookie());
      setUserForm({ username: '', password: '', email: '', role: 'user', is_active: true });
      setState((current) => ({ ...current, message: '사용자를 생성했습니다.' }));
    });
  }

  async function saveUser(user: AdminUser) {
    const draft = userDrafts[user.id] ?? userToDraft(user);
    await runBusy(`user-${user.id}`, async () => {
      await updateAdminUser(user.id, { email: draft.email || null, role: draft.role, is_active: draft.is_active, permissions: parseCsv(draft.permissions_csv) }, getCsrfCookie());
      setState((current) => ({ ...current, message: `${user.username} 사용자를 저장했습니다.` }));
    });
  }

  async function resetPassword(user: AdminUser) {
    const temporaryPassword = window.prompt(`${user.username} 임시 비밀번호를 입력하세요.`);
    if (!temporaryPassword) return;
    await runBusy(`user-reset-${user.id}`, async () => {
      await resetAdminUserPassword(user.id, temporaryPassword, getCsrfCookie());
      setState((current) => ({ ...current, message: `${user.username} 비밀번호를 재설정했습니다.` }));
    });
  }



  async function saveResourceGrant() {
    const subjectId = Number(grantForm.subject_id);
    if (!subjectId || !grantForm.resource_type.trim() || !grantForm.resource_id.trim() || !grantForm.permission_key.trim()) return;
    await runBusy('resource-grant-save', async () => {
      await createResourceGrant({ subject_type: grantForm.subject_type, subject_id: subjectId, resource_type: grantForm.resource_type, resource_id: grantForm.resource_id, permission_key: grantForm.permission_key }, getCsrfCookie());
      setState((current) => ({ ...current, message: '리소스 권한을 부여했습니다.' }));
    });
  }

  async function removeResourceGrant(grant: ResourceGrant) {
    await runBusy(`resource-grant-${grant.id}`, async () => {
      await deleteResourceGrant(grant.id, getCsrfCookie());
      setState((current) => ({ ...current, message: '리소스 권한을 삭제했습니다.' }));
    });
  }

  async function changeMembership(action: 'add' | 'remove') {
    const userId = Number(membershipForm.user_id);
    const groupId = Number(membershipForm.group_id);
    if (!userId || !groupId) return;
    await runBusy(`membership-${action}`, async () => {
      if (action === 'add') await addUserGroup(userId, groupId, getCsrfCookie());
      else await removeUserGroup(userId, groupId, getCsrfCookie());
      setState((current) => ({ ...current, message: '사용자 그룹 멤버십을 변경했습니다.' }));
    });
  }

  async function saveGroup() {
    if (!groupForm.key.trim() || !groupForm.name.trim()) return;
    await runBusy('group-save', async () => {
      await upsertAdminGroup({ ...groupForm, permissions: parseCsv(groupForm.permissions_csv) }, getCsrfCookie());
      setGroupForm({ key: '', name: '', description: '', is_active: true, permissions_csv: '' });
      setState((current) => ({ ...current, message: '그룹/RBAC 설정을 저장했습니다.' }));
    });
  }

  async function createTaxonomy(kind: 'category' | 'tag') {
    await runBusy(`${kind}-create`, async () => {
      if (kind === 'category') {
        if (!categoryForm.name.trim()) return;
        await createCategory(categoryForm, getCsrfCookie());
        setCategoryForm({ name: '', description: '', sort_order: 0, is_active: true });
      } else {
        if (!tagForm.name.trim()) return;
        await createTag(tagForm, getCsrfCookie());
        setTagForm({ name: '', sort_order: 0, is_active: true });
      }
      setState((current) => ({ ...current, message: '카테고리/태그를 생성했습니다.' }));
    });
  }

  async function saveCategory(category: Category) {
    const draft = categoryDrafts[category.id] ?? categoryToDraft(category);
    await runBusy(`category-${category.id}`, async () => {
      await updateCategory(category.id, draft, getCsrfCookie());
      setState((current) => ({ ...current, message: `${category.name} 카테고리를 저장했습니다.` }));
    });
  }

  async function saveTag(tag: Tag) {
    const draft = tagDrafts[tag.id] ?? tagToDraft(tag);
    await runBusy(`tag-${tag.id}`, async () => {
      await updateTag(tag.id, draft, getCsrfCookie());
      setState((current) => ({ ...current, message: `${tag.name} 태그를 저장했습니다.` }));
    });
  }


  async function purgeSessionMetadata() {
    await runBusy('sessions-purge', async () => {
      const result = await purgeSessions(getCsrfCookie());
      setState((current) => ({ ...current, message: `세션/로그 정리 완료: 로그인 ${result.login_events_deleted}건 · 세션 ${result.session_activity_deleted}건` }));
    });
  }

  async function runBackup() {
    await runBusy('backup', async () => {
      await createBackup(getCsrfCookie());
      setState((current) => ({ ...current, message: '백업을 생성했습니다.' }));
    });
  }

  async function runValidate(id: number) {
    await runBusy(`backup-${id}`, async () => {
      const result = await validateBackup(id, getCsrfCookie());
      setState((current) => ({ ...current, message: result.valid ? '백업 검증 성공' : `백업 검증 실패: ${result.issues.join(', ')}` }));
    });
  }

  async function runRestoreDryRun(id: number) {
    await runBusy(`restore-${id}`, async () => {
      const result = await dryRunRestoreBackup(id, getCsrfCookie());
      setState((current) => ({
        ...current,
        message: result.compatible
          ? `복원 점검 성공: ${result.would_restore.join(', ')}`
          : `복원 점검 실패: ${result.issues.join(', ')}`,
      }));
    });
  }

  async function runSearch() {
    if (searchForm.q.trim().length < 2) return;
    setState((current) => ({ ...current, busy: 'search', message: undefined }));
    try {
      const payload = await fetchUnifiedSearch(searchForm.q, searchForm.includeNsa);
      setState((current) => ({ ...current, searchResults: payload.results, message: `통합 검색 결과 ${payload.results.length}건` }));
    } finally {
      setState((current) => ({ ...current, busy: undefined }));
    }
  }

  if (state.error) {
    return <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">{state.error}</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="text-sm text-slate-600">운영 콘솔은 DB, 자산, 권한, 감사, 백업 상태를 한 화면에 모읍니다.</div>
        <div className="flex gap-2">
          <Link href="/admin/newsletters" className="rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-700">뉴스레터 관리</Link>
          <Link href="/admin/read-events" className="rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-700">읽음 현황</Link>
          <a href={`${getBrowserApiBase()}/api/v1/admin/read-events.csv`} className="rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-700">읽음 CSV</a>
          <button type="button" onClick={() => void refresh()} className="rounded-md bg-slate-900 px-3 py-2 text-sm font-semibold text-white">새로고침</button>
        </div>
      </div>

      {state.message ? <div className="rounded-lg border border-blue-200 bg-blue-50 p-3 text-sm text-blue-700">{state.message}</div> : null}

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-xs font-semibold uppercase text-slate-500">Version / Mode</p>
          <p className="mt-2 text-2xl font-semibold">v{state.summary?.app_version ?? '-'}</p>
          <p className="text-sm text-slate-500">{state.summary?.app_env ?? '-'}</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-xs font-semibold uppercase text-slate-500">Newsletters</p>
          <p className="mt-2 text-2xl font-semibold">{state.summary?.newsletter_total ?? 0}</p>
          <p className="text-sm text-slate-500">최근: {state.summary?.latest_newsletter_title ?? '-'}</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-xs font-semibold uppercase text-slate-500">Assets</p>
          <p className="mt-2 text-2xl font-semibold">{state.health?.ok ?? 0} OK</p>
          <p className="text-sm text-slate-500">누락 {state.health?.missing ?? 0} · checksum {state.health?.checksum_mismatch ?? 0} · 설정 {state.health?.misconfig ?? 0}</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-xs font-semibold uppercase text-slate-500">AI 운영</p>
          <p className="mt-2 text-2xl font-semibold">{String(state.summary?.ai_status?.status ?? '-')}</p>
          <p className="text-sm text-slate-500">logs {state.ai?.request_logs_total ?? 0} · failures {state.ai?.request_failures ?? 0}</p>
        </div>
      </section>


      <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="mb-3 flex items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold">접속자/세션</h2>
            <p className="text-sm text-slate-500">로그인 세션 활동과 익명 IP 읽음 집계를 함께 확인합니다.</p>
          </div>
          <button
            type="button"
            onClick={() => void purgeSessionMetadata()}
            disabled={state.busy === 'sessions-purge'}
            className="rounded-md border border-red-200 px-3 py-2 text-sm font-semibold text-red-700 disabled:opacity-50"
          >
            오래된 세션/로그 정리
          </button>
        </div>
        <div className="grid gap-4 lg:grid-cols-3">
          <div className="rounded-lg border border-slate-100 p-3">
            <p className="text-xs font-semibold uppercase text-slate-500">Active sessions</p>
            <p className="mt-1 text-2xl font-semibold">{state.connectedUsers?.active_count ?? 0}</p>
            <div className="mt-3 space-y-2 text-sm">
              {(state.connectedUsers?.active_sessions ?? []).length ? state.connectedUsers?.active_sessions.map((session) => (
                <div key={`${session.user_id}-${session.last_seen_at}`} className="flex items-center justify-between gap-2">
                  <span className="font-medium text-slate-700">{session.username}</span>
                  <span className="text-xs text-slate-500">{new Date(session.last_seen_at).toLocaleString('ko-KR')}</span>
                </div>
              )) : <p className="text-slate-500">활성 로그인 세션 없음</p>}
            </div>
          </div>
          <div className="rounded-lg border border-slate-100 p-3">
            <p className="text-xs font-semibold uppercase text-slate-500">Recent login events</p>
            <p className="mt-1 text-sm text-slate-600">실패 {state.connectedUsers?.login_failure_count ?? 0}건</p>
            <div className="mt-3 max-h-40 space-y-2 overflow-auto text-sm">
              {(state.connectedUsers?.recent_login_events ?? []).slice(0, 6).map((event) => (
                <div key={event.id} className="flex items-center justify-between gap-2">
                  <span>{event.username}</span>
                  <Badge tone={event.status === 'success' ? 'green' : 'red'}>{event.status}</Badge>
                </div>
              ))}
            </div>
          </div>
          <div className="rounded-lg border border-slate-100 p-3">
            <p className="text-xs font-semibold uppercase text-slate-500">Anonymous read tracking</p>
            <p className="mt-1 text-2xl font-semibold">{state.connectedUsers?.read_tracking_summary.total_reads ?? 0}</p>
            <p className="text-sm text-slate-500">IP/뉴스레터 집계 행 {state.connectedUsers?.read_tracking_summary.rows ?? 0}개</p>
          </div>
        </div>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold">DB/자산 경로 상태</h2>
          <Badge tone="blue">config-health</Badge>
        </div>
        <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
          {(state.configHealth?.roots ?? []).map((root) => (
            <div key={root.kind} className="rounded-lg border border-slate-100 p-3 text-sm">
              <div className="mb-1 flex items-center justify-between gap-2">
                <strong>{root.kind}</strong>
                <Badge tone={root.exists && root.readable ? 'green' : 'red'}>{root.exists && root.readable ? 'OK' : '점검 필요'}</Badge>
              </div>
              <p className="break-all font-mono text-xs text-slate-500">{root.resolved_path}</p>
              <p className="mt-1 text-xs text-slate-500">exists {String(root.exists)} · readable {String(root.readable)}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold">대시보드 모듈 DB 관리</h2>
          <Badge tone="green">CRUD / reorder / status</Badge>
        </div>
        <div className="grid gap-3 xl:grid-cols-2">
          {state.modules.map((module) => {
            const draft = moduleDrafts[module.id] ?? moduleToDraft(module);
            return (
              <div key={module.key} className="rounded-lg border border-slate-100 p-3 text-sm">
                <div className="mb-2 flex items-center justify-between gap-2">
                  <strong>{module.key}</strong>
                  <Badge tone={draft.is_enabled ? 'green' : 'amber'}>{draft.is_enabled ? 'enabled' : 'disabled'}</Badge>
                </div>
                <div className="grid gap-2 md:grid-cols-2">
                  <input value={draft.title} onChange={(event) => setModuleDrafts((current) => ({ ...current, [module.id]: { ...draft, title: event.target.value } }))} className="rounded-md border border-slate-300 px-2 py-1" aria-label={`${module.key} title`} />
                  <input value={draft.section} onChange={(event) => setModuleDrafts((current) => ({ ...current, [module.id]: { ...draft, section: event.target.value } }))} className="rounded-md border border-slate-300 px-2 py-1" aria-label={`${module.key} section`} />
                  <input value={draft.href} onChange={(event) => setModuleDrafts((current) => ({ ...current, [module.id]: { ...draft, href: event.target.value } }))} className="rounded-md border border-slate-300 px-2 py-1" aria-label={`${module.key} href`} />
                  <select value={draft.status} onChange={(event) => setModuleDrafts((current) => ({ ...current, [module.id]: { ...draft, status: event.target.value } }))} className="rounded-md border border-slate-300 px-2 py-1" aria-label={`${module.key} status`}>
                    <option value="active">active</option>
                    <option value="development">development</option>
                    <option value="coming_soon">coming soon</option>
                    <option value="hidden">hidden</option>
                  </select>
                  <input value={draft.badge} onChange={(event) => setModuleDrafts((current) => ({ ...current, [module.id]: { ...draft, badge: event.target.value } }))} className="rounded-md border border-slate-300 px-2 py-1" aria-label={`${module.key} badge`} />
                  <input type="number" value={draft.sort_order} onChange={(event) => setModuleDrafts((current) => ({ ...current, [module.id]: { ...draft, sort_order: Number(event.target.value) } }))} className="rounded-md border border-slate-300 px-2 py-1" aria-label={`${module.key} sort order`} />
                </div>
                <textarea value={draft.description ?? ''} onChange={(event) => setModuleDrafts((current) => ({ ...current, [module.id]: { ...draft, description: event.target.value } }))} className="mt-2 w-full rounded-md border border-slate-300 px-2 py-1" rows={2} aria-label={`${module.key} description`} />
                <label className="mt-2 inline-flex items-center gap-2 text-xs text-slate-600"><input type="checkbox" checked={draft.is_external} onChange={(event) => setModuleDrafts((current) => ({ ...current, [module.id]: { ...draft, is_external: event.target.checked } }))} /> external</label>
                <label className="mt-2 ml-3 inline-flex items-center gap-2 text-xs text-slate-600">audience
                  <select value={draft.visibility} onChange={(event) => setModuleDrafts((current) => ({ ...current, [module.id]: { ...draft, visibility: event.target.value } }))} className="rounded-md border border-slate-300 px-2 py-1" aria-label={`${module.key} visibility`}>
                    <option value="public">public</option>
                    <option value="admin">admin (operator only)</option>
                  </select>
                </label>
                <div className="mt-2 flex gap-2">
                  <button type="button" disabled={state.busy === `module-${module.id}`} onClick={() => void saveModule(module)} className="rounded-md bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-40">저장</button>
                  <button type="button" disabled={state.busy === `module-${module.id}`} onClick={() => void toggleModule(module)} className="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-700 disabled:opacity-40">{draft.is_enabled ? '비활성화' : '활성화'}</button>
                  <button type="button" disabled={state.busy === `module-${module.id}`} onClick={() => void removeModule(module)} className="rounded-md border border-rose-300 px-3 py-1.5 text-xs font-semibold text-rose-600 disabled:opacity-40">삭제</button>
                </div>
              </div>
            );
          })}
        </div>
        <div className="mt-4 rounded-lg border border-dashed border-slate-300 p-3 text-sm">
          <p className="mb-2 font-semibold text-slate-700">새 모듈 추가</p>
          <div className="grid gap-2 md:grid-cols-3">
            <input value={moduleForm.key} onChange={(event) => setModuleForm((current) => ({ ...current, key: event.target.value }))} placeholder="key" className="rounded-md border border-slate-300 px-2 py-1" aria-label="new module key" />
            <input value={moduleForm.title} onChange={(event) => setModuleForm((current) => ({ ...current, title: event.target.value }))} placeholder="title" className="rounded-md border border-slate-300 px-2 py-1" aria-label="new module title" />
            <input value={moduleForm.section} onChange={(event) => setModuleForm((current) => ({ ...current, section: event.target.value }))} placeholder="section" className="rounded-md border border-slate-300 px-2 py-1" aria-label="new module section" />
            <input value={moduleForm.href} onChange={(event) => setModuleForm((current) => ({ ...current, href: event.target.value }))} placeholder="href" className="rounded-md border border-slate-300 px-2 py-1" aria-label="new module href" />
            <select value={moduleForm.status} onChange={(event) => setModuleForm((current) => ({ ...current, status: event.target.value }))} className="rounded-md border border-slate-300 px-2 py-1" aria-label="new module status">
              <option value="active">active</option>
              <option value="development">development</option>
              <option value="coming_soon">coming soon</option>
              <option value="hidden">hidden</option>
            </select>
            <select value={moduleForm.visibility} onChange={(event) => setModuleForm((current) => ({ ...current, visibility: event.target.value }))} className="rounded-md border border-slate-300 px-2 py-1" aria-label="new module visibility">
              <option value="public">public</option>
              <option value="admin">admin (operator only)</option>
            </select>
          </div>
          <button type="button" disabled={state.busy === 'module-create'} onClick={() => void createModule()} className="mt-2 rounded-md bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-40">모듈 추가</button>
        </div>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold">관리자 계정 / 비밀번호</h2>
          <Badge tone="amber">self-service</Badge>
        </div>
        <p className="mb-3 text-sm text-slate-500">현재 비밀번호를 확인한 뒤 새 비밀번호로 교체합니다. 변경 즉시 다른 세션은 로그아웃됩니다.</p>
        <div className="grid gap-2 md:grid-cols-3">
          <input type="password" value={passwordForm.current} onChange={(event) => setPasswordForm((current) => ({ ...current, current: event.target.value }))} placeholder="현재 비밀번호" className="rounded-md border border-slate-300 px-2 py-1" aria-label="current password" />
          <input type="password" value={passwordForm.next} onChange={(event) => setPasswordForm((current) => ({ ...current, next: event.target.value }))} placeholder="새 비밀번호 (8자 이상)" className="rounded-md border border-slate-300 px-2 py-1" aria-label="new password" />
          <input type="password" value={passwordForm.confirm} onChange={(event) => setPasswordForm((current) => ({ ...current, confirm: event.target.value }))} placeholder="새 비밀번호 확인" className="rounded-md border border-slate-300 px-2 py-1" aria-label="confirm password" />
        </div>
        <button type="button" disabled={state.busy === 'password-change'} onClick={() => void changePassword()} className="mt-2 rounded-md bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-40">비밀번호 변경</button>
      </section>

      <section className="grid gap-6 xl:grid-cols-2">
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <h2 className="mb-3 text-lg font-semibold">사용자/RBAC</h2>
          <div className="mb-4 grid gap-2 rounded-lg border border-slate-100 p-3 text-sm md:grid-cols-2">
            <input placeholder="username" value={userForm.username} onChange={(event) => setUserForm((current) => ({ ...current, username: event.target.value }))} className="rounded-md border border-slate-300 px-2 py-1" />
            <input placeholder="temporary password" type="password" value={userForm.password} onChange={(event) => setUserForm((current) => ({ ...current, password: event.target.value }))} className="rounded-md border border-slate-300 px-2 py-1" />
            <input placeholder="email" value={userForm.email} onChange={(event) => setUserForm((current) => ({ ...current, email: event.target.value }))} className="rounded-md border border-slate-300 px-2 py-1" />
            <select value={userForm.role} onChange={(event) => setUserForm((current) => ({ ...current, role: event.target.value }))} className="rounded-md border border-slate-300 px-2 py-1"><option value="admin">admin</option><option value="user">user</option><option value="pending">pending</option></select>
            <label className="inline-flex items-center gap-2 text-xs text-slate-600"><input type="checkbox" checked={userForm.is_active} onChange={(event) => setUserForm((current) => ({ ...current, is_active: event.target.checked }))} /> active</label>
            <button type="button" disabled={state.busy === 'user-create'} onClick={() => void createUser()} className="rounded-md bg-slate-900 px-3 py-2 text-xs font-semibold text-white disabled:opacity-40">사용자 생성</button>
          </div>
          <div className="space-y-2">
            {state.users.map((user) => {
              const draft = userDrafts[user.id] ?? userToDraft(user);
              return (
                <div key={user.id} className="rounded-lg border border-slate-100 px-3 py-2 text-sm">
                  <div className="flex items-center justify-between gap-2"><span className="font-medium">{user.username}</span><Badge tone={draft.role === 'admin' ? 'green' : draft.role === 'pending' ? 'amber' : 'slate'}>{draft.role}</Badge></div>
                  <div className="mt-2 grid gap-2 md:grid-cols-2">
                    <input value={draft.email ?? ''} onChange={(event) => setUserDrafts((current) => ({ ...current, [user.id]: { ...draft, email: event.target.value } }))} className="rounded-md border border-slate-300 px-2 py-1" aria-label={`${user.username} email`} />
                    <select value={draft.role} onChange={(event) => setUserDrafts((current) => ({ ...current, [user.id]: { ...draft, role: event.target.value } }))} className="rounded-md border border-slate-300 px-2 py-1" aria-label={`${user.username} role`}><option value="admin">admin</option><option value="user">user</option><option value="pending">pending</option></select>
                  </div>
                  <textarea value={draft.permissions_csv} onChange={(event) => setUserDrafts((current) => ({ ...current, [user.id]: { ...draft, permissions_csv: event.target.value } }))} className="mt-2 w-full rounded-md border border-slate-300 px-2 py-1 font-mono text-xs" rows={2} aria-label={`${user.username} permissions`} />
                  <label className="mt-2 inline-flex items-center gap-2 text-xs text-slate-600"><input type="checkbox" checked={draft.is_active} onChange={(event) => setUserDrafts((current) => ({ ...current, [user.id]: { ...draft, is_active: event.target.checked } }))} /> active</label>
                  <div className="mt-2 flex gap-2"><button type="button" onClick={() => void saveUser(user)} className="rounded-md bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white">저장</button><button type="button" onClick={() => void resetPassword(user)} className="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-700">비밀번호 재설정</button></div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <h2 className="mb-3 text-lg font-semibold">그룹/RBAC 권한</h2>
          <p className="mb-3 text-xs text-slate-500">사용 가능 권한 {state.permissions.length}개: {state.permissions.slice(0, 5).map((permission) => permission.key).join(', ')}{state.permissions.length > 5 ? ' ...' : ''}</p>
          <div className="grid gap-2 rounded-lg border border-slate-100 p-3 text-sm md:grid-cols-2">
            <input placeholder="group key" value={groupForm.key} onChange={(event) => setGroupForm((current) => ({ ...current, key: event.target.value }))} className="rounded-md border border-slate-300 px-2 py-1" />
            <input placeholder="group name" value={groupForm.name} onChange={(event) => setGroupForm((current) => ({ ...current, name: event.target.value }))} className="rounded-md border border-slate-300 px-2 py-1" />
            <input placeholder="description" value={groupForm.description} onChange={(event) => setGroupForm((current) => ({ ...current, description: event.target.value }))} className="rounded-md border border-slate-300 px-2 py-1 md:col-span-2" />
            <textarea placeholder="permission keys, comma-separated" value={groupForm.permissions_csv} onChange={(event) => setGroupForm((current) => ({ ...current, permissions_csv: event.target.value }))} className="rounded-md border border-slate-300 px-2 py-1 font-mono text-xs md:col-span-2" rows={2} />
            <label className="inline-flex items-center gap-2 text-xs text-slate-600"><input type="checkbox" checked={groupForm.is_active} onChange={(event) => setGroupForm((current) => ({ ...current, is_active: event.target.checked }))} /> active</label>
            <button type="button" disabled={state.busy === 'group-save'} onClick={() => void saveGroup()} className="rounded-md bg-slate-900 px-3 py-2 text-xs font-semibold text-white disabled:opacity-40">그룹 저장</button>
          </div>
          <div className="mt-3 space-y-2">
            {state.groups.length === 0 ? <p className="text-sm text-slate-500">등록된 그룹이 없습니다.</p> : null}
            {state.groups.map((group) => <div key={group.id} className="rounded-lg border border-slate-100 px-3 py-2 text-sm"><div className="flex justify-between"><strong>{group.name}</strong><Badge tone={group.is_active ? 'green' : 'amber'}>{group.key}</Badge></div><p className="mt-1 font-mono text-xs text-slate-500">{group.permissions.join(', ') || '권한 없음'}</p></div>)}
          </div>
        </div>
      </section>



      <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <h2 className="mb-3 text-lg font-semibold">RBAC 매트릭스 / 리소스 권한</h2>
        <div className="mb-4 grid gap-2 rounded-lg border border-slate-100 p-3 text-sm md:grid-cols-5">
          <select value={grantForm.subject_type} onChange={(event) => setGrantForm((current) => ({ ...current, subject_type: event.target.value as 'user' | 'group' }))} className="rounded-md border border-slate-300 px-2 py-1" aria-label="grant subject type"><option value="user">user</option><option value="group">group</option></select>
          <input placeholder="subject id" value={grantForm.subject_id} onChange={(event) => setGrantForm((current) => ({ ...current, subject_id: event.target.value }))} className="rounded-md border border-slate-300 px-2 py-1" />
          <input placeholder="resource type" value={grantForm.resource_type} onChange={(event) => setGrantForm((current) => ({ ...current, resource_type: event.target.value }))} className="rounded-md border border-slate-300 px-2 py-1" />
          <input placeholder="resource id" value={grantForm.resource_id} onChange={(event) => setGrantForm((current) => ({ ...current, resource_id: event.target.value }))} className="rounded-md border border-slate-300 px-2 py-1" />
          <input placeholder="permission key" value={grantForm.permission_key} onChange={(event) => setGrantForm((current) => ({ ...current, permission_key: event.target.value }))} className="rounded-md border border-slate-300 px-2 py-1" />
          <button type="button" onClick={() => void saveResourceGrant()} className="rounded-md bg-slate-900 px-3 py-2 text-xs font-semibold text-white md:col-span-5">리소스 권한 부여</button>
        </div>
        <div className="mb-4 grid gap-2 rounded-lg border border-slate-100 p-3 text-sm md:grid-cols-4">
          <input placeholder="user id" value={membershipForm.user_id} onChange={(event) => setMembershipForm((current) => ({ ...current, user_id: event.target.value }))} className="rounded-md border border-slate-300 px-2 py-1" />
          <input placeholder="group id" value={membershipForm.group_id} onChange={(event) => setMembershipForm((current) => ({ ...current, group_id: event.target.value }))} className="rounded-md border border-slate-300 px-2 py-1" />
          <button type="button" onClick={() => void changeMembership('add')} className="rounded-md bg-blue-600 px-3 py-2 text-xs font-semibold text-white">그룹 추가</button>
          <button type="button" onClick={() => void changeMembership('remove')} className="rounded-md border border-slate-300 px-3 py-2 text-xs font-semibold text-slate-700">그룹 제거</button>
        </div>
        <div className="mb-4 space-y-2">
          {state.resourceGrants.map((grant) => <div key={grant.id} className="flex items-center justify-between rounded-lg border border-slate-100 px-3 py-2 text-xs"><span><strong>{grant.subject_type}:{grant.subject_id}</strong> → {grant.resource_type}/{grant.resource_id} · {grant.permission_key}</span><button type="button" onClick={() => void removeResourceGrant(grant)} className="rounded-md border border-red-200 px-2 py-1 font-semibold text-red-700">삭제</button></div>)}
        </div>
        <div className="space-y-3">
          {state.rbacMatrix.map((row) => <div key={row.user_id} className="rounded-lg border border-slate-100 p-3 text-xs"><div className="mb-1 flex items-center gap-2"><strong>{row.username}</strong><Badge tone={row.role === 'admin' ? 'green' : 'slate'}>{row.role}</Badge><span className="text-slate-400">id {row.user_id}</span></div><p><strong>role</strong>: {row.role_permissions.join(', ') || '없음'}</p><p><strong>direct</strong>: {row.direct_permissions.join(', ') || '없음'}</p><p><strong>group</strong>: {row.group_permissions.map((item) => `${item.group}:${item.key}`).join(', ') || '없음'}</p><p><strong>effective</strong>: {row.effective_permissions.map((item) => `${item.key} [${item.sources.join('|')}]`).join(', ') || '없음'}</p><p><strong>resource</strong>: {row.resource_grants.map((item) => `${item.resource_type}/${item.resource_id}:${item.permission_key} [${item.source}]`).join(', ') || '없음'}</p></div>)}
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-2">
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <h2 className="mb-3 text-lg font-semibold">카테고리/태그 관리</h2>
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <div className="mb-2 grid gap-2 text-sm">
                <input placeholder="카테고리명" value={categoryForm.name} onChange={(event) => setCategoryForm((current) => ({ ...current, name: event.target.value }))} className="rounded-md border border-slate-300 px-2 py-1" />
                <input placeholder="설명" value={categoryForm.description} onChange={(event) => setCategoryForm((current) => ({ ...current, description: event.target.value }))} className="rounded-md border border-slate-300 px-2 py-1" />
                <input type="number" value={categoryForm.sort_order} onChange={(event) => setCategoryForm((current) => ({ ...current, sort_order: Number(event.target.value) }))} className="rounded-md border border-slate-300 px-2 py-1" />
                <button type="button" onClick={() => void createTaxonomy('category')} className="rounded-md bg-slate-900 px-3 py-2 text-xs font-semibold text-white">카테고리 생성</button>
              </div>
              <div className="space-y-2">
                {state.categories.map((category) => {
                  const draft = categoryDrafts[category.id] ?? categoryToDraft(category);
                  return <div key={category.id} className="rounded-lg border border-slate-100 p-2 text-sm"><input value={draft.name} onChange={(event) => setCategoryDrafts((current) => ({ ...current, [category.id]: { ...draft, name: event.target.value } }))} className="w-full rounded-md border border-slate-300 px-2 py-1" /><div className="mt-1 flex items-center gap-2"><input type="number" value={draft.sort_order} onChange={(event) => setCategoryDrafts((current) => ({ ...current, [category.id]: { ...draft, sort_order: Number(event.target.value) } }))} className="w-20 rounded-md border border-slate-300 px-2 py-1" /><label className="text-xs"><input type="checkbox" checked={draft.is_active} onChange={(event) => setCategoryDrafts((current) => ({ ...current, [category.id]: { ...draft, is_active: event.target.checked } }))} /> active</label><button type="button" onClick={() => void saveCategory(category)} className="rounded-md border border-slate-300 px-2 py-1 text-xs">저장</button></div></div>;
                })}
              </div>
            </div>
            <div>
              <div className="mb-2 grid gap-2 text-sm">
                <input placeholder="태그명" value={tagForm.name} onChange={(event) => setTagForm((current) => ({ ...current, name: event.target.value }))} className="rounded-md border border-slate-300 px-2 py-1" />
                <input type="number" value={tagForm.sort_order} onChange={(event) => setTagForm((current) => ({ ...current, sort_order: Number(event.target.value) }))} className="rounded-md border border-slate-300 px-2 py-1" />
                <button type="button" onClick={() => void createTaxonomy('tag')} className="rounded-md bg-slate-900 px-3 py-2 text-xs font-semibold text-white">태그 생성</button>
              </div>
              <div className="space-y-2">
                {state.tags.map((tag) => {
                  const draft = tagDrafts[tag.id] ?? tagToDraft(tag);
                  return <div key={tag.id} className="rounded-lg border border-slate-100 p-2 text-sm"><input value={draft.name} onChange={(event) => setTagDrafts((current) => ({ ...current, [tag.id]: { ...draft, name: event.target.value } }))} className="w-full rounded-md border border-slate-300 px-2 py-1" /><div className="mt-1 flex items-center gap-2"><input type="number" value={draft.sort_order} onChange={(event) => setTagDrafts((current) => ({ ...current, [tag.id]: { ...draft, sort_order: Number(event.target.value) } }))} className="w-20 rounded-md border border-slate-300 px-2 py-1" /><label className="text-xs"><input type="checkbox" checked={draft.is_active} onChange={(event) => setTagDrafts((current) => ({ ...current, [tag.id]: { ...draft, is_active: event.target.checked } }))} /> active</label><button type="button" onClick={() => void saveTag(tag)} className="rounded-md border border-slate-300 px-2 py-1 text-xs">저장</button></div></div>;
                })}
              </div>
            </div>
          </div>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <h2 className="mb-3 text-lg font-semibold">통합 검색 / AI 운영</h2>
          <div className="flex flex-wrap gap-2 text-sm">
            <input placeholder="뉴스레터·Document·Civil 검색" value={searchForm.q} onChange={(event) => setSearchForm((current) => ({ ...current, q: event.target.value }))} className="min-w-64 flex-1 rounded-md border border-slate-300 px-2 py-1" />
            <label className="inline-flex items-center gap-2 text-xs text-slate-600"><input type="checkbox" checked={searchForm.includeNsa} onChange={(event) => setSearchForm((current) => ({ ...current, includeNsa: event.target.checked }))} /> NSA 포함</label>
            <button type="button" onClick={() => void runSearch()} className="rounded-md bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white">검색</button>
          </div>
          <div className="mt-3 space-y-2">
            {state.searchResults.map((result, index) => <a key={`${result.source}-${result.url}-${index}`} href={result.url} className="block rounded-lg border border-slate-100 px-3 py-2 text-sm"><div className="flex items-center justify-between gap-2"><strong>{result.title}</strong><Badge tone="blue">{result.source}</Badge></div><p className="mt-1 text-slate-500">{result.snippet || result.url}</p></a>)}
            {state.searchResults.length === 0 ? <p className="text-sm text-slate-500">2글자 이상 입력하면 뉴스레터와 문서를 한 번에 검색합니다. NSA는 권한이 있을 때만 포함됩니다.</p> : null}
          </div>
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-2">
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-lg font-semibold">백업</h2>
            <button type="button" disabled={state.busy === 'backup'} onClick={() => void runBackup()} className="rounded-md bg-blue-600 px-3 py-2 text-sm font-semibold text-white disabled:opacity-40">백업 생성</button>
          </div>
          <div className="space-y-2">
            {state.backups.map((backup) => (
              <div key={backup.id} className="flex items-center justify-between gap-3 rounded-lg border border-slate-100 px-3 py-2 text-sm">
                <div>
                  <p className="font-medium">{backup.filename}</p>
                  <p className="font-mono text-xs text-slate-500">{backup.sha256.slice(0, 16)} · {backup.file_size} bytes · {backup.status}</p>
                </div>
                <div className="flex gap-2"><button type="button" onClick={() => void runValidate(backup.id)} className="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-700">검증</button><button type="button" onClick={() => void runRestoreDryRun(backup.id)} className="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-700">복원 점검</button><a href={`${getBrowserApiBase()}/api/v1/admin/backups/${backup.id}/download`} className="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-700">다운로드</a></div>
              </div>
            ))}
            {state.backups.length === 0 ? <p className="text-sm text-slate-500">아직 생성된 백업이 없습니다.</p> : null}
          </div>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <h2 className="mb-3 text-lg font-semibold">최근 감사 로그</h2>
          <div className="space-y-2">
            {state.audits.map((event) => (
              <div key={event.id} className="rounded-lg border border-slate-100 px-3 py-2 text-sm">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-xs text-slate-500">{event.action}</span>
                  <Badge>{event.status}</Badge>
                </div>
                <p className="mt-1 text-slate-600">{event.actor_username ?? 'system'} → {event.target_type} {event.target_id ?? ''}</p>
                <p className="mt-1 text-xs text-slate-400">{event.created_at}</p>
              </div>
            ))}
            {state.audits.length === 0 ? <p className="text-sm text-slate-500">감사 이벤트가 아직 없습니다.</p> : null}
          </div>
        </div>
      </section>
    </div>
  );
}
