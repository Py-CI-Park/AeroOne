import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { AdminConsoleTabs } from '@/components/admin/admin-console-tabs';
import * as api from '@/lib/api';
import type { AdminOverviewResponse } from '@/lib/types';

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

const overviewFixture: AdminOverviewResponse = {
  generated_at: '2026-07-12T00:00:00Z',
  anchor: '2026-07-05T00:00:00Z',
  users: {
    total: 12,
    active: 10,
    inactive: 2,
    roles: { admin: 3, user: 8, pending: 1 },
    created: { current: 2, prior: 1, delta: 1 },
  },
  logins: {
    success: { current: 20, prior: 15, delta: 5 },
    failure: { current: 2, prior: 3, delta: -1 },
    logout: { current: 18, prior: 14, delta: 4 },
  },
  ai: {
    total: { current: 50, prior: 40, delta: 10 },
    failure: { current: 1, prior: 2, delta: -1 },
  },
  sessions: { active_session_count: 4, active_user_count: 3, active_count: 3 },
  modules: {
    total: 4,
    buckets: {
      unavailable: [{ key: 'legacy-portal', label: 'Legacy Portal' }],
      coming: [{ key: 'beta-lab', label: 'Beta Lab' }],
      development: [{ key: 'dev-console', label: 'Dev Console' }],
      active: [{ key: 'dashboard', label: 'Dashboard' }],
    },
  },
  system: {
    app_version: '1.13.0',
    app_env: 'test',
    database_kind: 'sqlite',
    newsletter_count: 5,
    asset_health: { ok: 4, missing: 1, checksum_mismatch: 0, misconfig: 0 },
    read_summary: { rows: 6, total_reads: 42 },
  },
  recent_audit: Array.from({ length: 11 }, (_, index) => ({
    id: index + 1,
    action: `overview.audit.${index + 1}`,
    target_type: index % 2 === 0 ? 'backup' : null,
    status: index === 0 ? 'failed' : 'success',
    created_at: `2026-07-0${(index % 9) + 1}T00:00:00Z`,
  })),
};

