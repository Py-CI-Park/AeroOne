import React from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { AdminConsoleTabs } from '@/components/admin/admin-console-tabs';
import { AdminHomeConsole } from '@/components/admin/admin-home-console';
import * as api from '@/lib/api';

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return {
    ...actual,
    fetchAdminOverview: vi.fn(),
    fetchAdminUsers: vi.fn(),
    fetchConnectedUsers: vi.fn(),
    fetchAdminPermissions: vi.fn(),
    fetchAdminGroups: vi.fn(),
    fetchRbacMatrix: vi.fn(),
    listResourceGrants: vi.fn(),
    fetchAuditEvents: vi.fn(),
    fetchServiceModulesAdmin: vi.fn(),
    createServiceModule: vi.fn(),
    updateServiceModule: vi.fn(),
    deleteServiceModule: vi.fn(),
    createResourceGrant: vi.fn(),
    addUserGroup: vi.fn(),
    removeUserGroup: vi.fn(),
    deleteResourceGrant: vi.fn(),
    purgeSessions: vi.fn(),
    fetchAssetHealth: vi.fn(),
    fetchConfigHealth: vi.fn(),
    fetchBackups: vi.fn(),
    fetchCategories: vi.fn(),
    fetchTags: vi.fn(),
    fetchAdminAiStatus: vi.fn(),
    fetchAiProviderConfig: vi.fn(),
    stageAiProviderCompatibleConfig: vi.fn(),
    testAiProviderStagedConfig: vi.fn(),
    activateAiProviderCompatible: vi.fn(),
    selectAiProviderKind: vi.fn(),
    deleteAiProviderCredential: vi.fn(),
    reconcileAiProviderConfig: vi.fn(),
    fetchLlmConnections: vi.fn().mockResolvedValue([]),
  };
});

const overviewFixture = {
  generated_at: '2026-07-05T00:00:00Z',
  anchor: '2026-06-28T00:00:00Z',
  users: { total: 2, active: 2, inactive: 0, roles: { admin: 1, user: 1, pending: 0 }, created: { current: 1, prior: 0, delta: 1 } },
  logins: { success: { current: 3, prior: 2, delta: 1 }, failure: { current: 0, prior: 1, delta: -1 }, logout: { current: 2, prior: 1, delta: 1 } },
  ai: { total: { current: 5, prior: 4, delta: 1 }, failure: { current: 0, prior: 0, delta: 0 } },
  sessions: { active_session_count: 1, active_user_count: 1, active_count: 1 },
  modules: { total: 2, buckets: { unavailable: [], coming: [], development: [], active: [{ key: 'ov-dashboard', label: 'Overview Dashboard' }] } },
  system: { app_version: '1.11.0', app_env: 'test', database_kind: 'sqlite', newsletter_count: 1, asset_health: { ok: 1, missing: 0, checksum_mismatch: 0, misconfig: 0 }, read_summary: { rows: 1, total_reads: 3 } },
  recent_audit: [{ id: 41, action: 'overview.audit.sample', target_type: 'backup', status: 'success', created_at: '2026-07-05T00:00:00Z' }],
};


const aiProviderConfigFixture = {
  selected_kind: 'ollama' as const,
  compatible_state: 'absent' as const,
  compatible_display_url: null,
  compatible_model: null,
  compatible_generation: null,
  compatible_test_proof_at: null,
  compatible_test_proof_model: null,
  config_version: 1,
  updated_at: '2026-07-05T00:00:00Z',
};

const aiProviderConfigWithCompatibleFixture = {
  selected_kind: 'openai_compatible' as const,
  compatible_state: 'verified' as const,
  compatible_display_url: 'https://api.example.com/***',
  compatible_model: 'gpt-4o-mini',
  compatible_generation: 'gen-3',
  compatible_test_proof_at: '2026-07-05T00:00:00Z',
  compatible_test_proof_model: 'gpt-4o-mini',
  config_version: 4,
  updated_at: '2026-07-05T00:00:00Z',
};

beforeEach(() => {
  vi.clearAllMocks();
});

function mockAdminData() {
  vi.mocked(api.fetchAdminOverview).mockResolvedValue(overviewFixture as never);
  vi.mocked(api.fetchAdminUsers).mockResolvedValue([{ id: 1, username: 'operator', email: 'op@example.com', role: 'admin', is_active: true, permissions: ['admin.read'] }, { id: 2, username: 'analyst', email: 'analyst@example.com', role: 'user', is_active: true, permissions: [] }] as never);
  vi.mocked(api.fetchConnectedUsers).mockResolvedValue({ active_sessions: [{ user_id: 1, username: 'operator', last_seen_at: '2026-07-05T00:00:00Z' }], active_count: 1, recent_login_events: [{ id: 9, user_id: 1, username: 'operator', status: 'success', created_at: '2026-07-05T00:00:00Z' }], login_failure_count: 0, read_tracking_summary: { rows: 1, total_reads: 3 } } as never);
  vi.mocked(api.fetchAdminPermissions).mockResolvedValue([{ key: 'admin.read', description: 'Admin read' }] as never);
  vi.mocked(api.fetchAdminGroups).mockResolvedValue([{ id: 2, key: 'ops', name: 'Operators', is_active: true, permissions: ['admin.read'] }] as never);
  vi.mocked(api.fetchRbacMatrix).mockResolvedValue([{ user_id: 1, username: 'operator', role: 'admin', role_permissions: [], direct_permissions: ['admin.read'], group_permissions: [], effective_permissions: [{ key: 'admin.read', sources: ['direct'] }], resource_grants: [] }] as never);
  vi.mocked(api.listResourceGrants).mockResolvedValue([{ id: 3, subject_type: 'group', subject_id: 2, resource_type: 'collection', resource_id: 'nsa', permission_key: 'collections.nsa.read' }] as never);
  vi.mocked(api.fetchAuditEvents).mockResolvedValue([{ id: 4, actor_username: 'operator', action: 'backup.create', target_type: 'backup', target_id: '1', status: 'success', created_at: '2026-07-05T00:00:00Z' }] as never);
  vi.mocked(api.fetchServiceModulesAdmin).mockResolvedValue([{ id: 5, key: 'dashboard', title: 'Dashboard', description: 'Main', href: '/', section: 'Core', status: 'active', badge: 'Live', sort_order: 2, is_enabled: true, is_external: false, visibility: 'admin' }, { id: 6, key: 'analytics', title: 'Analytics', description: 'Reports', href: '/analytics', section: 'Core', status: 'active', badge: 'New', sort_order: 1, is_enabled: true, is_external: false, visibility: 'admin' }] as never);
  vi.mocked(api.fetchAssetHealth).mockResolvedValue({ ok: 1, missing: 0, checksum_mismatch: 0, misconfig: 0, items: [] } as never);
  vi.mocked(api.fetchConfigHealth).mockResolvedValue({ roots: [{ kind: 'import', resolved_path: 'D:/_database/newsletter', exists: true, readable: true }] } as never);
  vi.mocked(api.fetchBackups).mockResolvedValue([{ id: 6, filename: 'backup.zip', sha256: '1234567890abcdef', file_size: 123, status: 'created', created_at: '2026-07-05T00:00:00Z' }] as never);
  vi.mocked(api.fetchCategories).mockResolvedValue([{ id: 7, name: '분류', description: '설명', sort_order: 0, is_active: true }] as never);
  vi.mocked(api.fetchTags).mockResolvedValue([{ id: 8, name: '태그', sort_order: 0, is_active: true }] as never);
  vi.mocked(api.fetchAdminAiStatus).mockResolvedValue({ status: { ok: true }, request_logs_total: 2, request_failures: 0 } as never);
  vi.mocked(api.fetchAiProviderConfig).mockResolvedValue(aiProviderConfigFixture as never);
  vi.mocked(api.createServiceModule).mockResolvedValue({ id: 10, key: 'new-module', title: 'New Module', description: null, href: '/new', section: 'Development', status: 'development', badge: null, sort_order: 0, is_enabled: true, is_external: false, visibility: 'admin' } as never);
  vi.mocked(api.updateServiceModule).mockResolvedValue({ id: 5, key: 'dashboard', title: 'Dashboard', description: 'Main', href: '/', section: 'Core', status: 'active', badge: 'Live', sort_order: 2, is_enabled: true, is_external: false, visibility: 'admin' } as never);
  vi.mocked(api.deleteServiceModule).mockResolvedValue(undefined as never);
  vi.mocked(api.createResourceGrant).mockResolvedValue({ id: 11, subject_type: 'user', subject_id: 1, resource_type: 'collection', resource_id: 'nsa', permission_key: 'collections.nsa.read' } as never);
  vi.mocked(api.addUserGroup).mockResolvedValue(undefined as never);
  vi.mocked(api.removeUserGroup).mockResolvedValue(undefined as never);
  vi.mocked(api.deleteResourceGrant).mockResolvedValue(undefined as never);
  vi.mocked(api.purgeSessions).mockResolvedValue({ login_events_deleted: 2, session_activity_deleted: 3 } as never);
}

