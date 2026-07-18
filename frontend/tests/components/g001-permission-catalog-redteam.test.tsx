import React from 'react';
import { render, screen, within, fireEvent } from '@testing-library/react';
import { AdminConsoleTabs } from '@/components/admin/admin-console-tabs';
import { PermissionCheckboxGrid } from '@/components/admin/widgets/permission-checkbox-grid';
import { describePermission, groupPermissionsByCategory } from '@/lib/permission-catalog';
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
    fetchAssetHealth: vi.fn(),
    fetchConfigHealth: vi.fn(),
    fetchBackups: vi.fn(),
    fetchCategories: vi.fn(),
    fetchTags: vi.fn(),
    fetchAdminAiStatus: vi.fn(),
    fetchLlmConnections: vi.fn().mockResolvedValue([]),
    createResourceGrant: vi.fn(),
    updateAdminUser: vi.fn(),
    upsertAdminGroup: vi.fn(),
    addUserGroup: vi.fn(),
    removeUserGroup: vi.fn(),
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
    users: { total: 2, active: 2, inactive: 0, roles: { admin: 1, user: 1, pending: 0 }, created: { current: 0, prior: 0, delta: 0 } },
    logins: { success: { current: 0, prior: 0, delta: 0 }, failure: { current: 0, prior: 0, delta: 0 }, logout: { current: 0, prior: 0, delta: 0 } },
    ai: { total: { current: 0, prior: 0, delta: 0 }, failure: { current: 0, prior: 0, delta: 0 } },
    sessions: { active_session_count: 0, active_user_count: 0, active_count: 0 },
    modules: { total: 0, buckets: { unavailable: [], coming: [], development: [], active: [] } },
    system: { app_version: '1.12.0', app_env: 'test', database_kind: 'sqlite', newsletter_count: 0, asset_health: { ok: 0, missing: 0, checksum_mismatch: 0, misconfig: 0 }, read_summary: { rows: 0, total_reads: 0 } },
    recent_audit: [],
  } as never);
  vi.mocked(api.fetchAdminUsers).mockResolvedValue([
    { id: 1, username: 'operator', email: 'op@example.com', role: 'admin', is_active: true, permissions: ['admin.rbac.manage'] },
    { id: 9, username: 'analyst', email: null, role: 'user', is_active: true, permissions: [] },
  ] as never);
  vi.mocked(api.fetchConnectedUsers).mockResolvedValue({ active_sessions: [], active_count: 0, recent_login_events: [], login_failure_count: 0, read_tracking_summary: { rows: 0, total_reads: 0 } } as never);
  vi.mocked(api.fetchAdminPermissions).mockResolvedValue([
    { key: 'admin.rbac.manage' },
    { key: 'admin.users.manage' },
    { key: 'ai.use' },
    { key: 'collections.nsa.read' },
    { key: 'collections.read' },
    { key: 'documents.delete' },
    { key: 'search.nsa.read' },
  ] as never);
  vi.mocked(api.fetchAdminGroups).mockResolvedValue([{ id: 2, key: 'ops', name: 'Operators', is_active: true, permissions: ['admin.rbac.manage'] }] as never);
  vi.mocked(api.fetchRbacMatrix).mockResolvedValue([{ user_id: 1, username: 'operator', role: 'admin', role_permissions: [], direct_permissions: ['admin.rbac.manage'], group_permissions: [], effective_permissions: [{ key: 'admin.rbac.manage', sources: ['direct'] }], resource_grants: [] }] as never);
  vi.mocked(api.listResourceGrants).mockResolvedValue([] as never);
  vi.mocked(api.fetchAuditEvents).mockResolvedValue([] as never);
  vi.mocked(api.fetchServiceModulesAdmin).mockResolvedValue([] as never);
  vi.mocked(api.fetchAssetHealth).mockResolvedValue({ ok: 0, missing: 0, checksum_mismatch: 0, misconfig: 0, items: [] } as never);
  vi.mocked(api.fetchConfigHealth).mockResolvedValue({ roots: [] } as never);
  vi.mocked(api.fetchBackups).mockResolvedValue([] as never);
  vi.mocked(api.fetchCategories).mockResolvedValue([] as never);
  vi.mocked(api.fetchTags).mockResolvedValue([] as never);
  vi.mocked(api.fetchAdminAiStatus).mockResolvedValue({ status: { ok: true }, request_logs_total: 0, request_failures: 0 } as never);
  vi.mocked(api.createResourceGrant).mockResolvedValue({ id: 7, subject_type: 'user', subject_id: 1, resource_type: 'collection', resource_id: 'nsa', permission_key: 'collections.nsa.read' } as never);
}

