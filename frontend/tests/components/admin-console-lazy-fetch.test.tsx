import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { AdminConsoleTabs } from '@/components/admin/admin-console-tabs';
import * as api from '@/lib/api';

// G008: 마운트 시 17종 refreshKey 를 일괄 fetch 하던 과거 동작을 대체하는 lazy fetch 계약을
// 검증한다. 그룹 진입 시 그 그룹의 refreshKeys 만 fetch 되고, 같은 그룹 재진입 시 재fetch
// 되지 않아야 한다(명시적 새로고침 버튼은 예외 — 이 파일에서는 다루지 않는다).
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
    fetchAiProviderConfig: vi.fn(),
    fetchLlmConnections: vi.fn(),
  };
});

const overviewFixture = {
  generated_at: '2026-07-17T00:00:00Z',
  anchor: '2026-07-10T00:00:00Z',
  users: { total: 1, active: 1, inactive: 0, roles: { admin: 1, user: 0, pending: 0 }, created: { current: 0, prior: 0, delta: 0 } },
  logins: { success: { current: 0, prior: 0, delta: 0 }, failure: { current: 0, prior: 0, delta: 0 }, logout: { current: 0, prior: 0, delta: 0 } },
  ai: { total: { current: 0, prior: 0, delta: 0 }, failure: { current: 0, prior: 0, delta: 0 } },
  sessions: { active_session_count: 0, active_user_count: 0, active_count: 0 },
  modules: { total: 0, buckets: { unavailable: [], coming: [], development: [], active: [] } },
  system: { app_version: '1.17.1', app_env: 'test', database_kind: 'sqlite', newsletter_count: 0, asset_health: { ok: 0, missing: 0, checksum_mismatch: 0, misconfig: 0 }, read_summary: { rows: 0, total_reads: 0 } },
  recent_audit: [],
};

// admin-console-tabs.tsx 가 refresh() 에서 소비하는 17종 fetcher 전부(그룹별로 정확히
// 어떤 것이 lazy-fetch 되는지 단언하기 위해 전 종을 스파이한다).
const allFetcherNames = [
  'fetchAdminOverview',
  'fetchAdminUsers',
  'fetchConnectedUsers',
  'fetchAdminPermissions',
  'fetchAdminGroups',
  'fetchRbacMatrix',
  'listResourceGrants',
  'fetchAuditEvents',
  'fetchServiceModulesAdmin',
  'fetchAssetHealth',
  'fetchConfigHealth',
  'fetchBackups',
  'fetchCategories',
  'fetchTags',
  'fetchAdminAiStatus',
  'fetchAiProviderConfig',
  'fetchLlmConnections',
] as const;

function mockAdminData() {
  vi.mocked(api.fetchAdminOverview).mockResolvedValue(overviewFixture as never);
  vi.mocked(api.fetchAdminUsers).mockResolvedValue([{ id: 1, username: 'operator', email: 'op@example.com', role: 'admin', is_active: true, permissions: [] }] as never);
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
  vi.mocked(api.fetchAiProviderConfig).mockResolvedValue({ selected_kind: 'ollama', compatible_state: 'absent', compatible_display_url: null, compatible_model: null, compatible_generation: null, compatible_test_proof_at: null, compatible_test_proof_model: null, config_version: 1, updated_at: '2026-07-17T00:00:00Z' } as never);
  vi.mocked(api.fetchLlmConnections).mockResolvedValue([] as never);
}

function totalCallCount() {
  return allFetcherNames.reduce((sum, name) => sum + vi.mocked(api[name]).mock.calls.length, 0);
}

beforeEach(() => {
  vi.clearAllMocks();
  mockAdminData();
});

test('mounting the console (개요 진입) fetches far fewer requests than the legacy 17-fetch bulk refresh', async () => {
  render(<AdminConsoleTabs />);

  // 개요(overview) 그룹만 lazy fetch 되어야 한다: fetchAdminOverview 단 1건.
  await waitFor(() => expect(api.fetchAdminOverview).toHaveBeenCalledTimes(1));

  // 다른 16종 fetcher 는 마운트 시점에 전혀 호출되지 않는다(과거 17종 일괄 fetch 대비 감소).
  expect(api.fetchAdminUsers).not.toHaveBeenCalled();
  expect(api.fetchConnectedUsers).not.toHaveBeenCalled();
  expect(api.fetchAdminPermissions).not.toHaveBeenCalled();
  expect(api.fetchAdminGroups).not.toHaveBeenCalled();
  expect(api.fetchRbacMatrix).not.toHaveBeenCalled();
  expect(api.listResourceGrants).not.toHaveBeenCalled();
  expect(api.fetchAuditEvents).not.toHaveBeenCalled();
  expect(api.fetchServiceModulesAdmin).not.toHaveBeenCalled();
  expect(api.fetchAssetHealth).not.toHaveBeenCalled();
  expect(api.fetchConfigHealth).not.toHaveBeenCalled();
  expect(api.fetchBackups).not.toHaveBeenCalled();
  expect(api.fetchCategories).not.toHaveBeenCalled();
  expect(api.fetchTags).not.toHaveBeenCalled();
  expect(api.fetchAdminAiStatus).not.toHaveBeenCalled();
  expect(api.fetchAiProviderConfig).not.toHaveBeenCalled();
  expect(api.fetchLlmConnections).not.toHaveBeenCalled();

  // before(과거 마운트 시 일괄 refresh): 17건. after(신규 lazy 마운트): 1건.
  const before = 17;
  const after = totalCallCount();
  expect(after).toBe(1);
  expect(after).toBeLessThan(before);
});

