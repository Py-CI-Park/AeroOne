import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { AdminConsoleTabs } from '@/components/admin/admin-console-tabs';
import { APP_VERSION, CHANGELOG } from '@/lib/changelog';
import * as api from '@/lib/api';

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return {
    ...actual,
    fetchAdminSummary: vi.fn(),
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
  };
});

beforeEach(() => {
  vi.clearAllMocks();
  mockAdminData();
});

function mockAdminData() {
  vi.mocked(api.fetchAdminSummary).mockResolvedValue({ app_version: '1.12.0', app_env: 'test', database_url: 'sqlite:///test.db', db_ok: true, newsletter_total: 1, latest_newsletter_title: '최근 뉴스', active_modules: 1, coming_soon_modules: 0, asset_health: {}, read_summary: {}, ai_status: { status: 'ok' }, recent_audit_events: [] } as never);
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

async function renderConsole() {
  const view = render(<AdminConsoleTabs />);
  expect(await screen.findByText('대시보드 모듈 DB 관리')).toBeInTheDocument();
  return view;
}

function expectSelectedTab(name: string) {
  expect(screen.getByRole('tab', { name })).toHaveAttribute('aria-selected', 'true');
}

async function pressShortcutAndExpect(key: string, tabName: string) {
  fireEvent.keyDown(window, { key });
  await waitFor(() => expectSelectedTab(tabName));
}

test('G004 maps digit shortcuts 1, 3, and 9 to the exact admin tabs when focus is not editable', async () => {
  await renderConsole();

  await pressShortcutAndExpect('1', '모듈');
  expect(screen.getByText('대시보드 모듈 DB 관리')).toBeInTheDocument();

  await pressShortcutAndExpect('3', 'RBAC');
  expect(await screen.findByText('그룹/RBAC 권한')).toBeInTheDocument();

  await pressShortcutAndExpect('9', '감사');
  expect(await screen.findByRole('heading', { name: '감사 로그' })).toBeInTheDocument();
});

test('G004 ignores 0, non-digits, and modified digit shortcuts', async () => {
  await renderConsole();
  fireEvent.keyDown(window, { key: '3' });
  await waitFor(() => expectSelectedTab('RBAC'));

  fireEvent.keyDown(window, { key: '0' });
  expectSelectedTab('RBAC');

  fireEvent.keyDown(window, { key: 'a' });
  expectSelectedTab('RBAC');

  fireEvent.keyDown(window, { key: '1', ctrlKey: true });
  expectSelectedTab('RBAC');

  fireEvent.keyDown(window, { key: '1', metaKey: true });
  expectSelectedTab('RBAC');

  fireEvent.keyDown(window, { key: '1', altKey: true });
  expectSelectedTab('RBAC');
});

test('G004 ignores digit shortcuts while an input or select has focus', async () => {
  await renderConsole();
  fireEvent.click(screen.getByRole('tab', { name: 'RBAC' }));
  await waitFor(() => expectSelectedTab('RBAC'));

  const groupKey = await screen.findByLabelText('group key');
  groupKey.focus();
  fireEvent.keyDown(window, { key: '1' });
  expectSelectedTab('RBAC');
  expect(screen.getByRole('tab', { name: '모듈' })).toHaveAttribute('aria-selected', 'false');

  groupKey.blur();
  const subjectType = screen.getByLabelText('grant subject type');
  subjectType.focus();
  fireEvent.keyDown(window, { key: '1' });
  expectSelectedTab('RBAC');
  expect(screen.getByRole('tab', { name: '모듈' })).toHaveAttribute('aria-selected', 'false');
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
  expect(within(helpList as HTMLElement).getByText(/숫자 키 1~9/)).toBeInTheDocument();
});

test('G004 release version constants advance to 1.12.1', () => {
  expect(APP_VERSION).toBe('1.12.1');
  expect(CHANGELOG[0].version).toBe('1.12.1');
});
