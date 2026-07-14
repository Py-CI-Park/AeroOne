import React from 'react';
import { fireEvent, render, screen, within } from '@testing-library/react';
import { AdminConsoleTabs } from '@/components/admin/admin-console-tabs';
import { buildAuditCsv } from '@/components/admin/sections/admin-audit-section';
import type { AuditEvent } from '@/lib/types';
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
    fetchAiProviderConfig: vi.fn(),
    fetchLlmConnections: vi.fn().mockResolvedValue([]),
  };
});

const csvHeader = 'id,actor_username,actor_role,action,target_type,target_id,status,ip_address,created_at';

const auditEvents: AuditEvent[] = [
  { id: 101, actor_username: 'operator', actor_role: 'admin', action: 'backup.create', target_type: 'backup', target_id: 'bk-1', status: 'success', ip_address: '10.0.0.1', created_at: '2026-07-05T10:00:00Z' },
  { id: 102, actor_username: 'analyst', actor_role: 'user', action: 'user.update', target_type: 'user', target_id: 'u-2', status: 'failed', ip_address: '10.0.0.2', created_at: '2026-07-04T09:00:00Z' },
  { id: 103, actor_username: 'operator', actor_role: 'admin', action: 'session.purge', target_type: 'session', target_id: null, status: 'success', ip_address: '10.0.0.3', created_at: '2026-07-03T08:00:00Z' },
  { id: 104, actor_username: 'viewer', actor_role: 'auditor', action: 'audit.export', target_type: 'audit', target_id: 'exp-1', status: 'queued', ip_address: null, created_at: '2026-07-02T07:00:00Z' },
];

function parseCsvRecord(record: string) {
  const cells: string[] = [];
  let cell = '';
  let quoted = false;
  for (let index = 0; index < record.length; index += 1) {
    const char = record[index];
    const next = record[index + 1];
    if (char === '"' && quoted && next === '"') {
      cell += '"';
      index += 1;
    } else if (char === '"') {
      quoted = !quoted;
    } else if (char === ',' && !quoted) {
      cells.push(cell);
      cell = '';
    } else {
      cell += char;
    }
  }
  cells.push(cell);
  return cells;
}

function mockAdminData() {
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
  vi.mocked(api.fetchAuditEvents).mockResolvedValue(auditEvents as never);
  vi.mocked(api.fetchServiceModulesAdmin).mockResolvedValue([] as never);
  vi.mocked(api.fetchAssetHealth).mockResolvedValue({ ok: 0, missing: 0, checksum_mismatch: 0, misconfig: 0, items: [] } as never);
  vi.mocked(api.fetchConfigHealth).mockResolvedValue({ roots: [] } as never);
  vi.mocked(api.fetchBackups).mockResolvedValue([{ id: 201, filename: 'admin-backup.zip', sha256: 'abcdef1234567890', file_size: 4096, status: 'created', created_at: '2026-07-05T11:00:00Z' }] as never);
  vi.mocked(api.fetchCategories).mockResolvedValue([] as never);
  vi.mocked(api.fetchTags).mockResolvedValue([] as never);
  vi.mocked(api.fetchAdminAiStatus).mockResolvedValue({ status: { ok: true }, request_logs_total: 0, request_failures: 0 } as never);
}

beforeEach(() => {
  vi.clearAllMocks();
  mockAdminData();
});

test('buildAuditCsv resists import-corrupting escaping edge cases', () => {
  const csv = buildAuditCsv([
    { id: 42, actor_username: 'comma, "quote"\nline', actor_role: undefined, action: 'audit.export', target_type: 'audit', target_id: null, status: 'success', ip_address: '127.0.0.1', created_at: '2026-07-05T00:00:00Z' },
    { id: 43, actor_username: 'plain', actor_role: 'role"x', action: 'line\rbreak', target_type: 'target,kind', target_id: undefined, status: 'failed', ip_address: null, created_at: '2026-07-06T00:00:00Z' },
  ]);

  expect(csv.startsWith(`${csvHeader}\n`)).toBe(true);
  expect(csv).toContain('42,"comma, ""quote""\nline",,audit.export,audit,,success,127.0.0.1,2026-07-05T00:00:00Z');
  expect(csv).toContain('43,plain,"role""x","line\rbreak","target,kind",,failed,,2026-07-06T00:00:00Z');

  const firstRecord = csv.slice(csvHeader.length + 1, csv.indexOf('\n43,'));
  expect(parseCsvRecord(firstRecord)).toEqual(['42', 'comma, "quote"\nline', '', 'audit.export', 'audit', '', 'success', '127.0.0.1', '2026-07-05T00:00:00Z']);
});