test('entering the 계정(accounts) tab lazily fetches its refreshKeys only at that point', async () => {
  render(<AdminConsoleTabs />);
  await waitFor(() => expect(api.fetchAdminOverview).toHaveBeenCalledTimes(1));

  expect(api.fetchAdminUsers).not.toHaveBeenCalled();
  fireEvent.click(await screen.findByRole('tab', { name: '계정' }));

  await waitFor(() => expect(api.fetchAdminUsers).toHaveBeenCalledTimes(1));
  expect(api.fetchConnectedUsers).toHaveBeenCalledTimes(1);
  expect(api.fetchAdminPermissions).toHaveBeenCalledTimes(1);
  expect(api.fetchAdminGroups).toHaveBeenCalledTimes(1);
  expect(api.fetchRbacMatrix).toHaveBeenCalledTimes(1);
  expect(api.listResourceGrants).toHaveBeenCalledTimes(1);

  // 계정 그룹과 무관한 다른 그룹의 fetcher 는 여전히 호출되지 않는다.
  expect(api.fetchServiceModulesAdmin).not.toHaveBeenCalled();
  expect(api.fetchAssetHealth).not.toHaveBeenCalled();
  expect(api.fetchAdminAiStatus).not.toHaveBeenCalled();
  expect(api.fetchAuditEvents).not.toHaveBeenCalled();
});

test('re-entering an already-loaded group does not refetch (per-group cache)', async () => {
  render(<AdminConsoleTabs />);
  await waitFor(() => expect(api.fetchAdminOverview).toHaveBeenCalledTimes(1));

  fireEvent.click(await screen.findByRole('tab', { name: '계정' }));
  await waitFor(() => expect(api.fetchAdminUsers).toHaveBeenCalledTimes(1));

  fireEvent.click(await screen.findByRole('tab', { name: '콘텐츠' }));
  await waitFor(() => expect(api.fetchServiceModulesAdmin).toHaveBeenCalledTimes(1));

  // 계정 그룹으로 되돌아가도 users/connectedUsers 등은 다시 fetch 되지 않는다.
  fireEvent.click(screen.getByRole('tab', { name: '계정' }));
  await screen.findByText('사용자/RBAC');
  expect(api.fetchAdminUsers).toHaveBeenCalledTimes(1);
  expect(api.fetchConnectedUsers).toHaveBeenCalledTimes(1);
  expect(api.fetchAdminPermissions).toHaveBeenCalledTimes(1);
  expect(api.fetchAdminGroups).toHaveBeenCalledTimes(1);
  expect(api.fetchRbacMatrix).toHaveBeenCalledTimes(1);
  expect(api.listResourceGrants).toHaveBeenCalledTimes(1);

  // 개요로 되돌아가도 overview 는 다시 fetch 되지 않는다.
  fireEvent.click(screen.getByRole('tab', { name: '개요' }));
  await screen.findByText('사용자 통계');
  expect(api.fetchAdminOverview).toHaveBeenCalledTimes(1);
});

// G008: ?tab= 하위호환·canonical 재작성 회귀. 구 9평면탭 키가 신규 6그룹으로 매핑되고,
// 알 수 없는 값은 개요로 폴백하며, 진입 후 URL 이 정규 그룹키로 재작성되는지 고정한다.
function tabSelected(name: string) {
  return screen.getByRole('tab', { name }).getAttribute('aria-selected') === 'true';
}

test('legacy ?tab= keys map to their new group and lazily fetch that group on mount', async () => {
  window.history.replaceState({}, '', '/admin?tab=users');
  render(<AdminConsoleTabs />);

  // 구 'users' 탭 딥링크 → 계정 그룹 활성 + 계정 그룹 refreshKeys 만 lazy fetch(개요 아님).
  await waitFor(() => expect(api.fetchAdminUsers).toHaveBeenCalledTimes(1));
  expect(tabSelected('계정')).toBe(true);
  expect(api.fetchAdminOverview).not.toHaveBeenCalled();
  // URL 은 정규 그룹키(accounts)로 재작성된다.
  expect(new URLSearchParams(window.location.search).get('tab')).toBe('accounts');
});

test('legacy content-family ?tab= keys (modules/taxonomy/search) resolve to the 콘텐츠 group', async () => {
  window.history.replaceState({}, '', '/admin?tab=modules');
  render(<AdminConsoleTabs />);

  await waitFor(() => expect(api.fetchServiceModulesAdmin).toHaveBeenCalledTimes(1));
  expect(tabSelected('콘텐츠')).toBe(true);
  expect(new URLSearchParams(window.location.search).get('tab')).toBe('content');
});

test('an unknown ?tab= value falls back to the 개요 group', async () => {
  window.history.replaceState({}, '', '/admin?tab=totally-unknown');
  render(<AdminConsoleTabs />);

  await waitFor(() => expect(api.fetchAdminOverview).toHaveBeenCalledTimes(1));
  expect(tabSelected('개요')).toBe(true);
  expect(api.fetchAdminUsers).not.toHaveBeenCalled();
  expect(new URLSearchParams(window.location.search).get('tab')).toBe('overview');
});

test('switching groups rewrites ?tab= to the canonical group key', async () => {
  render(<AdminConsoleTabs />);
  await waitFor(() => expect(api.fetchAdminOverview).toHaveBeenCalledTimes(1));

  fireEvent.click(await screen.findByRole('tab', { name: '시스템' }));
  await waitFor(() => expect(new URLSearchParams(window.location.search).get('tab')).toBe('system'));
});