// G008: 9개 평면 탭이 6개 그룹(overview/accounts/content/system/ai/audit) 으로 재편되어
// 대부분의 옛 항목(사용자/RBAC/세션 → 계정, 모듈/분류/검색 → 콘텐츠, 백업 → 시스템)이
// 같은 그룹 패널 안에서 함께 렌더된다. '의미 보존': 각 옛 섹션의 컨트롤이 여전히
// 존재/동작함을 확인하되, 그룹 탭을 먼저 클릭해 도달한다.
const parityMatrix = [
  {
    tab: '콘텐츠(모듈)',
    expected: ['대시보드 모듈 DB 관리', 'dashboard module row', 'module row save', 'module create'],
    assertPresent: async () => {
      fireEvent.click(await screen.findByRole('tab', { name: '콘텐츠' }));
      expect(await screen.findByText('대시보드 모듈 DB 관리')).toBeInTheDocument();
      expect(screen.getByText('dashboard')).toBeInTheDocument();
      expect(screen.getAllByRole('button', { name: '저장' }).length).toBeGreaterThan(0);
      expect(screen.getByRole('button', { name: '모듈 추가' })).toBeInTheDocument();
    },
  },
  {
    tab: '계정(사용자)',
    expected: ['사용자/RBAC', 'user-create', 'operator user row', 'user row save', 'password reset'],
    assertPresent: async () => {
      fireEvent.click(screen.getByRole('tab', { name: '계정' }));
      expect(await screen.findByText('사용자/RBAC')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '사용자 생성' })).toBeInTheDocument();
      expect(screen.getAllByText('operator').length).toBeGreaterThan(0);
      expect(screen.getAllByRole('button', { name: '저장' }).length).toBeGreaterThan(0);
      expect(screen.getAllByRole('button', { name: '비밀번호 재설정' }).length).toBeGreaterThan(0);
    },
  },
  {
    tab: '계정(RBAC)',
    expected: ['resource grant create', 'membership add/remove', 'grant delete', 'RBAC matrix'],
    assertPresent: async () => {
      fireEvent.click(screen.getByRole('tab', { name: '계정' }));
      expect(await screen.findByText('그룹/RBAC 권한')).toBeInTheDocument();
      expect(screen.getByText('RBAC 매트릭스 / 리소스 권한')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '리소스 권한 부여' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '그룹 추가' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '그룹 제거' })).toBeInTheDocument();
      expect(screen.getAllByText('operator').length).toBeGreaterThan(0);
      expect(screen.getAllByText(/collections\.nsa\.read/).length).toBeGreaterThan(0);
      expect(screen.getByRole('button', { name: '삭제' })).toBeInTheDocument();
    },
  },
  {
    tab: '계정(세션)',
    expected: ['purge button', 'active sessions', 'recent login events', 'read tracking'],
    assertPresent: async () => {
      fireEvent.click(screen.getByRole('tab', { name: '계정' }));
      expect(await screen.findByText('접속자/세션')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '오래된 세션/로그 정리' })).toBeInTheDocument();
      expect(screen.getByText('활성 세션')).toBeInTheDocument();
      expect(screen.getByText('최근 로그인/로그아웃 이벤트')).toBeInTheDocument();
      expect(screen.getByText('익명 읽음 추적')).toBeInTheDocument();
      expect(screen.getAllByText('operator').length).toBeGreaterThan(0);
    },
  },
  {
    tab: '시스템',
    expected: ['config-health', 'asset/config root', 'password change'],
    assertPresent: async () => {
      fireEvent.click(screen.getByRole('tab', { name: '시스템' }));
      expect(await screen.findByText('DB/자산 경로 상태')).toBeInTheDocument();
      expect(screen.getByText('config-health')).toBeInTheDocument();
      expect(screen.getByText('import')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '비밀번호 변경' })).toBeInTheDocument();
      expect(screen.getByLabelText('current password')).toBeInTheDocument();
    },
  },
  {
    tab: 'AI',
    expected: ['AI status', 'AI provider config'],
    assertPresent: async () => {
      fireEvent.click(screen.getByRole('tab', { name: 'AI' }));
      expect(await screen.findByText('AI 운영 상태')).toBeInTheDocument();
      expect(await screen.findByText('AI 제공자 설정')).toBeInTheDocument();
      expect(screen.getByText('provider-config')).toBeInTheDocument();
      expect(screen.getByLabelText('compatible canonical url')).toBeInTheDocument();
      expect(screen.getByLabelText('compatible api key')).toBeInTheDocument();
    },
  },
  {
    tab: '콘텐츠(분류)',
    expected: ['category create', 'tag create', 'category row save', 'tag row save'],
    assertPresent: async () => {
      fireEvent.click(screen.getByRole('tab', { name: '콘텐츠' }));
      expect(await screen.findByText('카테고리/태그 관리')).toBeInTheDocument();
      const taxonomySection = screen.getByText('카테고리/태그 관리').closest('section') as HTMLElement;
      expect(within(taxonomySection).getByRole('button', { name: '카테고리 생성' })).toBeInTheDocument();
      expect(within(taxonomySection).getByRole('button', { name: '태그 생성' })).toBeInTheDocument();
      expect(within(taxonomySection).getByDisplayValue('분류')).toBeInTheDocument();
      expect(within(taxonomySection).getByDisplayValue('태그')).toBeInTheDocument();
      expect(within(taxonomySection).getAllByRole('button', { name: '저장' })).toHaveLength(2);
    },
  },
  {
    tab: '콘텐츠(검색)',
    expected: ['search input', 'NSA toggle', 'search button'],
    assertPresent: async () => {
      fireEvent.click(screen.getByRole('tab', { name: '콘텐츠' }));
      expect(await screen.findByText('통합 검색 / AI 운영')).toBeInTheDocument();
      expect(screen.getByPlaceholderText('뉴스레터·Document·Civil 검색')).toBeInTheDocument();
      expect(screen.getByLabelText('NSA 포함')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '검색' })).toBeInTheDocument();
    },
  },
  {
    tab: '시스템(백업)',
    expected: ['create backup', 'backup list', 'validate', 'restore dry run'],
    assertPresent: async () => {
      fireEvent.click(screen.getByRole('tab', { name: '시스템' }));
      expect(await screen.findByRole('heading', { name: '백업' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '백업 생성' })).toBeInTheDocument();
      expect(screen.getByText('backup.zip')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '검증' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '복원 점검' })).toBeInTheDocument();
      expect(screen.getByText("감사 로그는 '감사' 탭에서 필터·CSV로 확인하세요.")).toBeInTheDocument();
    },
  },
  {
    tab: '감사',
    expected: ['audit log', 'CSV export', 'audit search', 'audit event'],
    assertPresent: async () => {
      fireEvent.click(screen.getByRole('tab', { name: '감사' }));
      expect(await screen.findByRole('heading', { name: '감사 로그' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '현재 결과 CSV 내보내기' })).toBeInTheDocument();
      expect(screen.getByLabelText('감사 검색')).toBeInTheDocument();
      expect(screen.getByText('backup.create')).toBeInTheDocument();
    },
  },
] as const;