test.each(['x.y.z.evil', '', 'admin'])('describePermission safely falls back for unknown key %j', (key) => {
  expect(() => describePermission(key)).not.toThrow();
  expect(describePermission(key)).toEqual({ key, label: key, category: '기타', description: '' });
});

test('groupPermissionsByCategory is deterministic and pins unknown permissions to 기타 last', () => {
  const firstOrdering = ['x.y.z.evil', 'collections.read', 'admin.rbac.manage', 'collections.nsa.read', 'ai.use'];
  const secondOrdering = ['collections.nsa.read', 'ai.use', 'x.y.z.evil', 'admin.rbac.manage', 'collections.read'];

  const first = groupPermissionsByCategory(firstOrdering);
  const second = groupPermissionsByCategory(secondOrdering);
  const compact = (groups: ReturnType<typeof groupPermissionsByCategory>) => groups.map((group) => ({
    category: group.category,
    keys: group.entries.map((entry) => entry.key),
  }));

  expect(compact(first)).toEqual(compact(second));
  expect(first.at(-1)?.category).toBe('기타');
  expect(second.at(-1)?.category).toBe('기타');
  for (const group of first) {
    expect(group.entries.map((entry) => entry.key)).toEqual([...group.entries.map((entry) => entry.key)].sort());
  }
});

test('resource grant permission select exposes only collection-safe raw keys inside AdminConsoleTabs', async () => {
  render(<AdminConsoleTabs />);
  fireEvent.click(await screen.findByRole('tab', { name: '계정' }));
  expect(await screen.findByText('RBAC 매트릭스 / 리소스 권한')).toBeInTheDocument();

  const permissionSelect = screen.getByLabelText('grant permission key');
  const options = within(permissionSelect).getAllByRole('option') as HTMLOptionElement[];
  const values = options.map((option) => option.value);

  expect(values).toEqual(['', 'collections.nsa.read', 'collections.read']);
  expect(values).not.toContain('admin.rbac.manage');
  expect(values).not.toContain('admin.users.manage');
  expect(values.some((value) => value.startsWith('admin.'))).toBe(false);
  expect(options.slice(1).map((option) => option.value)).toEqual(['collections.nsa.read', 'collections.read']);
  expect(options.slice(1).map((option) => option.textContent)).toEqual(['NSA 문서 열람 (collections.nsa.read)', '문서 전체 열람 (collections.read)']);
});

test('PermissionCheckboxGrid empty state renders no checkboxes', () => {
  render(<PermissionCheckboxGrid permissions={[]} value={[]} onChange={vi.fn()} label="redteam permissions" />);

  expect(screen.getByText('사용 가능한 권한이 없습니다.')).toBeInTheDocument();
  expect(screen.queryAllByRole('checkbox')).toHaveLength(0);
});

test('PermissionCheckboxGrid renders unknown permissions under 기타 without dropping the raw key', () => {
  render(<PermissionCheckboxGrid permissions={[{ key: 'x.y.z.evil' }]} value={[]} onChange={vi.fn()} label="redteam permissions" />);

  expect(screen.getByText('기타')).toBeInTheDocument();
  expect(screen.getAllByText('x.y.z.evil').some((element) => element.classList.contains('font-mono'))).toBe(true);
  expect(screen.getByLabelText('redteam permissions x.y.z.evil')).toBeInTheDocument();
});