function mockAdminData(overview: AdminOverviewResponse = overviewFixture) {
  vi.mocked(api.fetchAdminOverview).mockResolvedValue(overview as never);
  vi.mocked(api.fetchAdminUsers).mockResolvedValue([] as never);
  vi.mocked(api.fetchConnectedUsers).mockResolvedValue({ active_sessions: [], active_session_count: 0, active_user_count: 0, active_count: 0, recent_login_events: [], login_failure_count: 0, read_tracking_summary: { rows: 0, total_reads: 0 } } as never);
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

beforeEach(() => {
  vi.clearAllMocks();
});

test('AdminOverviewSection renders 사용자/로그인/AI/세션/모듈/시스템/최근 감사 from a realistic AdminOverviewResponse', async () => {
  mockAdminData();
  render(<AdminConsoleTabs />);

  expect(await screen.findByText('사용자 통계')).toBeInTheDocument();
  expect(screen.getByText('12')).toBeInTheDocument();
  expect(screen.getByText('활성 10 · 비활성 2')).toBeInTheDocument();
  expect(screen.getByText('admin 3')).toBeInTheDocument();
  expect(screen.getByText('user 8 · pending 1')).toBeInTheDocument();
  expect(screen.getByText('이전 1명 · +1명')).toBeInTheDocument();

  expect(screen.getByText('로그인 활동 (24h)')).toBeInTheDocument();
  expect(screen.getByText('20')).toBeInTheDocument();
  expect(screen.getByText('이전 15건 · +5건')).toBeInTheDocument();
  expect(screen.getByText('이전 3건 · -1건')).toBeInTheDocument();

  expect(screen.getByText('AI 요청')).toBeInTheDocument();
  expect(screen.getByText('50')).toBeInTheDocument();
  expect(screen.getByText('이전 40건 · +10건')).toBeInTheDocument();

  expect(screen.getByText('4 / 3')).toBeInTheDocument();

  expect(screen.getByText('모듈 게이트 현황')).toBeInTheDocument();
  expect(screen.getByText('이용 불가')).toBeInTheDocument();
  expect(screen.getByText('Legacy Portal')).toBeInTheDocument();
  expect(screen.getByText('예정')).toBeInTheDocument();
  expect(screen.getByText('Beta Lab')).toBeInTheDocument();
  expect(screen.getByText('개발 중')).toBeInTheDocument();
  expect(screen.getByText('Dev Console')).toBeInTheDocument();
  expect(screen.getByText('활성')).toBeInTheDocument();
  expect(screen.getByText('Dashboard')).toBeInTheDocument();

  expect(screen.getByRole('heading', { name: '시스템' })).toBeInTheDocument();
  expect(screen.getByText('v1.13.0')).toBeInTheDocument();
  expect(screen.getByText('sqlite')).toBeInTheDocument();
  expect(screen.getByText('4 OK')).toBeInTheDocument();
  expect(screen.getByText('누락 1 · checksum 0 · 설정 0')).toBeInTheDocument();
  expect(screen.getByText('행 6개')).toBeInTheDocument();
  expect(screen.queryByText(/sqlite:\/\//)).not.toBeInTheDocument();
  expect(screen.queryByText(/database_url/i)).not.toBeInTheDocument();

  expect(screen.getByText('최근 감사 (최대 10건)')).toBeInTheDocument();
  expect(screen.getByText('overview.audit.1')).toBeInTheDocument();
  expect(screen.getByText('overview.audit.10')).toBeInTheDocument();
  expect(screen.queryByText('overview.audit.11')).not.toBeInTheDocument();
});

test('AdminOverviewSection unavailable bucket lists first among module buckets', async () => {
  mockAdminData();
  render(<AdminConsoleTabs />);

  await screen.findByText('모듈 게이트 현황');
  const bucketTitles = screen.getAllByText(/^(이용 불가|예정|개발 중|활성)$/).map((element) => element.textContent);
  expect(bucketTitles).toEqual(['이용 불가', '예정', '개발 중', '활성']);
});

test('AdminOverviewSection shows an empty-bucket placeholder without throwing when a module bucket has no entries', async () => {
  mockAdminData({
    ...overviewFixture,
    modules: { total: 1, buckets: { unavailable: [], coming: [], development: [], active: [{ key: 'dashboard', label: 'Dashboard' }] } },
  });
  render(<AdminConsoleTabs />);

  await screen.findByText('모듈 게이트 현황');
  expect(screen.getAllByText('없음').length).toBeGreaterThanOrEqual(3);
});

test('AdminOverviewSection surfaces a degraded state with the error message when overview fetch fails, instead of rendering stale stats', async () => {
  vi.mocked(api.fetchAdminOverview).mockRejectedValue(new Error('개요를 불러오지 못했습니다.') as never);
  vi.mocked(api.fetchAdminUsers).mockResolvedValue([] as never);
  vi.mocked(api.fetchConnectedUsers).mockResolvedValue({ active_sessions: [], active_session_count: 0, active_user_count: 0, active_count: 0, recent_login_events: [], login_failure_count: 0, read_tracking_summary: { rows: 0, total_reads: 0 } } as never);
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

  render(<AdminConsoleTabs />);

  const alerts = await screen.findAllByRole('alert');
  expect(alerts.some((element) => element.textContent === '개요를 불러오지 못했습니다.')).toBe(true);
  expect(screen.queryByText('사용자 통계')).not.toBeInTheDocument();
});

test('AdminOverviewSection tolerates an empty recent_audit list without throwing', async () => {
  mockAdminData({ ...overviewFixture, recent_audit: [] });
  render(<AdminConsoleTabs />);

  await screen.findByText('최근 감사 (최대 10건)');
  expect(screen.getByText('최근 감사 이벤트가 없습니다.')).toBeInTheDocument();
});
