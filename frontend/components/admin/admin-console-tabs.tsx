'use client';

import React, { createContext, useContext, useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';

import {
  activateAiProviderCompatible,
  addUserGroup,
  createAdminUser,
  createBackup,
  changeOwnPassword,
  createResourceGrant,
  createServiceModule,
  deleteAiProviderCredential,
  deleteResourceGrant,
  deleteServiceModule,
  createCategory,
  createTag,
  dryRunRestoreBackup,
  fetchAdminAiStatus,
  fetchAdminGroups,
  fetchAdminPermissions,
  fetchAdminOverview,
  fetchAdminUsers,
  fetchAiProviderConfig,
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
  getSafeAiProviderReasonMessage,
  reconcileAiProviderConfig,
  removeUserGroup,
  resetAdminUserPassword,
  selectAiProviderKind,
  stageAiProviderCompatibleConfig,
  testAiProviderStagedConfig,
  updateAdminUser,
  updateCategory,
  updateServiceModule,
  updateTag,
  upsertAdminGroup,
  validateBackup,
  listResourceGrants,
  purgeSessions,
  type AiProviderConfigResponse,
  type AiProviderKind,
} from '@/lib/api';
import { getCsrfCookie } from '@/lib/cookies';
import type {
  AdminGroup,
  AdminOverviewResponse,
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
import { AdminAuditSection } from './sections/admin-audit-section';
import { AdminOverviewSection } from './sections/admin-overview-section';
import { ConfirmProvider, useConfirm } from './widgets/confirm-dialog';
import { ToastStack, type AdminToast } from './widgets/toast-stack';

export type ModuleDraft = Pick<ServiceModule, 'title' | 'description' | 'href' | 'section' | 'status' | 'badge' | 'sort_order' | 'is_enabled' | 'is_external' | 'visibility'>;
export type UserDraft = Pick<AdminUser, 'display_name' | 'email' | 'role' | 'is_active'> & { permissions_csv: string };
export type TaxonomyDraft = { name: string; description?: string; sort_order: number; is_active: boolean };

type PanelState = {
  overview?: AdminOverviewResponse;
  users: AdminUser[];
  permissions: Permission[];
  groups: AdminGroup[];
  rbacMatrix: RbacMatrixUser[];
  resourceGrants: ResourceGrant[];
  audits: AuditEvent[];
  modules: ServiceModule[];
  connectedUsers?: ConnectedUsersResponse;
  connectedUsersError?: string;
  connectedUsersLoading?: boolean;
  health?: AssetHealthResponse;
  configHealth?: ConfigHealthResponse;
  backups: BackupRecord[];
  categories: Category[];
  tags: Tag[];
  ai?: AiAdminStatus;
  aiProvider?: AiProviderConfigResponse;
  searchResults: UnifiedSearchResult[];
  error?: string;
  toasts: AdminToast[];
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
  toasts: [],
  busy: 'initial-load',
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
  return { display_name: user.display_name ?? '', email: user.email ?? '', role: user.role, is_active: user.is_active, permissions_csv: user.permissions.join(', ') };
}

export function categoryToDraft(category: Category): TaxonomyDraft {
  return { name: category.name, description: category.description ?? '', sort_order: category.sort_order ?? 0, is_active: category.is_active ?? true };
}

export function tagToDraft(tag: Tag): TaxonomyDraft {
  return { name: tag.name, sort_order: tag.sort_order ?? 0, is_active: tag.is_active ?? true };
}

type AdminConsoleContextValue = {
  state: PanelState;
  refresh: (keys?: RefreshKey[]) => Promise<void>;
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
  userForm: { username: string; password: string; display_name: string; email: string; role: string; is_active: boolean };
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
  aiProviderForm: { kind: AiProviderKind; canonical_url: string; display_url: string; model: string; generation: string };
  setAiProviderForm: React.Dispatch<React.SetStateAction<AdminConsoleContextValue['aiProviderForm']>>;
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
  stageAiProviderConfig: (apiKey: string) => Promise<void>;
  testAiProviderCandidate: () => Promise<void>;
  activateAiProviderConfig: () => Promise<void>;
  selectAiProviderConfigKind: (kind: AiProviderKind) => Promise<void>;
  deleteAiProviderCredentials: () => Promise<void>;
  reconcileAiProviderState: () => Promise<void>;
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
  { key: 'audit', label: '감사' },
] as const;

type TabKey = (typeof tabs)[number]['key'];
type RefreshKey = 'overview' | 'users' | 'connectedUsers' | 'permissions' | 'groups' | 'rbacMatrix' | 'resourceGrants' | 'audits' | 'modules' | 'health' | 'configHealth' | 'backups' | 'categories' | 'tags' | 'ai' | 'aiProvider';
const allRefreshKeys: RefreshKey[] = ['overview', 'users', 'connectedUsers', 'permissions', 'groups', 'rbacMatrix', 'resourceGrants', 'audits', 'modules', 'health', 'configHealth', 'backups', 'categories', 'tags', 'ai', 'aiProvider'];

export function AdminConsoleTabs() {
  return (
    <ConfirmProvider>
      <AdminConsoleTabsContent />
    </ConfirmProvider>
  );
}


function AdminConsoleTabsContent() {
  const confirm = useConfirm();
  const [activeTab, setActiveTab] = useState<TabKey>('modules');
  const [state, setState] = useState<PanelState>(initialState);
  const [moduleDrafts, setModuleDrafts] = useState<Record<number, ModuleDraft>>({});
  const [userDrafts, setUserDrafts] = useState<Record<number, UserDraft>>({});
  const [categoryDrafts, setCategoryDrafts] = useState<Record<number, TaxonomyDraft>>({});
  const [tagDrafts, setTagDrafts] = useState<Record<number, TaxonomyDraft>>({});
  const [moduleForm, setModuleForm] = useState({ key: '', title: '', section: 'Development', status: 'development', href: '', description: '', sort_order: 0, is_external: false, visibility: 'admin' });
  const [userForm, setUserForm] = useState({ username: '', password: '', display_name: '', email: '', role: 'user', is_active: true });
  const [groupForm, setGroupForm] = useState({ key: '', name: '', description: '', is_active: true, permissions_csv: '' });
  const [grantForm, setGrantForm] = useState({ subject_type: 'user' as 'user' | 'group', subject_id: '', resource_type: 'collection', resource_id: 'nsa', permission_key: 'collections.nsa.read' });
  const [membershipForm, setMembershipForm] = useState({ user_id: '', group_id: '' });
  const [categoryForm, setCategoryForm] = useState({ name: '', description: '', sort_order: 0, is_active: true });
  const [tagForm, setTagForm] = useState({ name: '', sort_order: 0, is_active: true });
  const [searchForm, setSearchForm] = useState({ q: '', includeNsa: false });
  const [passwordForm, setPasswordForm] = useState({ current: '', next: '', confirm: '' });
  const [aiProviderForm, setAiProviderForm] = useState<{ kind: AiProviderKind; canonical_url: string; display_url: string; model: string; generation: string }>({ kind: 'openai_compatible', canonical_url: '', display_url: '', model: '', generation: '' });
  const toastIdRef = useRef(0);
  const connectedUsersRequestRef = useRef(0);

  function pushToast(type: AdminToast['type'], text: string) {
    toastIdRef.current += 1;
    const id = toastIdRef.current;
    setState((current) => ({
      ...current,
      toasts: [...current.toasts, { id, type, text }],
    }));
  }

  function dismissToast(id: number) {
    setState((current) => ({ ...current, toasts: current.toasts.filter((toast) => toast.id !== id) }));
  }

  async function refresh(keys: RefreshKey[] = allRefreshKeys) {
    setState((current) => ({
      ...current,
      busy: current.busy ?? 'refresh',
      ...(keys.includes('connectedUsers') ? { connectedUsersLoading: true } : {}),
    }));
    const connectedUsersRequestId = keys.includes('connectedUsers')
      ? ++connectedUsersRequestRef.current
      : undefined;
    const next: Partial<PanelState> = {
      error: undefined,
      ...(connectedUsersRequestId !== undefined ? { connectedUsersError: undefined } : {}),
    };
    const errors: string[] = [];
    let connectedUsersError: string | undefined;
    try {
      await Promise.all(keys.map(async (key) => {
        try {
          if (key === 'overview') next.overview = await fetchAdminOverview();
          if (key === 'users') next.users = await fetchAdminUsers();
          if (key === 'connectedUsers') next.connectedUsers = await fetchConnectedUsers();
          if (key === 'permissions') next.permissions = await fetchAdminPermissions();
          if (key === 'groups') next.groups = await fetchAdminGroups();
          if (key === 'rbacMatrix') next.rbacMatrix = await fetchRbacMatrix();
          if (key === 'resourceGrants') next.resourceGrants = await listResourceGrants();
          if (key === 'audits') next.audits = await fetchAuditEvents();
          if (key === 'modules') next.modules = await fetchServiceModulesAdmin();
          if (key === 'health') next.health = await fetchAssetHealth();
          if (key === 'configHealth') next.configHealth = await fetchConfigHealth();
          if (key === 'backups') next.backups = await fetchBackups();
          if (key === 'categories') next.categories = await fetchCategories();
          if (key === 'tags') next.tags = await fetchTags();
          if (key === 'ai') next.ai = await fetchAdminAiStatus();
          if (key === 'aiProvider') next.aiProvider = await fetchAiProviderConfig();
        } catch (error) {
          const text = error instanceof Error ? error.message : '관리자 정보를 불러오지 못했습니다.';
          if (key === 'connectedUsers') {
            connectedUsersError = text;
            next.connectedUsersError = text;
          } else {
            errors.push(text);
          }
        }
      }));
      if (
        connectedUsersRequestId !== undefined
        && connectedUsersRequestId !== connectedUsersRequestRef.current
      ) {
        delete next.connectedUsers;
        delete next.connectedUsersError;
        connectedUsersError = undefined;
      }
      if (
        connectedUsersRequestId !== undefined
        && connectedUsersRequestId === connectedUsersRequestRef.current
      ) {
        next.connectedUsersLoading = false;
      }
      next.error = errors[0];
      if (connectedUsersError) pushToast('error', connectedUsersError);
      if (next.error) pushToast('error', next.error);
      setState((current) => ({ ...current, ...next }));
      if (next.modules) setModuleDrafts(Object.fromEntries(next.modules.map((module) => [module.id, moduleToDraft(module)])));
      if (next.users) setUserDrafts(Object.fromEntries(next.users.map((user) => [user.id, userToDraft(user)])));
      if (next.categories) setCategoryDrafts(Object.fromEntries(next.categories.map((category) => [category.id, categoryToDraft(category)])));
      if (next.tags) setTagDrafts(Object.fromEntries(next.tags.map((tag) => [tag.id, tagToDraft(tag)])));
    } finally {
      setState((current) => ({ ...current, busy: current.busy === 'refresh' || current.busy === 'initial-load' ? undefined : current.busy }));
    }
  }

  useEffect(() => { void refresh(); }, []);

  async function runBusy(label: string, refreshKeys: RefreshKey[], action: () => Promise<string | void>) {
    setState((current) => ({ ...current, busy: label, error: undefined }));
    try {
      const message = await action();
      if (refreshKeys.length) await refresh(refreshKeys);
      if (message) pushToast('success', message);
    } catch (error) {
      pushToast('error', error instanceof Error ? error.message : '작업을 완료하지 못했습니다.');
    } finally {
      setState((current) => ({ ...current, busy: undefined }));
    }
  }

  async function saveModule(module: ServiceModule) {
    const draft = moduleDrafts[module.id] ?? moduleToDraft(module);
    await runBusy(`module-${module.id}`, ['modules', 'overview', 'audits'], async () => { await updateServiceModule(module.id, draft, getCsrfCookie()); return `${draft.title} 모듈을 저장했습니다.`; });
  }
  async function toggleModule(module: ServiceModule) {
    const draft = moduleDrafts[module.id] ?? moduleToDraft(module);
    await runBusy(`module-${module.id}`, ['modules', 'overview', 'audits'], async () => { await updateServiceModule(module.id, { is_enabled: !draft.is_enabled }, getCsrfCookie()); return `${module.title} 모듈 상태를 변경했습니다.`; });
  }
  async function createModule() {
    if (!moduleForm.key.trim() || !moduleForm.title.trim()) return;
    await runBusy('module-create', ['modules', 'overview', 'audits'], async () => { await createServiceModule({ ...moduleForm, description: moduleForm.description || null }, getCsrfCookie()); setModuleForm({ key: '', title: '', section: 'Development', status: 'development', href: '', description: '', sort_order: 0, is_external: false, visibility: 'admin' }); return '대시보드 모듈을 추가했습니다.'; });
  }
  async function removeModule(module: ServiceModule) {
    const result = await confirm({ title: '모듈 삭제', message: `${module.key} 모듈을 삭제할까요?\n삭제 후 대시보드 노출 및 관리자 목록에서 제거됩니다.`, confirmLabel: '삭제', tone: 'danger' });
    if (!result.confirmed) return;
    await runBusy(`module-${module.id}`, ['modules', 'overview', 'audits'], async () => { await deleteServiceModule(module.id, getCsrfCookie()); return `${module.title} 모듈을 삭제했습니다.`; });
  }
  async function changePassword() {
    if (!passwordForm.current || !passwordForm.next) return;
    if (passwordForm.next !== passwordForm.confirm) { pushToast('error', '새 비밀번호와 확인 값이 일치하지 않습니다.'); return; }
    await runBusy('password-change', ['audits'], async () => { await changeOwnPassword(passwordForm.current, passwordForm.next, getCsrfCookie()); setPasswordForm({ current: '', next: '', confirm: '' }); return '관리자 비밀번호를 변경했습니다.'; });
  }
  async function createUser() {
    if (!userForm.username.trim() || !userForm.password.trim()) return;
    await runBusy('user-create', ['users', 'rbacMatrix', 'audits'], async () => { await createAdminUser({ ...userForm, display_name: userForm.display_name || null, email: userForm.email || null }, getCsrfCookie()); setUserForm({ username: '', password: '', display_name: '', email: '', role: 'user', is_active: true }); return '사용자를 생성했습니다.'; });
  }
  async function saveUser(user: AdminUser) {
    const draft = userDrafts[user.id] ?? userToDraft(user);
    await runBusy(`user-${user.id}`, ['users', 'rbacMatrix', 'audits'], async () => { await updateAdminUser(user.id, { display_name: draft.display_name || null, email: draft.email || null, role: draft.role, is_active: draft.is_active, permissions: parseCsv(draft.permissions_csv) }, getCsrfCookie()); return `${user.username} 사용자를 저장했습니다.`; });
  }
  async function resetPassword(user: AdminUser) {
    const result = await confirm({ title: '비밀번호 재설정', message: `${user.username} 사용자의 비밀번호를 임시 비밀번호로 재설정합니다.`, inputLabel: '임시 비밀번호', inputType: 'password', confirmLabel: '재설정', tone: 'danger' });
    if (!result.confirmed || !result.value) return;
    const temporaryPassword = result.value.trim();
    await runBusy(`user-reset-${user.id}`, ['users', 'audits'], async () => { await resetAdminUserPassword(user.id, temporaryPassword, getCsrfCookie()); return `${user.username} 비밀번호를 재설정했습니다.`; });
  }
  async function saveGroup() {
    if (!groupForm.key.trim() || !groupForm.name.trim()) return;
    await runBusy('group-save', ['groups', 'resourceGrants', 'rbacMatrix', 'users', 'audits'], async () => { await upsertAdminGroup({ ...groupForm, permissions: parseCsv(groupForm.permissions_csv) }, getCsrfCookie()); setGroupForm({ key: '', name: '', description: '', is_active: true, permissions_csv: '' }); return '그룹/RBAC 설정을 저장했습니다.'; });
  }
  async function saveResourceGrant() {
    const subjectId = Number(grantForm.subject_id);
    if (!subjectId || !grantForm.resource_type.trim() || !grantForm.resource_id.trim() || !grantForm.permission_key.trim()) return;
    await runBusy('resource-grant-save', ['groups', 'resourceGrants', 'rbacMatrix', 'users', 'audits'], async () => { await createResourceGrant({ subject_type: grantForm.subject_type, subject_id: subjectId, resource_type: grantForm.resource_type, resource_id: grantForm.resource_id, permission_key: grantForm.permission_key }, getCsrfCookie()); return '리소스 권한을 부여했습니다.'; });
  }
  async function removeResourceGrant(grant: ResourceGrant) {
    const result = await confirm({ title: '리소스 권한 삭제', message: `${grant.subject_type}:${grant.subject_id}의 ${grant.resource_type}/${grant.resource_id} 권한(${grant.permission_key})을 삭제할까요?\n해당 주체의 접근 권한이 즉시 줄어듭니다.`, confirmLabel: '삭제', tone: 'danger' });
    if (!result.confirmed) return;
    await runBusy(`resource-grant-${grant.id}`, ['groups', 'resourceGrants', 'rbacMatrix', 'users', 'audits'], async () => { await deleteResourceGrant(grant.id, getCsrfCookie()); return '리소스 권한을 삭제했습니다.'; });
  }
  async function changeMembership(action: 'add' | 'remove') {
    const userId = Number(membershipForm.user_id);
    const groupId = Number(membershipForm.group_id);
    if (!userId || !groupId) return;
    if (action === 'remove') {
      const result = await confirm({ title: '그룹 멤버십 제거', message: '이 사용자를 그룹에서 제거할까요?\n그룹 권한이 즉시 회수됩니다.', confirmLabel: '제거', tone: 'danger' });
      if (!result.confirmed) return;
    }
    await runBusy(`membership-${action}`, ['groups', 'resourceGrants', 'rbacMatrix', 'users', 'audits'], async () => { if (action === 'add') await addUserGroup(userId, groupId, getCsrfCookie()); else await removeUserGroup(userId, groupId, getCsrfCookie()); return action === 'add' ? '그룹에 사용자를 추가했습니다.' : '그룹에서 사용자를 제거했습니다.'; });
  }
  async function createTaxonomy(kind: 'category' | 'tag') {
    await runBusy(`${kind}-create`, ['categories', 'tags', 'audits'], async () => { if (kind === 'category') { if (!categoryForm.name.trim()) return; await createCategory(categoryForm, getCsrfCookie()); setCategoryForm({ name: '', description: '', sort_order: 0, is_active: true }); } else { if (!tagForm.name.trim()) return; await createTag(tagForm, getCsrfCookie()); setTagForm({ name: '', sort_order: 0, is_active: true }); } return '카테고리/태그를 생성했습니다.'; });
  }
  async function saveCategory(category: Category) {
    const draft = categoryDrafts[category.id] ?? categoryToDraft(category);
    await runBusy(`category-${category.id}`, ['categories', 'tags', 'audits'], async () => { await updateCategory(category.id, draft, getCsrfCookie()); return `${category.name} 카테고리를 저장했습니다.`; });
  }
  async function saveTag(tag: Tag) {
    const draft = tagDrafts[tag.id] ?? tagToDraft(tag);
    await runBusy(`tag-${tag.id}`, ['categories', 'tags', 'audits'], async () => { await updateTag(tag.id, draft, getCsrfCookie()); return `${tag.name} 태그를 저장했습니다.`; });
  }
  async function purgeSessionMetadata() {
    const result = await confirm({ title: '세션/로그 정리', message: '오래된 로그인 이벤트와 세션 활동 메타데이터를 정리할까요?\n보관 기준 밖의 세션/로그 집계가 삭제됩니다.', confirmLabel: '정리', tone: 'danger' });
    if (!result.confirmed) return;
    await runBusy('sessions-purge', ['connectedUsers', 'audits'], async () => { const payload = await purgeSessions(getCsrfCookie()); return `세션/로그 정리 완료: 로그인 ${payload.login_events_deleted}건 · 세션 ${payload.session_activity_deleted}건`; });
  }
  async function runSearch() {
    if (searchForm.q.trim().length < 2) return;
    await runBusy('search', [], async () => { const payload = await fetchUnifiedSearch(searchForm.q, searchForm.includeNsa); setState((current) => ({ ...current, searchResults: payload.results })); return `통합 검색 결과 ${payload.results.length}건`; });
  }
  async function runBackup() {
    await runBusy('backup', ['backups', 'overview', 'audits'], async () => { await createBackup(getCsrfCookie()); return '백업을 생성했습니다.'; });
  }
  async function runValidate(id: number) {
    await runBusy(`backup-${id}`, ['backups', 'overview', 'audits'], async () => { const result = await validateBackup(id, getCsrfCookie()); return result.valid ? '백업 검증 성공' : `백업 검증 실패: ${result.issues.join(', ')}`; });
  }
  async function runRestoreDryRun(id: number) {
    await runBusy(`restore-${id}`, ['backups', 'overview', 'audits'], async () => { const result = await dryRunRestoreBackup(id, getCsrfCookie()); return result.compatible ? `복원 점검 성공: ${result.would_restore.join(', ')}` : `복원 점검 실패: ${result.issues.join(', ')}`; });
  }
  async function stageAiProviderConfig(apiKey: string) {
    const configVersion = state.aiProvider?.config_version;
    if (configVersion === undefined) return;
    if (!aiProviderForm.canonical_url.trim() || !aiProviderForm.display_url.trim() || !aiProviderForm.model.trim() || !aiProviderForm.generation.trim() || !apiKey.trim()) {
      pushToast('error', 'Canonical URL, Display URL, 모델, 세대, API 키를 모두 입력하세요.');
      return;
    }
    setState((current) => ({ ...current, busy: 'ai-provider-stage', error: undefined }));
    try {
      await stageAiProviderCompatibleConfig({
        canonical_url: aiProviderForm.canonical_url.trim(),
        display_url: aiProviderForm.display_url.trim(),
        model: aiProviderForm.model.trim(),
        generation: aiProviderForm.generation.trim(),
        api_key: apiKey,
        expected_config_version: configVersion,
      }, getCsrfCookie());
      await refresh(['aiProvider']);
      pushToast('success', '설정을 저장했습니다. 이어서 저장 설정 테스트를 실행하세요.');
    } catch (error) {
      pushToast('error', error instanceof Error ? error.message : '설정 저장 요청을 완료하지 못했습니다.');
    } finally {
      setState((current) => ({ ...current, busy: undefined }));
    }
  }
  async function testAiProviderCandidate() {
    if (!aiProviderForm.canonical_url.trim() || !aiProviderForm.model.trim() || !aiProviderForm.generation.trim()) {
      pushToast('error', '테스트하려면 먼저 저장된 설정과 동일한 URL/모델/세대 값을 입력하세요.');
      return;
    }
    setState((current) => ({ ...current, busy: 'ai-provider-test', error: undefined }));
    try {
      const result = await testAiProviderStagedConfig({
        canonical_url: aiProviderForm.canonical_url.trim(),
        model: aiProviderForm.model.trim(),
        generation: aiProviderForm.generation.trim(),
      }, getCsrfCookie());
      await refresh(['aiProvider']);
      pushToast(result.success ? 'success' : 'error', getSafeAiProviderReasonMessage(result.reason_code));
    } catch (error) {
      pushToast('error', error instanceof Error ? error.message : '연동 테스트 요청을 완료하지 못했습니다.');
    } finally {
      setState((current) => ({ ...current, busy: undefined }));
    }
  }
  async function activateAiProviderConfig() {
    const configVersion = state.aiProvider?.config_version;
    if (configVersion === undefined) return;
    setState((current) => ({ ...current, busy: 'ai-provider-activate', error: undefined }));
    try {
      await activateAiProviderCompatible(configVersion, getCsrfCookie());
      await refresh(['aiProvider']);
      pushToast('success', '활성화 확인을 완료했습니다.');
    } catch (error) {
      pushToast('error', error instanceof Error ? error.message : '활성화 요청을 완료하지 못했습니다.');
    } finally {
      setState((current) => ({ ...current, busy: undefined }));
    }
  }
  async function selectAiProviderConfigKind(kind: AiProviderKind) {
    const configVersion = state.aiProvider?.config_version;
    if (configVersion === undefined) return;
    setState((current) => ({ ...current, busy: 'ai-provider-selection', error: undefined }));
    try {
      await selectAiProviderKind(kind, configVersion, getCsrfCookie());
      await refresh(['aiProvider']);
      pushToast('success', `제공자를 ${kind === 'ollama' ? 'Ollama' : 'OpenAI 호환'}(으)로 전환했습니다.`);
    } catch (error) {
      pushToast('error', error instanceof Error ? error.message : '제공자 전환 요청을 완료하지 못했습니다.');
    } finally {
      setState((current) => ({ ...current, busy: undefined }));
    }
  }
  async function deleteAiProviderCredentials() {
    const configVersion = state.aiProvider?.config_version;
    if (configVersion === undefined) return;
    const result = await confirm({ title: 'AI 제공자 자격 증명 삭제', message: 'OpenAI 호환 자격 증명을 삭제할까요?\n삭제 후에는 다시 등록하고 테스트해야 합니다.', confirmLabel: '삭제', tone: 'danger' });
    if (!result.confirmed) return;
    setState((current) => ({ ...current, busy: 'ai-provider-delete', error: undefined }));
    try {
      await deleteAiProviderCredential(configVersion, getCsrfCookie());
      await refresh(['aiProvider']);
      pushToast('success', '자격 증명 삭제 완료');
    } catch (error) {
      pushToast('error', error instanceof Error ? error.message : '자격 증명 삭제 요청을 완료하지 못했습니다.');
    } finally {
      setState((current) => ({ ...current, busy: undefined }));
    }
  }
  async function reconcileAiProviderState() {
    setState((current) => ({ ...current, busy: 'ai-provider-reconcile', error: undefined }));
    try {
      const result = await reconcileAiProviderConfig(getCsrfCookie());
      await refresh(['aiProvider']);
      pushToast(
        result.reconciled ? 'success' : 'error',
        result.reconciled ? '정합성 점검 완료: 일치' : '정합성 점검: 불일치가 감지되어 재보정했습니다',
      );
    } catch (error) {
      pushToast('error', error instanceof Error ? error.message : '정합성 점검 요청을 완료하지 못했습니다.');
    } finally {
      setState((current) => ({ ...current, busy: undefined }));
    }
  }

  const context = useMemo<AdminConsoleContextValue>(() => ({ state, refresh, moduleDrafts, setModuleDrafts, userDrafts, setUserDrafts, categoryDrafts, setCategoryDrafts, tagDrafts, setTagDrafts, moduleForm, setModuleForm, userForm, setUserForm, groupForm, setGroupForm, grantForm, setGrantForm, membershipForm, setMembershipForm, categoryForm, setCategoryForm, tagForm, setTagForm, searchForm, setSearchForm, passwordForm, setPasswordForm, aiProviderForm, setAiProviderForm, saveModule, toggleModule, createModule, removeModule, changePassword, createUser, saveUser, resetPassword, saveGroup, saveResourceGrant, removeResourceGrant, changeMembership, createTaxonomy, saveCategory, saveTag, purgeSessionMetadata, runSearch, runBackup, runValidate, runRestoreDryRun, stageAiProviderConfig, testAiProviderCandidate, activateAiProviderConfig, selectAiProviderConfigKind, deleteAiProviderCredentials, reconcileAiProviderState }), [state, moduleDrafts, userDrafts, categoryDrafts, tagDrafts, moduleForm, userForm, groupForm, grantForm, membershipForm, categoryForm, tagForm, searchForm, passwordForm, aiProviderForm]);

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
  useEffect(() => {
    function isEditableTarget(target: EventTarget | Element | null) {
      if (!(target instanceof HTMLElement)) return false;
      return ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName) || target.isContentEditable;
    }

    function handleNumberShortcut(event: KeyboardEvent) {
      if (event.ctrlKey || event.metaKey || event.altKey) return;
      if (!/^[1-9]$/.test(event.key)) return;
      if (isEditableTarget(event.target) || isEditableTarget(document.activeElement)) return;
      const tab = tabs[Number(event.key) - 1];
      if (!tab) return;
      event.preventDefault();
      activateTab(tab.key);
    }

    window.addEventListener('keydown', handleNumberShortcut);
    return () => window.removeEventListener('keydown', handleNumberShortcut);
  }, []);




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
        {state.error ? (
          <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700" role="alert">
            {state.error}
          </div>
        ) : null}
        <details className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700">
          <summary className="cursor-pointer font-semibold text-slate-900">콘솔 사용 도움말</summary>
          <ul className="mt-3 grid gap-1 md:grid-cols-2">
            <li><span className="font-semibold">모듈</span>: 대시보드 모듈 노출과 정렬을 관리합니다.</li>
            <li><span className="font-semibold">사용자</span>: 계정 상태와 직접 권한을 점검합니다.</li>
            <li><span className="font-semibold">RBAC</span>: 그룹, 멤버십, 리소스 권한을 조정합니다.</li>
            <li><span className="font-semibold">세션</span>: 접속자와 로그인 활동을 확인합니다.</li>
            <li><span className="font-semibold">시스템</span>: DB, 자산, AI 상태와 비밀번호를 점검합니다.</li>
            <li><span className="font-semibold">분류</span>: 카테고리와 태그 기준을 관리합니다.</li>
            <li><span className="font-semibold">검색</span>: 통합 검색과 AI 운영 결과를 확인합니다.</li>
            <li><span className="font-semibold">백업</span>: 백업 생성, 검증, 복원 점검을 실행합니다.</li>
            <li><span className="font-semibold">감사</span>: 운영 이벤트와 CSV 내보내기를 확인합니다.</li>
          </ul>
          <p className="mt-3 text-xs text-slate-500">입력 필드가 아닌 곳에서는 숫자 키 1~9로 탭을 바로 전환할 수 있습니다.</p>
        </details>
        <ToastStack toasts={state.toasts} onDismiss={dismissToast} />
        <AdminOverviewSection />
        {state.busy === 'initial-load' ? null : (
          <>
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
          {activeTab === 'audit' ? <AdminAuditSection /> : null}
        </div>
          </>
        )}
      </div>
    </AdminConsoleContext.Provider>
  );
}