test('buildAuditCsv returns only the header for an empty audit list', () => {
  expect(buildAuditCsv([])).toBe(csvHeader);
});

test('AdminAuditSection composes status, period, and search filters inside the 감사 tab', async () => {
  render(<AdminConsoleTabs />);

  fireEvent.click(await screen.findByRole('tab', { name: '감사' }));
  expect(await screen.findByRole('heading', { name: '감사 로그' })).toBeInTheDocument();
  expect(screen.getByText('결과 4 / 4건')).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText('감사 상태 필터'), { target: { value: 'failed' } });
  expect(screen.getByText('user.update')).toBeInTheDocument();
  expect(screen.queryByText('backup.create')).not.toBeInTheDocument();
  expect(screen.queryByText('session.purge')).not.toBeInTheDocument();
  expect(screen.getByText('결과 1 / 4건')).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText('감사 상태 필터'), { target: { value: '' } });
  fireEvent.change(screen.getByLabelText('감사 기간 시작'), { target: { value: '2026-07-03' } });
  fireEvent.change(screen.getByLabelText('감사 기간 끝'), { target: { value: '2026-07-04' } });
  expect(screen.getByText('user.update')).toBeInTheDocument();
  expect(screen.getByText('session.purge')).toBeInTheDocument();
  expect(screen.queryByText('backup.create')).not.toBeInTheDocument();
  expect(screen.queryByText('audit.export')).not.toBeInTheDocument();
  expect(screen.getByText('결과 2 / 4건')).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText('감사 기간 시작'), { target: { value: '' } });
  fireEvent.change(screen.getByLabelText('감사 기간 끝'), { target: { value: '' } });
  fireEvent.change(screen.getByLabelText('감사 검색'), { target: { value: 'operator' } });
  expect(screen.getByText('backup.create')).toBeInTheDocument();
  expect(screen.getByText('session.purge')).toBeInTheDocument();
  expect(screen.queryByText('user.update')).not.toBeInTheDocument();
  expect(screen.getByText('결과 2 / 4건')).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText('감사 검색'), { target: { value: 'backup' } });
  expect(screen.getByText('backup.create')).toBeInTheDocument();
  expect(screen.queryByText('session.purge')).not.toBeInTheDocument();
  expect(screen.getByText('결과 1 / 4건')).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText('감사 상태 필터'), { target: { value: 'failed' } });
  expect(screen.queryByText('backup.create')).not.toBeInTheDocument();
  expect(screen.queryByText('user.update')).not.toBeInTheDocument();
  expect(screen.getByText('검색 조건에 맞는 감사 이벤트가 없습니다.')).toBeInTheDocument();
  expect(screen.getByText('결과 0 / 4건')).toBeInTheDocument();
});

test('백업 tab does not duplicate the audit log list and keeps a pointer to the 감사 tab', async () => {
  render(<AdminConsoleTabs />);

  fireEvent.click(await screen.findByRole('tab', { name: '백업' }));
  const backupPanel = await screen.findByRole('tabpanel', { name: '백업' });

  expect(within(backupPanel).getByRole('heading', { name: '백업' })).toBeInTheDocument();
  expect(within(backupPanel).getByRole('button', { name: '백업 생성' })).toBeInTheDocument();
  expect(within(backupPanel).getByText('admin-backup.zip')).toBeInTheDocument();
  expect(within(backupPanel).getByText("감사 로그는 '감사' 탭에서 필터·CSV로 확인하세요.")).toBeInTheDocument();

  expect(within(backupPanel).queryByText('최근 감사 로그')).not.toBeInTheDocument();
  expect(within(backupPanel).queryByText('backup.create')).not.toBeInTheDocument();
  expect(within(backupPanel).queryByText('user.update')).not.toBeInTheDocument();
  expect(within(backupPanel).queryByText('session.purge')).not.toBeInTheDocument();
});