test('admin console tabs preserve feature parity controls for every decomposed section', async () => {
  mockAdminData();
  render(<AdminConsoleTabs />);

  for (const row of parityMatrix) {
    await row.assertPresent();
  }
});

test('admin list UX filters, sorts, renders empty state, and exposes tab/toast accessibility', async () => {
  mockAdminData();
  render(<AdminConsoleTabs />);

  const contentTab = await screen.findByRole('tab', { name: '콘텐츠' });
  expect(screen.getByRole('tablist', { name: '관리자 콘솔 탭' })).toBeInTheDocument();
  fireEvent.click(contentTab);
  expect(contentTab).toHaveAttribute('aria-selected', 'true');
  expect(contentTab).toHaveAttribute('aria-current', 'page');
  expect(await screen.findByRole('tabpanel', { name: '콘텐츠' })).toBeInTheDocument();

  const analytics = await screen.findByText('analytics');
  const dashboard = screen.getByText('dashboard');
  expect(analytics.compareDocumentPosition(dashboard) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();

  fireEvent.change(screen.getByLabelText('모듈 정렬'), { target: { value: 'key-desc' } });
  expect(screen.getByText('dashboard').compareDocumentPosition(screen.getByText('analytics')) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();

  fireEvent.click(screen.getByRole('tab', { name: '계정' }));
  expect(await screen.findByText('사용자/RBAC')).toBeInTheDocument();
  const usersSection = screen.getByText('사용자/RBAC').closest('section') as HTMLElement;
  expect(within(usersSection).getByLabelText('사용자 검색')).toBeInTheDocument();
  fireEvent.change(within(usersSection).getByLabelText('사용자 검색'), { target: { value: 'analyst' } });
  expect(within(usersSection).getByText('analyst')).toBeInTheDocument();
  expect(within(usersSection).queryByText('operator')).not.toBeInTheDocument();
  expect(within(usersSection).getByText('결과 1 / 2건')).toBeInTheDocument();

  fireEvent.change(within(usersSection).getByLabelText('사용자 검색'), { target: { value: 'nomatch' } });
  expect(within(usersSection).getByText('검색 조건에 맞는 사용자가 없습니다.')).toBeInTheDocument();

  fireEvent.click(screen.getByRole('tab', { name: '콘텐츠' }));
  fireEvent.change(await screen.findByLabelText('new module key'), { target: { value: 'valid-module' } });
  fireEvent.change(screen.getByLabelText('new module title'), { target: { value: 'Valid Module' } });
  fireEvent.change(screen.getByLabelText('new module href'), { target: { value: '/valid' } });
  fireEvent.click(screen.getByRole('button', { name: '모듈 추가' }));
  expect(await screen.findByRole('status')).toHaveAttribute('aria-live', 'polite');
});
test('admin console number shortcuts switch tabs, skip focused inputs, and expose onboarding help', async () => {
  mockAdminData();
  render(<AdminConsoleTabs />);

  expect(await screen.findByText('사용자 통계')).toBeInTheDocument();
  expect(screen.getByText('콘솔 사용 도움말')).toBeInTheDocument();
  expect(screen.getByText(/전체 운영 지표 요약/)).toBeInTheDocument();
  expect(screen.getByText(/숫자 키 1~6/)).toBeInTheDocument();

  fireEvent.keyDown(window, { key: '2' });
  await waitFor(() => expect(screen.getByRole('tab', { name: '계정' })).toHaveAttribute('aria-selected', 'true'));
  expect(await screen.findByText('그룹/RBAC 권한')).toBeInTheDocument();

  const groupKey = screen.getByLabelText('group key');
  groupKey.focus();
  fireEvent.keyDown(window, { key: '6' });
  expect(screen.getByRole('tab', { name: '계정' })).toHaveAttribute('aria-selected', 'true');
  expect(screen.getByRole('tab', { name: '감사' })).toHaveAttribute('aria-selected', 'false');

  groupKey.blur();
  fireEvent.keyDown(window, { key: '6' });
  await waitFor(() => expect(screen.getByRole('tab', { name: '감사' })).toHaveAttribute('aria-selected', 'true'));
  expect(await screen.findByRole('heading', { name: '감사 로그' })).toBeInTheDocument();
});

test('AdminHomeConsole renders the tab shell and tab switching preserves parent state', async () => {
  mockAdminData();
  render(<AdminHomeConsole />);

  expect(await screen.findByText('운영 콘솔은 DB, 자산, 권한, 감사, 백업 상태를 한 화면에 모읍니다.')).toBeInTheDocument();
  const tablist = screen.getByRole('tablist', { name: '관리자 콘솔 탭' });
  expect(tablist).toBeInTheDocument();
  expect(within(tablist).getAllByRole('tab').map((tab) => tab.textContent)).toEqual(['개요', '계정', '콘텐츠', '시스템', 'AI', '감사']);

  fireEvent.click(screen.getByRole('tab', { name: '콘텐츠' }));
  const newModuleKey = await screen.findByLabelText('new module key');
  fireEvent.change(newModuleKey, { target: { value: 'qa-module' } });
  expect(newModuleKey).toHaveValue('qa-module');

  fireEvent.click(screen.getByRole('tab', { name: '계정' }));
  expect(await screen.findByText('사용자/RBAC')).toBeInTheDocument();

  fireEvent.click(screen.getByRole('tab', { name: '콘텐츠' }));
  expect(await screen.findByText('대시보드 모듈 DB 관리')).toBeInTheDocument();
  expect(screen.getByLabelText('new module key')).toHaveValue('qa-module');
});

test('module status and visibility controls expose only allowed select options', async () => {
  mockAdminData();
  render(<AdminConsoleTabs />);

  fireEvent.click(await screen.findByRole('tab', { name: '콘텐츠' }));
  expect(await screen.findByText('대시보드 모듈 DB 관리')).toBeInTheDocument();

  const statusOptions = within(screen.getByLabelText('new module status')).getAllByRole('option').map((option) => (option as HTMLOptionElement).value);
  expect(statusOptions).toEqual(['active', 'development', 'coming_soon', 'hidden']);

  const visibilityOptions = within(screen.getByLabelText('new module visibility')).getAllByRole('option').map((option) => (option as HTMLOptionElement).value);
  expect(visibilityOptions).toEqual(['public', 'admin']);

  const rowStatusOptions = within(screen.getByLabelText('dashboard status')).getAllByRole('option').map((option) => (option as HTMLOptionElement).value);
  expect(rowStatusOptions).toEqual(['active', 'development', 'coming_soon', 'hidden']);
});

test('module custom section path is explicit and validates non-empty custom input', async () => {
  mockAdminData();
  render(<AdminConsoleTabs />);

  fireEvent.click(await screen.findByRole('tab', { name: '콘텐츠' }));
  expect(await screen.findByText('대시보드 모듈 DB 관리')).toBeInTheDocument();

  const sectionSelect = screen.getByLabelText('new module section');
  expect(within(sectionSelect).getAllByRole('option').map((option) => (option as HTMLOptionElement).value)).toEqual(['Newsletter', 'Document', 'Development', '__custom__']);

  fireEvent.change(sectionSelect, { target: { value: '__custom__' } });
  expect(screen.getByLabelText('new module section custom')).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText('new module key'), { target: { value: 'custom-module' } });
  fireEvent.change(screen.getByLabelText('new module title'), { target: { value: 'Custom Module' } });
  fireEvent.change(screen.getByLabelText('new module href'), { target: { value: '/custom' } });
  fireEvent.click(screen.getByRole('button', { name: '모듈 추가' }));

  expect(await screen.findByText('section은 필수입니다.')).toBeInTheDocument();
  expect(api.createServiceModule).not.toHaveBeenCalled();
});

test('invalid module create is blocked with inline validation before calling create handler', async () => {
  mockAdminData();
  render(<AdminConsoleTabs />);

  fireEvent.click(await screen.findByRole('tab', { name: '콘텐츠' }));
  expect(await screen.findByText('대시보드 모듈 DB 관리')).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('new module title'), { target: { value: 'Missing Key Module' } });
  fireEvent.change(screen.getByLabelText('new module href'), { target: { value: '/missing-key' } });
  fireEvent.click(screen.getByRole('button', { name: '모듈 추가' }));

  expect(await screen.findByText('key는 필수입니다.')).toBeInTheDocument();
  expect(api.createServiceModule).not.toHaveBeenCalled();
});

