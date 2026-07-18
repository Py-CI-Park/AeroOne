import React from 'react';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { AdminConsoleTabs } from '@/components/admin/admin-console-tabs';
import { paginate } from '@/components/admin/widgets/list-filter';
import { formatRelativeTime } from '@/lib/relative-time';
import * as api from '@/lib/api';
import type { ConnectedUsersResponse, LoginEvent } from '@/lib/types';

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
  };
});

const connectedUsersEmpty: ConnectedUsersResponse = {
  active_sessions: [],
  active_session_count: 0,
  active_user_count: 0,
  active_count: 0,
  recent_login_events: [],
  login_failure_count: 0,
  read_tracking_summary: { rows: 0, total_reads: 0 },
};

function mockAdminData(connectedUsers: ConnectedUsersResponse = connectedUsersEmpty) {
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
  vi.mocked(api.fetchConnectedUsers).mockResolvedValue(connectedUsers as never);
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
}

function makeLoginEvents(count: number): LoginEvent[] {
  const base = Date.parse('2026-07-05T12:00:00.000Z');
  return Array.from({ length: count }, (_, index) => ({
    id: index + 1,
    user_id: index + 1,
    username: `user-${String(index + 1).padStart(2, '0')}`,
    ip_address: `10.0.0.${index + 1}`,
    user_agent: 'vitest',
    status: index % 3 === 0 ? 'failure' : 'success',
    created_at: new Date(base + index * 60_000).toISOString(),
  }));
}

function deferred<T>() {
  let resolvePromise!: (value: T) => void;
  const promise = new Promise<T>((resolve) => {
    resolvePromise = resolve;
  });
  return { promise, resolve: resolvePromise };
}

beforeEach(() => {
  vi.useRealTimers();
  vi.clearAllMocks();
  mockAdminData();
});

afterEach(() => {
  vi.useRealTimers();
});

test('paginate clamps adversarial pages and preserves exact slices', () => {
  const items = ['a', 'b', 'c', 'd', 'e', 'f', 'g'];

  expect(paginate(items, -2, 3)).toEqual({ pageItems: ['a', 'b', 'c'], page: 0, totalPages: 3 });
  expect(paginate(items, 99, 3)).toEqual({ pageItems: ['g'], page: 2, totalPages: 3 });
  expect(paginate(items, 2, 0)).toEqual({ pageItems: items, page: 0, totalPages: 1 });
  expect(paginate(items, 2, -5)).toEqual({ pageItems: items, page: 0, totalPages: 1 });
  expect(paginate([], 3, 5)).toEqual({ pageItems: [], page: 0, totalPages: 1 });
  expect(paginate(items, 1.9, 3)).toEqual({ pageItems: ['d', 'e', 'f'], page: 1, totalPages: 3 });
});

test('formatRelativeTime buckets boundary values against a fixed clock', () => {
  const now = new Date('2026-07-05T12:00:00.000Z');
  const ago = (milliseconds: number) => new Date(now.getTime() - milliseconds).toISOString();

  expect(formatRelativeTime(ago(10_000), now)).toBe('방금');
  expect(formatRelativeTime(ago(11_000), now)).toBe('1분 전');
  expect(formatRelativeTime(ago(59 * 60_000), now)).toBe('59분 전');
  expect(formatRelativeTime(ago(60 * 60_000), now)).toBe('1시간 전');
  expect(formatRelativeTime(ago(23 * 60 * 60_000), now)).toBe('23시간 전');
  expect(formatRelativeTime(ago(24 * 60 * 60_000), now)).toBe('1일 전');
  expect(formatRelativeTime(new Date(now.getTime() + 5_000).toISOString(), now)).toBe('방금');
  expect(formatRelativeTime('', now)).toBe('');
  expect(formatRelativeTime('not-a-date', now)).toBe('');
});

test('세션 자동 새로고침 is scoped to connected users and clears on off and unmount', async () => {
  const { unmount } = render(<AdminConsoleTabs />);

  fireEvent.click(await screen.findByRole('tab', { name: '계정' }));
  expect(await screen.findByRole('heading', { name: '접속자/세션' })).toBeInTheDocument();
  await waitFor(() => expect(api.fetchConnectedUsers).toHaveBeenCalledTimes(1));

  const initialUsersCalls = vi.mocked(api.fetchAdminUsers).mock.calls.length;
  const initialModulesCalls = vi.mocked(api.fetchServiceModulesAdmin).mock.calls.length;

  vi.useFakeTimers();
  fireEvent.click(screen.getByLabelText('세션 자동 새로고침'));
  await act(async () => {
    vi.advanceTimersByTime(15_000);
    await Promise.resolve();
  });

  expect(api.fetchConnectedUsers).toHaveBeenCalledTimes(2);
  expect(api.fetchAdminUsers).toHaveBeenCalledTimes(initialUsersCalls);
  expect(api.fetchServiceModulesAdmin).toHaveBeenCalledTimes(initialModulesCalls);

  fireEvent.click(screen.getByLabelText('세션 자동 새로고침'));
  await act(async () => {
    vi.advanceTimersByTime(30_000);
    await Promise.resolve();
  });
  expect(api.fetchConnectedUsers).toHaveBeenCalledTimes(2);

  fireEvent.click(screen.getByLabelText('세션 자동 새로고침'));
  unmount();
  await act(async () => {
    vi.advanceTimersByTime(30_000);
    await Promise.resolve();
  });
  expect(api.fetchConnectedUsers).toHaveBeenCalledTimes(2);
});

