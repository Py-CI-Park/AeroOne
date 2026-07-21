import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { AdminConsoleTabs } from '@/components/admin/admin-console-tabs';
import { APP_VERSION, CHANGELOG } from '@/lib/changelog';
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
    fetchLlmConnections: vi.fn().mockResolvedValue([]),
  };
});

beforeEach(() => {
  vi.clearAllMocks();
  mockAdminData();
});

function mockAdminData() {
  vi.mocked(api.fetchAdminOverview).mockResolvedValue({
    generated_at: '2026-07-05T00:00:00Z',
    anchor: '2026-06-28T00:00:00Z',
    users: { total: 1, active: 1, inactive: 0, roles: { admin: 1, user: 0, pending: 0 }, created: { current: 0, prior: 0, delta: 0 } },
    logins: { success: { current: 0, prior: 0, delta: 0 }, failure: { current: 0, prior: 0, delta: 0 }, logout: { current: 0, prior: 0, delta: 0 } },
    ai: { total: { current: 0, prior: 0, delta: 0 }, failure: { current: 0, prior: 0, delta: 0 } },
    sessions: { active_session_count: 0, active_user_count: 0, active_count: 0 },
    modules: { total: 1, buckets: { unavailable: [], coming: [], development: [], active: [{ key: 'ov-dashboard', label: 'Overview Dashboard' }] } },
    system: { app_version: '1.12.0', app_env: 'test', database_kind: 'sqlite', newsletter_count: 1, asset_health: { ok: 1, missing: 0, checksum_mismatch: 0, misconfig: 0 }, read_summary: { rows: 0, total_reads: 0 } },
    recent_audit: [],
  } as never);
  vi.mocked(api.fetchAdminUsers).mockResolvedValue([{ id: 1, username: 'operator', email: 'op@example.com', role: 'admin', is_active: true, permissions: ['admin.read'] }] as never);
  vi.mocked(api.fetchConnectedUsers).mockResolvedValue({ active_sessions: [], active_count: 0, recent_login_events: [], login_failure_count: 0, read_tracking_summary: { rows: 0, total_reads: 0 } } as never);
  vi.mocked(api.fetchAdminPermissions).mockResolvedValue([{ key: 'admin.read', description: 'Admin read' }, { key: 'collections.nsa.read', description: 'NSA read' }] as never);
  vi.mocked(api.fetchAdminGroups).mockResolvedValue([{ id: 2, key: 'ops', name: 'Operators', is_active: true, permissions: ['admin.read'] }] as never);
  vi.mocked(api.fetchRbacMatrix).mockResolvedValue([{ user_id: 1, username: 'operator', role: 'admin', role_permissions: [], direct_permissions: ['admin.read'], group_permissions: [], effective_permissions: [{ key: 'admin.read', sources: ['direct'] }], resource_grants: [] }] as never);
  vi.mocked(api.listResourceGrants).mockResolvedValue([{ id: 3, subject_type: 'group', subject_id: 2, resource_type: 'collection', resource_id: 'nsa', permission_key: 'collections.nsa.read' }] as never);
  vi.mocked(api.fetchAuditEvents).mockResolvedValue([{ id: 4, actor_username: 'operator', action: 'backup.create', target_type: 'backup', target_id: '1', status: 'success', created_at: '2026-07-05T00:00:00Z' }] as never);
  vi.mocked(api.fetchServiceModulesAdmin).mockResolvedValue([{ id: 5, key: 'dashboard', title: 'Dashboard', description: 'Main', href: '/', section: 'Core', status: 'active', badge: 'Live', sort_order: 1, is_enabled: true, is_external: false, visibility: 'admin' }] as never);
  vi.mocked(api.fetchAssetHealth).mockResolvedValue({ ok: 1, missing: 0, checksum_mismatch: 0, misconfig: 0, items: [] } as never);
  vi.mocked(api.fetchConfigHealth).mockResolvedValue({ roots: [] } as never);
  vi.mocked(api.fetchBackups).mockResolvedValue([{ id: 6, filename: 'backup.zip', sha256: '1234567890abcdef', file_size: 123, status: 'created', created_at: '2026-07-05T00:00:00Z' }] as never);
  vi.mocked(api.fetchCategories).mockResolvedValue([{ id: 7, name: '분류', description: '설명', sort_order: 0, is_active: true }] as never);
  vi.mocked(api.fetchTags).mockResolvedValue([{ id: 8, name: '태그', sort_order: 0, is_active: true }] as never);
  vi.mocked(api.fetchAdminAiStatus).mockResolvedValue({ status: { ok: true }, request_logs_total: 0, request_failures: 0 } as never);
  vi.mocked(api.createServiceModule).mockResolvedValue({ id: 10 } as never);
  vi.mocked(api.updateServiceModule).mockResolvedValue({ id: 5 } as never);
  vi.mocked(api.deleteServiceModule).mockResolvedValue(undefined as never);
  vi.mocked(api.createResourceGrant).mockResolvedValue({ id: 11 } as never);
  vi.mocked(api.addUserGroup).mockResolvedValue(undefined as never);
  vi.mocked(api.removeUserGroup).mockResolvedValue(undefined as never);
  vi.mocked(api.deleteResourceGrant).mockResolvedValue(undefined as never);
  vi.mocked(api.purgeSessions).mockResolvedValue({ login_events_deleted: 0, session_activity_deleted: 0 } as never);
}