test('valid module create still calls the shell create handler with the existing payload shape', async () => {
  mockAdminData();
  render(<AdminConsoleTabs />);

  fireEvent.click(await screen.findByRole('tab', { name: '콘텐츠' }));
  expect(await screen.findByText('대시보드 모듈 DB 관리')).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('new module key'), { target: { value: 'valid-module' } });
  fireEvent.change(screen.getByLabelText('new module title'), { target: { value: 'Valid Module' } });
  fireEvent.change(screen.getByLabelText('new module href'), { target: { value: '/valid' } });
  fireEvent.change(screen.getByLabelText('new module status'), { target: { value: 'active' } });
  fireEvent.change(screen.getByLabelText('new module visibility'), { target: { value: 'public' } });
  fireEvent.click(screen.getByRole('button', { name: '모듈 추가' }));

  await waitFor(() => expect(api.createServiceModule).toHaveBeenCalledTimes(1));
  expect(api.createServiceModule).toHaveBeenCalledWith(
    expect.objectContaining({
      key: 'valid-module',
      title: 'Valid Module',
      section: 'Development',
      status: 'active',
      href: '/valid',
      description: null,
      sort_order: 0,
      is_external: false,
      visibility: 'public',
    }),
    expect.any(String),
  );
});

test('destructive resource grant delete requires in-app confirm before calling the API', async () => {
  mockAdminData();
  render(<AdminConsoleTabs />);

  fireEvent.click(await screen.findByRole('tab', { name: '계정' }));
  expect(await screen.findByText('그룹/RBAC 권한')).toBeInTheDocument();

  vi.clearAllMocks();
  fireEvent.click(screen.getByRole('button', { name: '삭제' }));
  const dialog = await screen.findByRole('dialog', { name: '리소스 권한 삭제' });
  expect(dialog).toHaveTextContent('접근 권한이 즉시 줄어듭니다.');

  fireEvent.click(within(dialog).getByRole('button', { name: '취소' }));
  expect(api.deleteResourceGrant).not.toHaveBeenCalled();

  fireEvent.click(screen.getByRole('button', { name: '삭제' }));
  const confirmDialog = await screen.findByRole('dialog', { name: '리소스 권한 삭제' });
  fireEvent.click(within(confirmDialog).getByRole('button', { name: '삭제' }));

  await waitFor(() => expect(api.deleteResourceGrant).toHaveBeenCalledWith(3, expect.any(String)));
});