test('세션 tab paginates login events and search resets back to page 1', async () => {
  const loginEvents = makeLoginEvents(13);
  mockAdminData({
    ...connectedUsersEmpty,
    recent_login_events: loginEvents,
    login_failure_count: loginEvents.filter((event) => event.status === 'failure').length,
  });

  render(<AdminConsoleTabs />);
  fireEvent.click(await screen.findByRole('tab', { name: '계정' }));
  expect(await screen.findByRole('heading', { name: '접속자/세션' })).toBeInTheDocument();
  await waitFor(() => expect(screen.getByText('페이지 1 / 2')).toBeInTheDocument());

  for (let id = 13; id >= 4; id -= 1) {
    expect(screen.getByText(`user-${String(id).padStart(2, '0')}`)).toBeInTheDocument();
  }
  expect(screen.queryByText('user-03')).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: '이전 페이지' })).toBeDisabled();
  expect(screen.getByRole('button', { name: '다음 페이지' })).not.toBeDisabled();

  fireEvent.click(screen.getByRole('button', { name: '다음 페이지' }));
  await waitFor(() => expect(screen.getByText('페이지 2 / 2')).toBeInTheDocument());
  expect(screen.queryByText('user-13')).not.toBeInTheDocument();
  expect(screen.getByText('user-03')).toBeInTheDocument();
  expect(screen.getByText('user-02')).toBeInTheDocument();
  expect(screen.getByText('user-01')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: '다음 페이지' })).toBeDisabled();

  fireEvent.change(screen.getByLabelText('로그인 이벤트 검색'), { target: { value: 'user-13' } });
  await waitFor(() => expect(screen.getByText('페이지 1 / 1')).toBeInTheDocument());
  expect(screen.getByText('user-13')).toBeInTheDocument();
  expect(screen.queryByText('user-12')).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: '이전 페이지' })).toBeDisabled();
});

test('세션 tab distinguishes active_session_count from active_user_count', async () => {
  mockAdminData({
    ...connectedUsersEmpty,
    active_sessions: [
      { user_id: 1, username: 'operator', last_seen_at: '2026-07-05T12:00:00Z' },
      { user_id: 1, username: 'operator', last_seen_at: '2026-07-05T11:00:00Z' },
    ],
    active_session_count: 2,
    active_user_count: 1,
    active_count: 1,
  });

  render(<AdminConsoleTabs />);
  fireEvent.click(await screen.findByRole('tab', { name: '계정' }));
  expect(await screen.findByRole('heading', { name: '접속자/세션' })).toBeInTheDocument();

  expect(screen.getByText('2')).toBeInTheDocument();
  expect(screen.getByText(/세션 2건 · 접속 사용자 1명/)).toBeInTheDocument();
});

test('세션 tab shows a retry control (not zeros) when connectedUsers fetch degrades', async () => {
  vi.mocked(api.fetchConnectedUsers).mockRejectedValueOnce(new Error('세션 정보를 불러오지 못했습니다.') as never);

  render(<AdminConsoleTabs />);
  fireEvent.click(await screen.findByRole('tab', { name: '계정' }));
  expect(await screen.findByRole('heading', { name: '접속자/세션' })).toBeInTheDocument();

  const retryButton = await screen.findByRole('button', { name: '다시 시도' });
  expect(retryButton).toBeInTheDocument();
  expect(screen.getByText('로그인 실패 지표를 표시할 수 없습니다.')).toBeInTheDocument();
  expect(screen.getByText('읽음 집계를 표시할 수 없습니다.')).toBeInTheDocument();
  expect(screen.queryByText('실패 0건')).not.toBeInTheDocument();
  const activeSessionsCard = screen.getByText('활성 세션').closest('div') as HTMLElement;
  expect(within(activeSessionsCard).queryByText('0')).not.toBeInTheDocument();

  vi.mocked(api.fetchConnectedUsers).mockResolvedValue(connectedUsersEmpty as never);
  fireEvent.click(retryButton);
  await waitFor(() => expect(screen.queryByRole('button', { name: '다시 시도' })).not.toBeInTheDocument());
});

