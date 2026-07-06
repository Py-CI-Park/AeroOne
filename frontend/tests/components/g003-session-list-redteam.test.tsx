import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { AdminConsoleTabs } from '@/components/admin/admin-console-tabs';
import { paginate } from '@/components/admin/widgets/list-filter';
import { formatRelativeTime } from '@/lib/relative-time';
import * as api from '@/lib/api';
import type { ConnectedUsersResponse, LoginEvent } from '@/lib/types';

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
    fetchAssetHealth: vi.fn(),
    fetchConfigHealth: vi.fn(),
    fetchBackups: vi.fn(),
    fetchCategories: vi.fn(),
    fetchTags: vi.fn(),
    fetchAdminAiStatus: vi.fn(),
  };
});

const connectedUsersEmpty: ConnectedUsersResponse = {
  active_sessions: [],
  active_count: 0,
  recent_login_events: [],
  login_failure_count: 0,
  read_tracking_summary: { rows: 0, total_reads: 0 },
};

function mockAdminData(connectedUsers: ConnectedUsersResponse = connectedUsersEmpty) {
  vi.mocked(api.fetchAdminSummary).mockResolvedValue({ app_version: '1.12.0', app_env: 'test', database_url: 'sqlite:///test.db', db_ok: true, newsletter_total: 0, latest_newsletter_title: null, active_modules: 0, coming_soon_modules: 0, asset_health: {}, read_summary: {}, ai_status: { status: 'ok' }, recent_audit_events: [] } as never);
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

  fireEvent.click(await screen.findByRole('tab', { name: '세션' }));
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
  fireEvent.click(await screen.findByRole('tab', { name: '세션' }));
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