test('successful actions render a dismissible toast stack item', async () => {
  mockAdminData();
  render(<AdminConsoleTabs />);

  fireEvent.click(await screen.findByRole('tab', { name: '콘텐츠' }));
  expect(await screen.findByText('대시보드 모듈 DB 관리')).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('new module key'), { target: { value: 'toast-module' } });
  fireEvent.change(screen.getByLabelText('new module title'), { target: { value: 'Toast Module' } });
  fireEvent.change(screen.getByLabelText('new module href'), { target: { value: '/toast' } });
  fireEvent.click(screen.getByRole('button', { name: '모듈 추가' }));

  expect(await screen.findByRole('status')).toHaveTextContent('대시보드 모듈을 추가했습니다.');
  fireEvent.click(screen.getByRole('button', { name: '알림 닫기' }));
  await waitFor(() => expect(screen.queryByText('대시보드 모듈을 추가했습니다.')).not.toBeInTheDocument());
});

test('module create performs scoped refresh for modules, overview, and audits', async () => {
  mockAdminData();
  render(<AdminConsoleTabs />);

  fireEvent.click(await screen.findByRole('tab', { name: '콘텐츠' }));
  expect(await screen.findByText('대시보드 모듈 DB 관리')).toBeInTheDocument();
  vi.clearAllMocks();

  fireEvent.change(screen.getByLabelText('new module key'), { target: { value: 'scoped-module' } });
  fireEvent.change(screen.getByLabelText('new module title'), { target: { value: 'Scoped Module' } });
  fireEvent.change(screen.getByLabelText('new module href'), { target: { value: '/scoped' } });
  fireEvent.click(screen.getByRole('button', { name: '모듈 추가' }));

  await waitFor(() => expect(api.createServiceModule).toHaveBeenCalledTimes(1));
  await waitFor(() => expect(api.fetchServiceModulesAdmin).toHaveBeenCalledTimes(1));
  expect(api.fetchAdminOverview).toHaveBeenCalledTimes(1);
  expect(api.fetchAuditEvents).toHaveBeenCalledTimes(1);
  expect(api.fetchAdminUsers).not.toHaveBeenCalled();
  expect(api.fetchConnectedUsers).not.toHaveBeenCalled();
  expect(api.fetchBackups).not.toHaveBeenCalled();
  expect(api.fetchTags).not.toHaveBeenCalled();
});

test('membership remove requires confirm, cancel and Escape do not call API, confirm removes', async () => {
  mockAdminData();
  render(<AdminConsoleTabs />);

  fireEvent.click(await screen.findByRole('tab', { name: '계정' }));
  expect(await screen.findByText('그룹/RBAC 권한')).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('membership user'), { target: { value: '1' } });
  fireEvent.change(screen.getByLabelText('membership group'), { target: { value: '2' } });

  vi.clearAllMocks();
  fireEvent.click(screen.getByRole('button', { name: '그룹 제거' }));
  const cancelDialog = await screen.findByRole('dialog', { name: '그룹 멤버십 제거' });
  expect(cancelDialog).toHaveTextContent('이 사용자를 그룹에서 제거할까요?');
  fireEvent.click(within(cancelDialog).getByRole('button', { name: '취소' }));
  expect(api.removeUserGroup).not.toHaveBeenCalled();

  fireEvent.click(screen.getByRole('button', { name: '그룹 제거' }));
  expect(await screen.findByRole('dialog', { name: '그룹 멤버십 제거' })).toBeInTheDocument();
  fireEvent.keyDown(window, { key: 'Escape' });
  await waitFor(() => expect(screen.queryByRole('dialog', { name: '그룹 멤버십 제거' })).not.toBeInTheDocument());
  expect(api.removeUserGroup).not.toHaveBeenCalled();

  fireEvent.click(screen.getByRole('button', { name: '그룹 제거' }));
  const confirmDialog = await screen.findByRole('dialog', { name: '그룹 멤버십 제거' });
  fireEvent.click(within(confirmDialog).getByRole('button', { name: '제거' }));

  await waitFor(() => expect(api.removeUserGroup).toHaveBeenCalledWith(1, 2, expect.any(String)));
  expect(api.addUserGroup).not.toHaveBeenCalled();
});

test('resource grant save refreshes recent audits in its scoped refetch', async () => {
  mockAdminData();
  render(<AdminConsoleTabs />);

  fireEvent.click(await screen.findByRole('tab', { name: '계정' }));
  expect(await screen.findByText('그룹/RBAC 권한')).toBeInTheDocument();
  vi.clearAllMocks();

  fireEvent.change(screen.getByLabelText('grant subject type'), { target: { value: 'user' } });
  fireEvent.change(screen.getByLabelText('grant subject'), { target: { value: '1' } });
  fireEvent.change(screen.getByLabelText('grant resource type'), { target: { value: 'collection' } });
  fireEvent.change(screen.getByLabelText('grant resource id'), { target: { value: 'nsa' } });
  fireEvent.change(screen.getByLabelText('grant permission key'), { target: { value: 'collections.nsa.read' } });
  fireEvent.click(screen.getByRole('button', { name: '리소스 권한 부여' }));

  await waitFor(() => expect(api.createResourceGrant).toHaveBeenCalledTimes(1));
  await waitFor(() => expect(api.fetchAuditEvents).toHaveBeenCalledTimes(1));
  expect(api.listResourceGrants).toHaveBeenCalledTimes(1);
  expect(api.fetchRbacMatrix).toHaveBeenCalledTimes(1);
  expect(api.fetchAdminUsers).toHaveBeenCalledTimes(1);
});

