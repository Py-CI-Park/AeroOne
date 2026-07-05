'use client';

import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';
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
  fetchUnifiedSearch,
  removeUserGroup,
  resetAdminUserPassword,
  updateAdminUser,
  updateCategory,
  updateServiceModule,
  updateTag,
  upsertAdminGroup,
  validateBackup,
  listResourceGrants,
  purgeSessions,
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
import { AdminModulesSection } from './sections/admin-modules-section';
import { AdminUsersSection } from './sections/admin-users-section';
import { AdminRbacSection } from './sections/admin-rbac-section';
import { AdminSessionsSection } from './sections/admin-sessions-section';
import { AdminSystemSection } from './sections/admin-system-section';
import { AdminTaxonomySection } from './sections/admin-taxonomy-section';
import { AdminSearchSection } from './sections/admin-search-section';
import { AdminBackupsSection } from './sections/admin-backups-section';

export type ModuleDraft = Pick<ServiceModule, 'title' | 'description' | 'href' | 'section' | 'status' | 'badge' | 'sort_order' | 'is_enabled' | 'is_external' | 'visibility'>;
export type UserDraft = Pick<AdminUser, 'email' | 'role' | 'is_active'> & { permissions_csv: string };
export type TaxonomyDraft = { name: string; description?: string; sort_order: number; is_active: boolean };