test('세션 tab does not degrade when an unrelated initial resource fails', async () => {
  mockAdminData({
    ...connectedUsersEmpty,
    active_session_count: 2,
    active_user_count: 1,
  });
  vi.mocked(api.fetchAdminUsers).mockRejectedValueOnce(new Error('사용자 목록 실패') as never);

  render(<AdminConsoleTabs />);
  fireEvent.click(await screen.findByRole('tab', { name: '계정' }));

  expect(await screen.findByText(/세션 2건 · 접속 사용자 1명/)).toBeInTheDocument();
  expect(screen.queryByText(/최신 세션 정보를 갱신하지 못했습니다/)).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: '다시 시도' })).not.toBeInTheDocument();
});

test('세션 tab preserves its own retry error when a sibling resource also fails', async () => {
  vi.mocked(api.fetchConnectedUsers).mockRejectedValueOnce(new Error('세션 결합 실패') as never);
  vi.mocked(api.fetchAdminUsers).mockRejectedValueOnce(new Error('사용자 결합 실패') as never);

  render(<AdminConsoleTabs />);
  fireEvent.click(await screen.findByRole('tab', { name: '계정' }));

  expect((await screen.findAllByText('세션 결합 실패')).length).toBeGreaterThan(0);
  expect(screen.getByRole('button', { name: '다시 시도' })).toBeInTheDocument();
  expect(screen.getAllByText('사용자 결합 실패').length).toBeGreaterThan(0);
});
test('세션 tab keeps last-good dataset with a visible degraded banner after refresh failure', async () => {
  mockAdminData({
    ...connectedUsersEmpty,
    active_session_count: 4,
    active_user_count: 2,
    login_failure_count: 3,
    read_tracking_summary: { rows: 2, total_reads: 7 },
  });
  vi.mocked(api.fetchConnectedUsers)
    .mockResolvedValueOnce({
      ...connectedUsersEmpty,
      active_session_count: 4,
      active_user_count: 2,
      login_failure_count: 3,
      read_tracking_summary: { rows: 2, total_reads: 7 },
    } as never)
    .mockRejectedValueOnce(new Error('세션 갱신 실패') as never);

  render(<AdminConsoleTabs />);
  fireEvent.click(await screen.findByRole('tab', { name: '계정' }));
  await waitFor(() => expect(screen.getByText(/세션 4건 · 접속 사용자 2명/)).toBeInTheDocument());

  vi.useFakeTimers();
  fireEvent.click(screen.getByLabelText('세션 자동 새로고침'));
  await act(async () => {
    vi.advanceTimersByTime(15_000);
    await Promise.resolve();
  });

  expect(screen.getByText(/최신 세션 정보를 갱신하지 못했습니다/)).toBeInTheDocument();
  expect(screen.getByText(/세션 4건 · 접속 사용자 2명/)).toBeInTheDocument();
  expect(screen.getByText('실패 3건')).toBeInTheDocument();
  expect(screen.getByText('7')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: '다시 시도' })).toBeInTheDocument();
});

test('세션 tab ignores an older connected-users response that finishes after a newer refresh', async () => {
  const olderRefresh = deferred<ConnectedUsersResponse>();
  vi.mocked(api.fetchConnectedUsers)
    .mockResolvedValueOnce({
      ...connectedUsersEmpty,
      active_session_count: 1,
      active_user_count: 1,
    } as never)
    .mockReturnValueOnce(olderRefresh.promise as never)
    .mockResolvedValueOnce({
      ...connectedUsersEmpty,
      active_session_count: 7,
      active_user_count: 3,
    } as never);

  render(<AdminConsoleTabs />);
  fireEvent.click(await screen.findByRole('tab', { name: '계정' }));
  expect(await screen.findByText(/세션 1건 · 접속 사용자 1명/)).toBeInTheDocument();

  vi.useFakeTimers();
  fireEvent.click(screen.getByLabelText('세션 자동 새로고침'));
  await act(async () => {
    vi.advanceTimersByTime(30_000);
    await Promise.resolve();
    await Promise.resolve();
  });
  expect(screen.getByText(/세션 7건 · 접속 사용자 3명/)).toBeInTheDocument();

  await act(async () => {
    olderRefresh.resolve({
      ...connectedUsersEmpty,
      active_session_count: 9,
      active_user_count: 4,
    });
    await Promise.resolve();
    await Promise.resolve();
  });
  expect(screen.getByText(/세션 7건 · 접속 사용자 3명/)).toBeInTheDocument();
  expect(screen.queryByText(/세션 9건 · 접속 사용자 4명/)).not.toBeInTheDocument();
});