test('destructive resource grant delete cancel paths include Escape before API confirmation', async () => {
  mockAdminData();
  render(<AdminConsoleTabs />);

  fireEvent.click(await screen.findByRole('tab', { name: '계정' }));
  expect(await screen.findByText('그룹/RBAC 권한')).toBeInTheDocument();

  vi.clearAllMocks();
  fireEvent.click(screen.getByRole('button', { name: '삭제' }));
  expect(await screen.findByRole('dialog', { name: '리소스 권한 삭제' })).toBeInTheDocument();

  fireEvent.keyDown(window, { key: 'Escape' });
  await waitFor(() => expect(screen.queryByRole('dialog', { name: '리소스 권한 삭제' })).not.toBeInTheDocument());
  expect(api.deleteResourceGrant).not.toHaveBeenCalled();

  fireEvent.click(screen.getByRole('button', { name: '삭제' }));
  const confirmDialog = await screen.findByRole('dialog', { name: '리소스 권한 삭제' });
  fireEvent.click(within(confirmDialog).getByRole('button', { name: '삭제' }));

  await waitFor(() => expect(api.deleteResourceGrant).toHaveBeenCalledWith(3, expect.any(String)));
});

test('session metadata purge requires confirm, cancel and Escape do not call API, confirm purges', async () => {
  mockAdminData();
  render(<AdminConsoleTabs />);

  fireEvent.click(await screen.findByRole('tab', { name: '계정' }));
  expect(await screen.findByText('접속자/세션')).toBeInTheDocument();

  vi.clearAllMocks();
  fireEvent.click(screen.getByRole('button', { name: '오래된 세션/로그 정리' }));
  const cancelDialog = await screen.findByRole('dialog', { name: '세션/로그 정리' });
  expect(cancelDialog).toHaveTextContent('보관 기준 밖의 세션/로그 집계가 삭제됩니다.');
  fireEvent.click(within(cancelDialog).getByRole('button', { name: '취소' }));
  expect(api.purgeSessions).not.toHaveBeenCalled();

  fireEvent.click(screen.getByRole('button', { name: '오래된 세션/로그 정리' }));
  expect(await screen.findByRole('dialog', { name: '세션/로그 정리' })).toBeInTheDocument();
  fireEvent.keyDown(window, { key: 'Escape' });
  await waitFor(() => expect(screen.queryByRole('dialog', { name: '세션/로그 정리' })).not.toBeInTheDocument());
  expect(api.purgeSessions).not.toHaveBeenCalled();

  fireEvent.click(screen.getByRole('button', { name: '오래된 세션/로그 정리' }));
  const confirmDialog = await screen.findByRole('dialog', { name: '세션/로그 정리' });
  fireEvent.click(within(confirmDialog).getByRole('button', { name: '정리' }));

  await waitFor(() => expect(api.purgeSessions).toHaveBeenCalledTimes(1));
});

test('toast stack exposes success status, error alert, manual dismiss, and auto dismiss', async () => {
  mockAdminData();
  render(<AdminConsoleTabs />);

  fireEvent.click(await screen.findByRole('tab', { name: '콘텐츠' }));
  expect(await screen.findByText('대시보드 모듈 DB 관리')).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('new module key'), { target: { value: 'toast-module' } });
  fireEvent.change(screen.getByLabelText('new module title'), { target: { value: 'Toast Module' } });
  fireEvent.change(screen.getByLabelText('new module href'), { target: { value: '/toast' } });
  fireEvent.click(screen.getByRole('button', { name: '모듈 추가' }));

  expect(await screen.findByRole('status')).toHaveTextContent('대시보드 모듈을 추가했습니다.');
  fireEvent.click(screen.getByRole('button', { name: '알림 닫기' }));
  await waitFor(() => expect(screen.queryByText('대시보드 모듈을 추가했습니다.')).not.toBeInTheDocument());

  vi.mocked(api.createServiceModule).mockRejectedValueOnce(new Error('boom create failed') as never);
  fireEvent.change(screen.getByLabelText('new module key'), { target: { value: 'error-module' } });
  fireEvent.change(screen.getByLabelText('new module title'), { target: { value: 'Error Module' } });
  fireEvent.change(screen.getByLabelText('new module href'), { target: { value: '/error' } });
  fireEvent.click(screen.getByRole('button', { name: '모듈 추가' }));

  expect(await screen.findByRole('alert')).toHaveTextContent('boom create failed');
  await waitFor(() => expect(screen.queryByText('boom create failed')).not.toBeInTheDocument(), { timeout: 4500 });
}, 10000);

test('session purge performs scoped refresh for connected users and audits and updates the affected session list', async () => {
  mockAdminData();
  render(<AdminConsoleTabs />);

  fireEvent.click(await screen.findByRole('tab', { name: '계정' }));
  expect(await screen.findByText('접속자/세션')).toBeInTheDocument();
  const sessionsSection = screen.getByText('접속자/세션').closest('section') as HTMLElement;
  expect(within(sessionsSection).getAllByText('operator').length).toBeGreaterThan(0);

  vi.clearAllMocks();
  vi.mocked(api.fetchConnectedUsers).mockResolvedValue({ active_sessions: [], active_count: 0, recent_login_events: [], login_failure_count: 0, read_tracking_summary: { rows: 0, total_reads: 0 } } as never);

  fireEvent.click(screen.getByRole('button', { name: '오래된 세션/로그 정리' }));
  const confirmDialog = await screen.findByRole('dialog', { name: '세션/로그 정리' });
  fireEvent.click(within(confirmDialog).getByRole('button', { name: '정리' }));

  await waitFor(() => expect(api.purgeSessions).toHaveBeenCalledTimes(1));
  await waitFor(() => expect(api.fetchConnectedUsers).toHaveBeenCalledTimes(1));
  expect(api.fetchAuditEvents).toHaveBeenCalledTimes(1);
  expect(api.fetchServiceModulesAdmin).not.toHaveBeenCalled();
  expect(api.fetchBackups).not.toHaveBeenCalled();
  expect(api.fetchAdminOverview).not.toHaveBeenCalled();
  expect(api.fetchAdminUsers).not.toHaveBeenCalled();
  expect(await screen.findByText('활성 로그인 세션 없음')).toBeInTheDocument();
  expect(within(sessionsSection).queryByText('operator')).not.toBeInTheDocument();
});

test('admin page keeps the server guard, sync AppShell, and client island import', () => {
  const pageSource = readFileSync(resolve(process.cwd(), 'app/admin/page.tsx'), 'utf8');
  const shellSource = readFileSync(resolve(process.cwd(), 'components/layout/app-shell.tsx'), 'utf8');

  expect(pageSource).toContain('requireAdminSession');
  expect(pageSource).toContain('<AdminHomeConsole />');
  expect(pageSource).toContain('<AppShell');
  expect(shellSource.startsWith("'use client'")).toBe(false);
  expect(shellSource.startsWith('"use client"')).toBe(false);
});

