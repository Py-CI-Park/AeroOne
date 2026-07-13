import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { AdminConsoleTabs } from '@/components/admin/admin-console-tabs';
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
  };
});

beforeEach(() => {
  vi.useRealTimers();
  vi.clearAllMocks();
  vi.mocked(api.fetchAdminOverview).mockResolvedValue({
    generated_at: '2026-07-05T00:00:00Z',
    anchor: '2026-06-28T00:00:00Z',
    users: { total: 0, active: 0, inactive: 0, roles: { admin: 0, user: 0, pending: 0 }, created: { current: 0, prior: 0, delta: 0 } },
    logins: { success: { current: 0, prior: 0, delta: 0 }, failure: { current: 0, prior: 0, delta: 0 }, logout: { current: 0, prior: 0, delta: 0 } },
    ai: { total: { current: 0, prior: 0, delta: 0 }, failure: { current: 0, prior: 0, delta: 0 } },
    sessions: { active_session_count: 0, active_user_count: 0, active_count: 0 },
    modules: { total: 0, buckets: { unavailable: [], coming: [], development: [], active: [] } },
    system: { app_version: '1.12.0', app_env: 'test', database_kind: 'sqlite', newsletter_count: 0, asset_health: { ok: 0, missing: 0, checksum_mismatch: 0, misconfig: 0 }, read_summary: { rows: 0, total_reads: 0 } },
    recent_audit: [],
  } as never);
  vi.mocked(api.fetchAdminUsers).mockResolvedValue([] as never);
  vi.mocked(api.fetchConnectedUsers).mockResolvedValue({ active_sessions: [], active_count: 0, recent_login_events: [], login_failure_count: 0, read_tracking_summary: { rows: 0, total_reads: 0 } } as never);
  vi.mocked(api.fetchAdminPermissions).mockResolvedValue([] as never);
  vi.mocked(api.fetchAdminGroups).mockResolvedValue([] as never);
  vi.mocked(api.fetchRbacMatrix).mockResolvedValue([] as never);
  vi.mocked(api.listResourceGrants).mockResolvedValue([] as never);
  vi.mocked(api.fetchAuditEvents).mockResolvedValue([] as never);
  vi.mocked(api.fetchServiceModulesAdmin).mockResolvedValue([] as never);
  vi.mocked(api.fetchAssetHealth).mockResolvedValue({ ok: 0, missing: 0, checksum_mismatch: 0, misconfig: 0, items: [] } as never);
  vi.mocked(api.fetchConfigHealth).mockResolvedValue({ roots: [] } as never);
  vi.mocked(api.fetchBackups).mockResolvedValue([] as never);
  vi.mocked(api.fetchCategories).mockResolvedValue([] as never);
  vi.mocked(api.fetchTags).mockResolvedValue([] as never);
  vi.mocked(api.fetchAdminAiStatus).mockResolvedValue({ status: { ok: true }, request_logs_total: 0, request_failures: 0 } as never);
});

afterEach(() => {
  vi.useRealTimers();
});

test('세션 자동 새로고침은 켠 뒤 connectedUsers만 15초마다 다시 불러오고 끄면 정리된다', async () => {
  render(<AdminConsoleTabs />);

  fireEvent.click(await screen.findByRole('tab', { name: '세션' }));
  expect(await screen.findByRole('heading', { name: '접속자/세션' })).toBeInTheDocument();
  await waitFor(() => expect(api.fetchConnectedUsers).toHaveBeenCalledTimes(1));

  const initialCalls = {
    overview: vi.mocked(api.fetchAdminOverview).mock.calls.length,
    users: vi.mocked(api.fetchAdminUsers).mock.calls.length,
    permissions: vi.mocked(api.fetchAdminPermissions).mock.calls.length,
    groups: vi.mocked(api.fetchAdminGroups).mock.calls.length,
    rbacMatrix: vi.mocked(api.fetchRbacMatrix).mock.calls.length,
    resourceGrants: vi.mocked(api.listResourceGrants).mock.calls.length,
    audits: vi.mocked(api.fetchAuditEvents).mock.calls.length,
    modules: vi.mocked(api.fetchServiceModulesAdmin).mock.calls.length,
    health: vi.mocked(api.fetchAssetHealth).mock.calls.length,
    configHealth: vi.mocked(api.fetchConfigHealth).mock.calls.length,
    backups: vi.mocked(api.fetchBackups).mock.calls.length,
    categories: vi.mocked(api.fetchCategories).mock.calls.length,
    tags: vi.mocked(api.fetchTags).mock.calls.length,
    ai: vi.mocked(api.fetchAdminAiStatus).mock.calls.length,
  };

  vi.useFakeTimers();
  fireEvent.click(screen.getByLabelText('세션 자동 새로고침'));
  await act(async () => {
    vi.advanceTimersByTime(15000);
  });

  expect(api.fetchConnectedUsers).toHaveBeenCalledTimes(2);
  expect(api.fetchAdminOverview).toHaveBeenCalledTimes(initialCalls.overview);
  expect(api.fetchAdminUsers).toHaveBeenCalledTimes(initialCalls.users);
  expect(api.fetchAdminPermissions).toHaveBeenCalledTimes(initialCalls.permissions);
  expect(api.fetchAdminGroups).toHaveBeenCalledTimes(initialCalls.groups);
  expect(api.fetchRbacMatrix).toHaveBeenCalledTimes(initialCalls.rbacMatrix);
  expect(api.listResourceGrants).toHaveBeenCalledTimes(initialCalls.resourceGrants);
  expect(api.fetchAuditEvents).toHaveBeenCalledTimes(initialCalls.audits);
  expect(api.fetchServiceModulesAdmin).toHaveBeenCalledTimes(initialCalls.modules);
  expect(api.fetchAssetHealth).toHaveBeenCalledTimes(initialCalls.health);
  expect(api.fetchConfigHealth).toHaveBeenCalledTimes(initialCalls.configHealth);
  expect(api.fetchBackups).toHaveBeenCalledTimes(initialCalls.backups);
  expect(api.fetchCategories).toHaveBeenCalledTimes(initialCalls.categories);
  expect(api.fetchTags).toHaveBeenCalledTimes(initialCalls.tags);
  expect(api.fetchAdminAiStatus).toHaveBeenCalledTimes(initialCalls.ai);

  fireEvent.click(screen.getByLabelText('세션 자동 새로고침'));
  await act(async () => {
    vi.advanceTimersByTime(15000);
  });
  expect(api.fetchConnectedUsers).toHaveBeenCalledTimes(2);
});