// G008: 9평면탭 → 6그룹(overview/accounts/content/system/ai/audit) 재편으로 숫자 단축키는
// 이제 1~6 만 유효한 그룹에 대응한다(개요=1, 계정=2, 콘텐츠=3, 시스템=4, AI=5, 감사=6).
// 아래 테스트들은 '숫자키로 그룹 전환·편집 포커스 시 무시·언마운트 정리·도움말 존재'라는
// 원래 의도를 그대로 보존하되, 매핑 대상 탭 이름/인덱스만 새 그룹 순서로 갱신한다.
async function renderConsole() {
  const view = render(<AdminConsoleTabs />);
  expect(await screen.findByText('사용자 통계')).toBeInTheDocument();
  return view;
}

function expectSelectedTab(name: string) {
  expect(screen.getByRole('tab', { name })).toHaveAttribute('aria-selected', 'true');
}

async function pressShortcutAndExpect(key: string, tabName: string) {
  fireEvent.keyDown(window, { key });
  await waitFor(() => expectSelectedTab(tabName));
}

test('G004 maps digit shortcuts 3, 2, and 6 to the exact admin tabs when focus is not editable', async () => {
  await renderConsole();

  await pressShortcutAndExpect('3', '콘텐츠');
  expect(await screen.findByText('대시보드 모듈 DB 관리')).toBeInTheDocument();

  await pressShortcutAndExpect('2', '계정');
  expect(await screen.findByText('그룹/RBAC 권한')).toBeInTheDocument();

  await pressShortcutAndExpect('6', '감사');
  expect(await screen.findByRole('heading', { name: '감사 로그' })).toBeInTheDocument();
});

test('G004 ignores 0, non-digits, and modified digit shortcuts', async () => {
  await renderConsole();
  fireEvent.keyDown(window, { key: '2' });
  await waitFor(() => expectSelectedTab('계정'));

  fireEvent.keyDown(window, { key: '0' });
  expectSelectedTab('계정');

  fireEvent.keyDown(window, { key: 'a' });
  expectSelectedTab('계정');

  fireEvent.keyDown(window, { key: '1', ctrlKey: true });
  expectSelectedTab('계정');

  fireEvent.keyDown(window, { key: '1', metaKey: true });
  expectSelectedTab('계정');

  fireEvent.keyDown(window, { key: '1', altKey: true });
  expectSelectedTab('계정');

  // 6그룹 재편 후 7~9 는 유효한 탭이 없으므로 무시된다(정규식 [1-6] + tabs[idx] 부재 no-op).
  fireEvent.keyDown(window, { key: '7' });
  expectSelectedTab('계정');
  fireEvent.keyDown(window, { key: '9' });
  expectSelectedTab('계정');
});

test('G004 ignores digit shortcuts while an input or select has focus', async () => {
  await renderConsole();
  fireEvent.click(screen.getByRole('tab', { name: '계정' }));
  await waitFor(() => expectSelectedTab('계정'));

  const groupKey = await screen.findByLabelText('group key');
  groupKey.focus();
  fireEvent.keyDown(window, { key: '1' });
  expectSelectedTab('계정');
  expect(screen.getByRole('tab', { name: '개요' })).toHaveAttribute('aria-selected', 'false');

  groupKey.blur();
  const subjectType = screen.getByLabelText('grant subject type');
  subjectType.focus();
  fireEvent.keyDown(window, { key: '1' });
  expectSelectedTab('계정');
  expect(screen.getByRole('tab', { name: '개요' })).toHaveAttribute('aria-selected', 'false');
});

test('G004 removes the global shortcut listener on unmount', async () => {
  const consoleError = vi.spyOn(console, 'error').mockImplementation(() => undefined);
  const { unmount } = await renderConsole();

  unmount();
  expect(() => fireEvent.keyDown(window, { key: '2' })).not.toThrow();
  expect(consoleError).not.toHaveBeenCalled();
  consoleError.mockRestore();
});

test('G004 exposes collapsible onboarding help with audit tab and shortcut guidance', async () => {
  await renderConsole();

  expect(screen.getByText('콘솔 사용 도움말')).toBeInTheDocument();
  const helpList = screen.getByText('콘솔 사용 도움말').closest('details');
  expect(helpList).not.toBeNull();
  expect(within(helpList as HTMLElement).getByText(/감사/)).toBeInTheDocument();
  expect(within(helpList as HTMLElement).getByText(/운영 이벤트와 CSV 내보내기/)).toBeInTheDocument();
  expect(within(helpList as HTMLElement).getByText(/숫자 키 1~6/)).toBeInTheDocument();
});

test('release version constants advance to 1.19.0', () => {
  expect(APP_VERSION).toBe('1.19.0');
  expect(CHANGELOG[0].version).toBe('1.19.0');
});