test('AI provider panel masks compatible config: only compatible_display_url renders, canonical URL/credential ref are never part of the safe DTO', async () => {
  mockAdminData();
  vi.mocked(api.fetchAiProviderConfig).mockResolvedValue(aiProviderConfigWithCompatibleFixture as never);
  render(<AdminConsoleTabs />);

  fireEvent.click(await screen.findByRole('tab', { name: 'AI' }));
  expect(await screen.findByText(aiProviderConfigWithCompatibleFixture.compatible_display_url)).toBeInTheDocument();
  expect(document.body.innerHTML).not.toContain('dpapi-ref-should-never-render');
  expect(document.body.innerHTML).not.toContain('internal-secret-upstream');
  expect(await screen.findByText('통과(최신)')).toBeInTheDocument();
});

test('API key field is an uncontrolled input with no value attribute that is cleared from the DOM immediately after a settled stage submission', async () => {
  mockAdminData();
  vi.mocked(api.stageAiProviderCompatibleConfig).mockResolvedValue(aiProviderConfigFixture as never);
  render(<AdminConsoleTabs />);

  fireEvent.click(await screen.findByRole('tab', { name: 'AI' }));
  const canonicalUrlInput = await screen.findByLabelText('compatible canonical url');
  const displayUrlInput = screen.getByLabelText('compatible display url');
  const modelInput = screen.getByLabelText('compatible model');
  const generationInput = screen.getByLabelText('compatible generation');
  const apiKeyInput = screen.getByLabelText('compatible api key') as HTMLInputElement;

  expect(apiKeyInput).toHaveAttribute('type', 'password');
  expect(apiKeyInput).not.toHaveAttribute('value');

  fireEvent.change(canonicalUrlInput, { target: { value: 'https://internal.example.net/v1' } });
  fireEvent.change(displayUrlInput, { target: { value: 'https://api.example.com/***' } });
  fireEvent.change(modelInput, { target: { value: 'gpt-4o-mini' } });
  fireEvent.change(generationInput, { target: { value: 'gen-1' } });
  fireEvent.change(apiKeyInput, { target: { value: 'super-secret-key-value' } });
  expect(apiKeyInput.value).toBe('super-secret-key-value');

  fireEvent.click(screen.getByRole('button', { name: '설정 저장/회전' }));

  await waitFor(() => expect(api.stageAiProviderCompatibleConfig).toHaveBeenCalledTimes(1));
  expect(api.stageAiProviderCompatibleConfig).toHaveBeenCalledWith(
    {
      canonical_url: 'https://internal.example.net/v1',
      display_url: 'https://api.example.com/***',
      model: 'gpt-4o-mini',
      generation: 'gen-1',
      api_key: 'super-secret-key-value',
      expected_config_version: 1,
    },
    '',
  );
  await waitFor(() => expect(apiKeyInput.value).toBe(''));
  expect(document.body.innerHTML).not.toContain('super-secret-key-value');
});

test('API key input is cleared even when the stage request rejects', async () => {
  mockAdminData();
  vi.mocked(api.stageAiProviderCompatibleConfig).mockRejectedValue(new Error('요청 처리에 실패했습니다'));
  render(<AdminConsoleTabs />);

  fireEvent.click(await screen.findByRole('tab', { name: 'AI' }));
  fireEvent.change(await screen.findByLabelText('compatible canonical url'), { target: { value: 'https://internal.example.net/v1' } });
  fireEvent.change(screen.getByLabelText('compatible display url'), { target: { value: 'https://api.example.com/***' } });
  fireEvent.change(screen.getByLabelText('compatible model'), { target: { value: 'gpt-4o-mini' } });
  fireEvent.change(screen.getByLabelText('compatible generation'), { target: { value: 'gen-1' } });
  const apiKeyInput = screen.getByLabelText('compatible api key') as HTMLInputElement;
  fireEvent.change(apiKeyInput, { target: { value: 'another-secret' } });

  fireEvent.click(screen.getByRole('button', { name: '설정 저장/회전' }));

  await waitFor(() => expect(api.stageAiProviderCompatibleConfig).toHaveBeenCalledTimes(1));
  await waitFor(() => expect(apiKeyInput.value).toBe(''));
  expect(document.body.innerHTML).not.toContain('another-secret');
});

test('staging is blocked client-side with a safe validation toast when URL, model, generation, or key are missing, and testing is blocked while no compatible config is staged', async () => {
  mockAdminData();
  render(<AdminConsoleTabs />);

  fireEvent.click(await screen.findByRole('tab', { name: 'AI' }));
  fireEvent.click(await screen.findByRole('button', { name: '설정 저장/회전' }));

  expect(await screen.findByText('Canonical URL, Display URL, 모델, 세대, API 키를 모두 입력하세요.')).toBeInTheDocument();
  expect(api.stageAiProviderCompatibleConfig).not.toHaveBeenCalled();

  expect(screen.getByRole('button', { name: '저장 설정 테스트' })).toBeDisabled();
  expect(api.testAiProviderStagedConfig).not.toHaveBeenCalled();
});

test('activation is gated on compatible_state === verified and reports a generic safe success message, refreshing only the provider config', async () => {
  mockAdminData();
  vi.mocked(api.fetchAiProviderConfig).mockResolvedValueOnce({ ...aiProviderConfigWithCompatibleFixture, compatible_state: 'unverified' } as never);
  render(<AdminConsoleTabs />);

  fireEvent.click(await screen.findByRole('tab', { name: 'AI' }));
  expect(await screen.findByText('미검증')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: '활성화 확인' })).toBeDisabled();
  expect(api.activateAiProviderCompatible).not.toHaveBeenCalled();
  expect(screen.getByRole('button', { name: '저장 설정 테스트' })).not.toBeDisabled();

  vi.mocked(api.fetchAiProviderConfig).mockResolvedValue(aiProviderConfigWithCompatibleFixture as never);
  fireEvent.click(screen.getByRole('button', { name: '정합성 점검' }));
  await waitFor(() => expect(screen.getByRole('button', { name: '활성화 확인' })).not.toBeDisabled());

  const usersCallsBefore = vi.mocked(api.fetchAdminUsers).mock.calls.length;
  vi.mocked(api.activateAiProviderCompatible).mockResolvedValue(aiProviderConfigWithCompatibleFixture as never);
  fireEvent.click(screen.getByRole('button', { name: '활성화 확인' }));

  await waitFor(() => expect(api.activateAiProviderCompatible).toHaveBeenCalledWith(4, ''));
  expect(await screen.findByText('활성화 확인을 완료했습니다.')).toBeInTheDocument();
  expect(vi.mocked(api.fetchAdminUsers).mock.calls.length).toBe(usersCallsBefore);
});