type PanelState = {
  summary?: AdminSummary;
  users: AdminUser[];
  permissions: Permission[];
  groups: AdminGroup[];
  rbacMatrix: RbacMatrixUser[];
  resourceGrants: ResourceGrant[];
  audits: AuditEvent[];
  modules: ServiceModule[];
  connectedUsers?: ConnectedUsersResponse;
  health?: AssetHealthResponse;
  configHealth?: ConfigHealthResponse;
  backups: BackupRecord[];
  categories: Category[];
  tags: Tag[];
  ai?: AiAdminStatus;
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

export function Badge({ children, tone = 'slate' }: { children: React.ReactNode; tone?: 'slate' | 'green' | 'amber' | 'red' | 'blue' }) {
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
  return value.split(',').map((item) => item.trim()).filter(Boolean);
}

export function moduleToDraft(module: ServiceModule): ModuleDraft {
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

export function userToDraft(user: AdminUser): UserDraft {
  return { email: user.email ?? '', role: user.role, is_active: user.is_active, permissions_csv: user.permissions.join(', ') };
}

export function categoryToDraft(category: Category): TaxonomyDraft {
  return { name: category.name, description: category.description ?? '', sort_order: category.sort_order ?? 0, is_active: category.is_active ?? true };
}

export function tagToDraft(tag: Tag): TaxonomyDraft {
  return { name: tag.name, sort_order: tag.sort_order ?? 0, is_active: tag.is_active ?? true };
}

type AdminConsoleContextValue = {
  state: PanelState;
  refresh: () => Promise<void>;
  moduleDrafts: Record<number, ModuleDraft>;
  setModuleDrafts: React.Dispatch<React.SetStateAction<Record<number, ModuleDraft>>>;
  userDrafts: Record<number, UserDraft>;
  setUserDrafts: React.Dispatch<React.SetStateAction<Record<number, UserDraft>>>;
  categoryDrafts: Record<number, TaxonomyDraft>;
  setCategoryDrafts: React.Dispatch<React.SetStateAction<Record<number, TaxonomyDraft>>>;
  tagDrafts: Record<number, TaxonomyDraft>;
  setTagDrafts: React.Dispatch<React.SetStateAction<Record<number, TaxonomyDraft>>>;
  moduleForm: { key: string; title: string; section: string; status: string; href: string; description: string; sort_order: number; is_external: boolean; visibility: string };
  setModuleForm: React.Dispatch<React.SetStateAction<AdminConsoleContextValue['moduleForm']>>;
  userForm: { username: string; password: string; email: string; role: string; is_active: boolean };
  setUserForm: React.Dispatch<React.SetStateAction<AdminConsoleContextValue['userForm']>>;
  groupForm: { key: string; name: string; description: string; is_active: boolean; permissions_csv: string };
  setGroupForm: React.Dispatch<React.SetStateAction<AdminConsoleContextValue['groupForm']>>;
  grantForm: { subject_type: 'user' | 'group'; subject_id: string; resource_type: string; resource_id: string; permission_key: string };
  setGrantForm: React.Dispatch<React.SetStateAction<AdminConsoleContextValue['grantForm']>>;
  membershipForm: { user_id: string; group_id: string };
  setMembershipForm: React.Dispatch<React.SetStateAction<AdminConsoleContextValue['membershipForm']>>;
  categoryForm: { name: string; description: string; sort_order: number; is_active: boolean };
  setCategoryForm: React.Dispatch<React.SetStateAction<AdminConsoleContextValue['categoryForm']>>;
  tagForm: { name: string; sort_order: number; is_active: boolean };
  setTagForm: React.Dispatch<React.SetStateAction<AdminConsoleContextValue['tagForm']>>;
  searchForm: { q: string; includeNsa: boolean };
  setSearchForm: React.Dispatch<React.SetStateAction<AdminConsoleContextValue['searchForm']>>;
  passwordForm: { current: string; next: string; confirm: string };
  setPasswordForm: React.Dispatch<React.SetStateAction<AdminConsoleContextValue['passwordForm']>>;
  saveModule: (module: ServiceModule) => Promise<void>;
  toggleModule: (module: ServiceModule) => Promise<void>;
  createModule: () => Promise<void>;
  removeModule: (module: ServiceModule) => Promise<void>;
  changePassword: () => Promise<void>;
  createUser: () => Promise<void>;
  saveUser: (user: AdminUser) => Promise<void>;
  resetPassword: (user: AdminUser) => Promise<void>;
  saveGroup: () => Promise<void>;
  saveResourceGrant: () => Promise<void>;
  removeResourceGrant: (grant: ResourceGrant) => Promise<void>;
  changeMembership: (action: 'add' | 'remove') => Promise<void>;
  createTaxonomy: (kind: 'category' | 'tag') => Promise<void>;
  saveCategory: (category: Category) => Promise<void>;
  saveTag: (tag: Tag) => Promise<void>;
  purgeSessionMetadata: () => Promise<void>;
  runSearch: () => Promise<void>;
  runBackup: () => Promise<void>;
  runValidate: (id: number) => Promise<void>;
  runRestoreDryRun: (id: number) => Promise<void>;
};

const AdminConsoleContext = createContext<AdminConsoleContextValue | null>(null);

export function useAdminConsoleData() {
  const context = useContext(AdminConsoleContext);
  if (!context) throw new Error('useAdminConsoleData must be used inside AdminConsoleTabs');
  return context;
}

const tabs = [
  { key: 'modules', label: '모듈' },
  { key: 'users', label: '사용자' },
  { key: 'rbac', label: 'RBAC' },
  { key: 'sessions', label: '세션' },
  { key: 'system', label: '시스템' },
  { key: 'taxonomy', label: '분류' },
  { key: 'search', label: '검색' },
  { key: 'backups', label: '백업' },
] as const;

type TabKey = (typeof tabs)[number]['key'];

export function AdminConsoleTabs() {
  const [activeTab, setActiveTab] = useState<TabKey>('modules');
  const [state, setState] = useState<PanelState>(initialState);
  const [moduleDrafts, setModuleDrafts] = useState<Record<number, ModuleDraft>>({});
  const [userDrafts, setUserDrafts] = useState<Record<number, UserDraft>>({});
  const [categoryDrafts, setCategoryDrafts] = useState<Record<number, TaxonomyDraft>>({});
  const [tagDrafts, setTagDrafts] = useState<Record<number, TaxonomyDraft>>({});
  const [moduleForm, setModuleForm] = useState({ key: '', title: '', section: 'Development', status: 'development', href: '', description: '', sort_order: 0, is_external: false, visibility: 'admin' });
  const [userForm, setUserForm] = useState({ username: '', password: '', email: '', role: 'user', is_active: true });
  const [groupForm, setGroupForm] = useState({ key: '', name: '', description: '', is_active: true, permissions_csv: '' });
  const [grantForm, setGrantForm] = useState({ subject_type: 'user' as 'user' | 'group', subject_id: '', resource_type: 'collection', resource_id: 'nsa', permission_key: 'collections.nsa.read' });
  const [membershipForm, setMembershipForm] = useState({ user_id: '', group_id: '' });
  const [categoryForm, setCategoryForm] = useState({ name: '', description: '', sort_order: 0, is_active: true });
  const [tagForm, setTagForm] = useState({ name: '', sort_order: 0, is_active: true });
  const [searchForm, setSearchForm] = useState({ q: '', includeNsa: false });
  const [passwordForm, setPasswordForm] = useState({ current: '', next: '', confirm: '' });

  async function refresh() {
    setState((current) => ({ ...current, busy: current.busy ?? 'refresh' }));
    try {
      const [summary, users, connectedUsers, permissions, groups, rbacMatrix, resourceGrants, audits, modules, health, configHealth, backups, categories, tags, ai] = await Promise.all([
        fetchAdminSummary(), fetchAdminUsers(), fetchConnectedUsers(), fetchAdminPermissions(), fetchAdminGroups(), fetchRbacMatrix(), listResourceGrants(), fetchAuditEvents(), fetchServiceModulesAdmin(), fetchAssetHealth(), fetchConfigHealth(), fetchBackups(), fetchCategories(), fetchTags(), fetchAdminAiStatus(),
      ]);
      setState((current) => ({ ...current, summary, users, connectedUsers, permissions, groups, rbacMatrix, resourceGrants, audits, modules, health, configHealth, backups, categories, tags, ai, error: undefined }));
      setModuleDrafts(Object.fromEntries(modules.map((module) => [module.id, moduleToDraft(module)])));
      setUserDrafts(Object.fromEntries(users.map((user) => [user.id, userToDraft(user)])));
      setCategoryDrafts(Object.fromEntries(categories.map((category) => [category.id, categoryToDraft(category)])));
      setTagDrafts(Object.fromEntries(tags.map((tag) => [tag.id, tagToDraft(tag)])));
    } catch (error) {
      setState((current) => ({ ...current, error: error instanceof Error ? error.message : '관리자 정보를 불러오지 못했습니다.' }));
    } finally {
      setState((current) => ({ ...current, busy: current.busy === 'refresh' ? undefined : current.busy }));
    }
  }

  useEffect(() => { void refresh(); }, []);

  async function runBusy(label: string, action: () => Promise<void>) {
    setState((current) => ({ ...current, busy: label, message: undefined, error: undefined }));
    try {
      await action();
      await refresh();
    } finally {
      setState((current) => ({ ...current, busy: undefined }));
    }
  }

  async function saveModule(module: ServiceModule) {
    const draft = moduleDrafts[module.id] ?? moduleToDraft(module);
    await runBusy(`module-${module.id}`, async () => { await updateServiceModule(module.id, draft, getCsrfCookie()); setState((current) => ({ ...current, message: `${draft.title} 모듈을 저장했습니다.` })); });
  }
  async function toggleModule(module: ServiceModule) {
    const draft = moduleDrafts[module.id] ?? moduleToDraft(module);
    await runBusy(`module-${module.id}`, async () => { await updateServiceModule(module.id, { is_enabled: !draft.is_enabled }, getCsrfCookie()); setState((current) => ({ ...current, message: `${module.title} 모듈 상태를 변경했습니다.` })); });
  }
  async function createModule() {
    if (!moduleForm.key.trim() || !moduleForm.title.trim()) return;
    await runBusy('module-create', async () => { await createServiceModule({ ...moduleForm, description: moduleForm.description || null }, getCsrfCookie()); setModuleForm({ key: '', title: '', section: 'Development', status: 'development', href: '', description: '', sort_order: 0, is_external: false, visibility: 'admin' }); setState((current) => ({ ...current, message: '대시보드 모듈을 추가했습니다.' })); });
  }
  async function removeModule(module: ServiceModule) {
    if (typeof window !== 'undefined' && !window.confirm(`${module.key} 모듈을 삭제할까요?`)) return;
    await runBusy(`module-${module.id}`, async () => { await deleteServiceModule(module.id, getCsrfCookie()); setState((current) => ({ ...current, message: `${module.title} 모듈을 삭제했습니다.` })); });
  }
  async function changePassword() {
    if (!passwordForm.current || !passwordForm.next) return;
    if (passwordForm.next !== passwordForm.confirm) { setState((current) => ({ ...current, error: '새 비밀번호와 확인 값이 일치하지 않습니다.' })); return; }
    await runBusy('password-change', async () => { await changeOwnPassword(passwordForm.current, passwordForm.next, getCsrfCookie()); setPasswordForm({ current: '', next: '', confirm: '' }); setState((current) => ({ ...current, message: '관리자 비밀번호를 변경했습니다.' })); });
  }
  async function createUser() {
    if (!userForm.username.trim() || !userForm.password.trim()) return;
    await runBusy('user-create', async () => { await createAdminUser({ ...userForm, email: userForm.email || null }, getCsrfCookie()); setUserForm({ username: '', password: '', email: '', role: 'user', is_active: true }); setState((current) => ({ ...current, message: '사용자를 생성했습니다.' })); });
  }
  async function saveUser(user: AdminUser) {
    const draft = userDrafts[user.id] ?? userToDraft(user);
    await runBusy(`user-${user.id}`, async () => { await updateAdminUser(user.id, { email: draft.email || null, role: draft.role, is_active: draft.is_active, permissions: parseCsv(draft.permissions_csv) }, getCsrfCookie()); setState((current) => ({ ...current, message: `${user.username} 사용자를 저장했습니다.` })); });
  }
  async function resetPassword(user: AdminUser) {
    const temporaryPassword = window.prompt(`${user.username} 임시 비밀번호를 입력하세요.`);
    if (!temporaryPassword) return;
    await runBusy(`user-reset-${user.id}`, async () => { await resetAdminUserPassword(user.id, temporaryPassword, getCsrfCookie()); setState((current) => ({ ...current, message: `${user.username} 비밀번호를 재설정했습니다.` })); });
  }
  async function saveGroup() {
    if (!groupForm.key.trim() || !groupForm.name.trim()) return;
    await runBusy('group-save', async () => { await upsertAdminGroup({ ...groupForm, permissions: parseCsv(groupForm.permissions_csv) }, getCsrfCookie()); setGroupForm({ key: '', name: '', description: '', is_active: true, permissions_csv: '' }); setState((current) => ({ ...current, message: '그룹/RBAC 설정을 저장했습니다.' })); });
  }
  async function saveResourceGrant() {
    const subjectId = Number(grantForm.subject_id);
    if (!subjectId || !grantForm.resource_type.trim() || !grantForm.resource_id.trim() || !grantForm.permission_key.trim()) return;
    await runBusy('resource-grant-save', async () => { await createResourceGrant({ subject_type: grantForm.subject_type, subject_id: subjectId, resource_type: grantForm.resource_type, resource_id: grantForm.resource_id, permission_key: grantForm.permission_key }, getCsrfCookie()); setState((current) => ({ ...current, message: '리소스 권한을 부여했습니다.' })); });
  }
  async function removeResourceGrant(grant: ResourceGrant) {
    await runBusy(`resource-grant-${grant.id}`, async () => { await deleteResourceGrant(grant.id, getCsrfCookie()); setState((current) => ({ ...current, message: '리소스 권한을 삭제했습니다.' })); });
  }
  async function changeMembership(action: 'add' | 'remove') {
    const userId = Number(membershipForm.user_id);
    const groupId = Number(membershipForm.group_id);
    if (!userId || !groupId) return;
    await runBusy(`membership-${action}`, async () => { if (action === 'add') await addUserGroup(userId, groupId, getCsrfCookie()); else await removeUserGroup(userId, groupId, getCsrfCookie()); setState((current) => ({ ...current, message: action === 'add' ? '그룹에 사용자를 추가했습니다.' : '그룹에서 사용자를 제거했습니다.' })); });
  }
  async function createTaxonomy(kind: 'category' | 'tag') {
    await runBusy(`${kind}-create`, async () => { if (kind === 'category') { if (!categoryForm.name.trim()) return; await createCategory(categoryForm, getCsrfCookie()); setCategoryForm({ name: '', description: '', sort_order: 0, is_active: true }); } else { if (!tagForm.name.trim()) return; await createTag(tagForm, getCsrfCookie()); setTagForm({ name: '', sort_order: 0, is_active: true }); } setState((current) => ({ ...current, message: '카테고리/태그를 생성했습니다.' })); });
  }
  async function saveCategory(category: Category) {
    const draft = categoryDrafts[category.id] ?? categoryToDraft(category);
    await runBusy(`category-${category.id}`, async () => { await updateCategory(category.id, draft, getCsrfCookie()); setState((current) => ({ ...current, message: `${category.name} 카테고리를 저장했습니다.` })); });
  }
  async function saveTag(tag: Tag) {
    const draft = tagDrafts[tag.id] ?? tagToDraft(tag);
    await runBusy(`tag-${tag.id}`, async () => { await updateTag(tag.id, draft, getCsrfCookie()); setState((current) => ({ ...current, message: `${tag.name} 태그를 저장했습니다.` })); });
  }
  async function purgeSessionMetadata() {
    await runBusy('sessions-purge', async () => { const result = await purgeSessions(getCsrfCookie()); setState((current) => ({ ...current, message: `세션/로그 정리 완료: 로그인 ${result.login_events_deleted}건 · 세션 ${result.session_activity_deleted}건` })); });
  }
  async function runSearch() {
    if (searchForm.q.trim().length < 2) return;
    await runBusy('search', async () => { const payload = await fetchUnifiedSearch(searchForm.q, searchForm.includeNsa); setState((current) => ({ ...current, searchResults: payload.results, message: `통합 검색 결과 ${payload.results.length}건` })); });
  }
  async function runBackup() {
    await runBusy('backup', async () => { await createBackup(getCsrfCookie()); setState((current) => ({ ...current, message: '백업을 생성했습니다.' })); });
  }
  async function runValidate(id: number) {
    await runBusy(`backup-${id}`, async () => { const result = await validateBackup(id, getCsrfCookie()); setState((current) => ({ ...current, message: result.valid ? '백업 검증 성공' : `백업 검증 실패: ${result.issues.join(', ')}` })); });
  }
  async function runRestoreDryRun(id: number) {
    await runBusy(`restore-${id}`, async () => { const result = await dryRunRestoreBackup(id, getCsrfCookie()); setState((current) => ({ ...current, message: result.compatible ? `복원 점검 성공: ${result.would_restore.join(', ')}` : `복원 점검 실패: ${result.issues.join(', ')}` })); });
  }

  const context = useMemo<AdminConsoleContextValue>(() => ({ state, refresh, moduleDrafts, setModuleDrafts, userDrafts, setUserDrafts, categoryDrafts, setCategoryDrafts, tagDrafts, setTagDrafts, moduleForm, setModuleForm, userForm, setUserForm, groupForm, setGroupForm, grantForm, setGrantForm, membershipForm, setMembershipForm, categoryForm, setCategoryForm, tagForm, setTagForm, searchForm, setSearchForm, passwordForm, setPasswordForm, saveModule, toggleModule, createModule, removeModule, changePassword, createUser, saveUser, resetPassword, saveGroup, saveResourceGrant, removeResourceGrant, changeMembership, createTaxonomy, saveCategory, saveTag, purgeSessionMetadata, runSearch, runBackup, runValidate, runRestoreDryRun }), [state, moduleDrafts, userDrafts, categoryDrafts, tagDrafts, moduleForm, userForm, groupForm, grantForm, membershipForm, categoryForm, tagForm, searchForm, passwordForm]);

  function activateTab(tab: TabKey) {
    setActiveTab(tab);
    window.requestAnimationFrame(() => document.getElementById(`admin-tab-${tab}`)?.focus());
  }

  function handleTabKeyDown(event: React.KeyboardEvent<HTMLButtonElement>, currentTab: TabKey) {
    const currentIndex = tabs.findIndex((tab) => tab.key === currentTab);
    const lastIndex = tabs.length - 1;
    let nextIndex: number | undefined;
    if (event.key === 'ArrowRight') nextIndex = currentIndex === lastIndex ? 0 : currentIndex + 1;
    if (event.key === 'ArrowLeft') nextIndex = currentIndex === 0 ? lastIndex : currentIndex - 1;
    if (event.key === 'Home') nextIndex = 0;
    if (event.key === 'End') nextIndex = lastIndex;
    if (nextIndex === undefined) return;
    event.preventDefault();
    activateTab(tabs[nextIndex].key);
  }

  if (state.error) return <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700" role="alert">{state.error}</div>;

  return (
    <AdminConsoleContext.Provider value={context}>
      <div className="space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="text-sm text-slate-600">운영 콘솔은 DB, 자산, 권한, 감사, 백업 상태를 한 화면에 모읍니다.</div>
          <div className="flex gap-2">
            <Link href="/admin/newsletters" className="rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-700">뉴스레터 관리</Link>
            <Link href="/admin/read-events" className="rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-700">읽음 현황</Link>
            <a href="/api/frontend/admin/read-events.csv" className="rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-700">읽음 CSV</a>
            <button type="button" onClick={() => void refresh()} className="rounded-md bg-slate-900 px-3 py-2 text-sm font-semibold text-white">새로고침</button>
          </div>
        </div>
        {state.message ? <div className="rounded-lg border border-blue-200 bg-blue-50 p-3 text-sm text-blue-700" role="status" aria-live="polite">{state.message}</div> : null}
        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm"><p className="text-xs font-semibold uppercase text-slate-500">Version / Mode</p><p className="mt-2 text-2xl font-semibold">v{state.summary?.app_version ?? '-'}</p><p className="text-sm text-slate-500">{state.summary?.app_env ?? '-'}</p></div>
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm"><p className="text-xs font-semibold uppercase text-slate-500">Newsletters</p><p className="mt-2 text-2xl font-semibold">{state.summary?.newsletter_total ?? 0}</p><p className="text-sm text-slate-500">최근: {state.summary?.latest_newsletter_title ?? '-'}</p></div>
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm"><p className="text-xs font-semibold uppercase text-slate-500">Assets</p><p className="mt-2 text-2xl font-semibold">{state.health?.ok ?? 0} OK</p><p className="text-sm text-slate-500">누락 {state.health?.missing ?? 0} · checksum {state.health?.checksum_mismatch ?? 0} · 설정 {state.health?.misconfig ?? 0}</p></div>
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm"><p className="text-xs font-semibold uppercase text-slate-500">AI 운영</p><p className="mt-2 text-2xl font-semibold">{String(state.summary?.ai_status?.status ?? '-')}</p><p className="text-sm text-slate-500">logs {state.ai?.request_logs_total ?? 0} · failures {state.ai?.request_failures ?? 0}</p></div>
        </section>
        <nav className="flex flex-wrap gap-2" aria-label="관리자 콘솔 탭" role="tablist">
          {tabs.map((tab) => {
            const selected = activeTab === tab.key;
            return (
              <button
                key={tab.key}
                id={`admin-tab-${tab.key}`}
                type="button"
                role="tab"
                aria-selected={selected}
                aria-current={selected ? 'page' : undefined}
                aria-controls={`admin-panel-${tab.key}`}
                tabIndex={selected ? 0 : -1}
                onClick={() => activateTab(tab.key)}
                onKeyDown={(event) => handleTabKeyDown(event, tab.key)}
                className={`rounded-md border px-3 py-2 text-sm font-semibold ${selected ? 'border-slate-900 bg-slate-900 text-white' : 'border-slate-300 bg-white text-slate-700'}`}
              >
                {tab.label}
              </button>
            );
          })}
        </nav>
        <div id={`admin-panel-${activeTab}`} role="tabpanel" aria-labelledby={`admin-tab-${activeTab}`}>
          {activeTab === 'modules' ? <AdminModulesSection /> : null}
          {activeTab === 'users' ? <AdminUsersSection /> : null}
          {activeTab === 'rbac' ? <AdminRbacSection /> : null}
          {activeTab === 'sessions' ? <AdminSessionsSection /> : null}
          {activeTab === 'system' ? <AdminSystemSection /> : null}
          {activeTab === 'taxonomy' ? <AdminTaxonomySection /> : null}
          {activeTab === 'search' ? <AdminSearchSection /> : null}
          {activeTab === 'backups' ? <AdminBackupsSection /> : null}
        </div>
      </div>
    </AdminConsoleContext.Provider>
  );
}