test('explicit provider selection requires an in-app apply action and calls the selection endpoint with the bound config version and the runtime empty-string CSRF token', async () => {
  mockAdminData();
  vi.mocked(api.selectAiProviderKind).mockResolvedValue(aiProviderConfigFixture as never);
  render(<AdminConsoleTabs />);

  fireEvent.click(await screen.findByRole('tab', { name: 'AI' }));
  await screen.findByText('AI 제공자 설정');
  const kindSelect = screen.getByLabelText('provider kind') as HTMLSelectElement;
  fireEvent.change(kindSelect, { target: { value: 'openai_compatible' } });
  expect(api.selectAiProviderKind).not.toHaveBeenCalled();

  fireEvent.click(screen.getByRole('button', { name: '선택 적용' }));
  await waitFor(() => expect(api.selectAiProviderKind).toHaveBeenCalledWith('openai_compatible', 1, ''));
});

test('deleting the compatible credential requires in-app confirm before calling the delete endpoint', async () => {
  mockAdminData();
  vi.mocked(api.fetchAiProviderConfig).mockResolvedValue(aiProviderConfigWithCompatibleFixture as never);
  vi.mocked(api.deleteAiProviderCredential).mockResolvedValue(aiProviderConfigFixture as never);
  render(<AdminConsoleTabs />);

  fireEvent.click(await screen.findByRole('tab', { name: 'AI' }));
  fireEvent.click(await screen.findByRole('button', { name: '자격 증명 삭제' }));
  expect(api.deleteAiProviderCredential).not.toHaveBeenCalled();

  const dialog = await screen.findByRole('dialog', { name: 'AI 제공자 자격 증명 삭제' });
  fireEvent.click(within(dialog).getByRole('button', { name: '취소' }));
  expect(api.deleteAiProviderCredential).not.toHaveBeenCalled();

  fireEvent.click(screen.getByRole('button', { name: '자격 증명 삭제' }));
  const dialogAgain = await screen.findByRole('dialog', { name: 'AI 제공자 자격 증명 삭제' });
  fireEvent.click(within(dialogAgain).getByRole('button', { name: '삭제' }));

  await waitFor(() => expect(api.deleteAiProviderCredential).toHaveBeenCalledWith(4, ''));
  expect(await screen.findByText('자격 증명 삭제 완료')).toBeInTheDocument();
});

test('reconcile reports safe reconciled/drift status from the flat reconcile response and an unrecognized test reason_code falls back to a generic safe message instead of raw text', async () => {
  mockAdminData();
  vi.mocked(api.reconcileAiProviderConfig).mockResolvedValue({ reconciled: false, compatible_state: 'unverified', config_version: 2 } as never);
  render(<AdminConsoleTabs />);

  fireEvent.click(await screen.findByRole('tab', { name: 'AI' }));
  fireEvent.click(await screen.findByRole('button', { name: '정합성 점검' }));
  expect(await screen.findByText('정합성 점검: 불일치가 감지되어 재보정했습니다')).toBeInTheDocument();

  expect(api.getSafeAiProviderReasonMessage(null)).toBe('연동 테스트 성공');
  expect(api.getSafeAiProviderReasonMessage('connect-failed')).toBe('연동 테스트 실패: 연결할 수 없습니다');
  expect(api.getSafeAiProviderReasonMessage('some_upstream_raw_error_text')).toBe('알 수 없는 상태입니다. 관리자에게 문의하세요.');
});

test('staged-config test uses the current canonical_url/model/generation with the runtime empty-string CSRF token and reports the safe reason label on failure', async () => {
  mockAdminData();
  vi.mocked(api.fetchAiProviderConfig).mockResolvedValue(aiProviderConfigWithCompatibleFixture as never);
  vi.mocked(api.testAiProviderStagedConfig).mockResolvedValue({ success: false, reason_code: 'connect-failed', tested_at: '2026-07-05T00:00:00Z', canonical_url: 'https://internal.example.net/v1', model: 'gpt-4o-mini', generation: 'gen-3' } as never);
  render(<AdminConsoleTabs />);

  fireEvent.click(await screen.findByRole('tab', { name: 'AI' }));
  fireEvent.change(await screen.findByLabelText('compatible canonical url'), { target: { value: 'https://internal.example.net/v1' } });
  fireEvent.change(screen.getByLabelText('compatible model'), { target: { value: 'gpt-4o-mini' } });
  fireEvent.change(screen.getByLabelText('compatible generation'), { target: { value: 'gen-3' } });

  fireEvent.click(screen.getByRole('button', { name: '저장 설정 테스트' }));

  await waitFor(() => expect(api.testAiProviderStagedConfig).toHaveBeenCalledWith(
    { canonical_url: 'https://internal.example.net/v1', model: 'gpt-4o-mini', generation: 'gen-3' },
    '',
  ));
  expect(await screen.findByText('연동 테스트 실패: 연결할 수 없습니다')).toBeInTheDocument();
});

test('AI provider actions disable their triggers while busy and re-enable once the request settles', async () => {
  mockAdminData();
  vi.mocked(api.fetchAiProviderConfig).mockResolvedValue(aiProviderConfigWithCompatibleFixture as never);
  let resolveStage: (value: api.AiProviderConfigResponse) => void = () => {};
  vi.mocked(api.stageAiProviderCompatibleConfig).mockImplementation(() => new Promise<api.AiProviderConfigResponse>((resolve) => { resolveStage = resolve; }));
  render(<AdminConsoleTabs />);

  fireEvent.click(await screen.findByRole('tab', { name: 'AI' }));
  fireEvent.change(await screen.findByLabelText('compatible canonical url'), { target: { value: 'https://internal.example.net/v1' } });
  fireEvent.change(screen.getByLabelText('compatible display url'), { target: { value: 'https://api.example.com/***' } });
  fireEvent.change(screen.getByLabelText('compatible model'), { target: { value: 'gpt-4o-mini' } });
  fireEvent.change(screen.getByLabelText('compatible generation'), { target: { value: 'gen-1' } });
  fireEvent.change(screen.getByLabelText('compatible api key'), { target: { value: 'busy-secret' } });

  const stageButton = screen.getByRole('button', { name: '설정 저장/회전' });
  fireEvent.click(stageButton);
  await waitFor(() => expect(stageButton).toBeDisabled());

  resolveStage(aiProviderConfigFixture);
  await waitFor(() => expect(stageButton).not.toBeDisabled());
});
