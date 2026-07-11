import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { AdminConsoleTabs } from '@/components/admin/admin-console-tabs';
import { buildAuditCsv } from '@/components/admin/sections/admin-audit-section';
import * as api from '@/lib/api';

function readBlobText(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsText(blob);
  });
}

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
    fetchLlmConnections: vi.fn().mockResolvedValue([]),
  };
});

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.fetchAdminSummary).mockResolvedValue({ app_version: '1.12.0', app_env: 'test', database_url: 'sqlite:///test.db', db_ok: true, newsletter_total: 0, latest_newsletter_title: null, active_modules: 0, coming_soon_modules: 0, asset_health: {}, read_summary: {}, ai_status: { status: 'ok' }, recent_audit_events: [] } as never);
  vi.mocked(api.fetchAdminUsers).mockResolvedValue([] as never);
  vi.mocked(api.fetchConnectedUsers).mockResolvedValue({ active_sessions: [], active_count: 0, recent_login_events: [], login_failure_count: 0, read_tracking_summary: { rows: 0, total_reads: 0 } } as never);
  vi.mocked(api.fetchAdminPermissions).mockResolvedValue([] as never);
  vi.mocked(api.fetchAdminGroups).mockResolvedValue([] as never);
  vi.mocked(api.fetchRbacMatrix).mockResolvedValue([] as never);
  vi.mocked(api.listResourceGrants).mockResolvedValue([] as never);
  vi.mocked(api.fetchAuditEvents).mockResolvedValue([
    { id: 1, actor_username: 'operator', actor_role: 'admin', action: 'backup.create', target_type: 'backup', target_id: '1', status: 'success', ip_address: '10.0.0.1', created_at: '2026-07-05T00:00:00Z' },
    { id: 2, actor_username: 'analyst', actor_role: 'user', action: 'user.update', target_type: 'user', target_id: '2', status: 'failed', ip_address: '10.0.0.2', created_at: '2026-07-03T00:00:00Z' },
    { id: 3, actor_username: null, actor_role: null, action: 'session.purge', target_type: 'session', target_id: null, status: 'success', ip_address: null, created_at: '2026-07-01T00:00:00Z' },
  ] as never);
  vi.mocked(api.fetchServiceModulesAdmin).mockResolvedValue([] as never);
  vi.mocked(api.fetchAssetHealth).mockResolvedValue({ ok: 0, missing: 0, checksum_mismatch: 0, misconfig: 0, items: [] } as never);
  vi.mocked(api.fetchConfigHealth).mockResolvedValue({ roots: [] } as never);
  vi.mocked(api.fetchBackups).mockResolvedValue([] as never);
  vi.mocked(api.fetchCategories).mockResolvedValue([] as never);
  vi.mocked(api.fetchTags).mockResolvedValue([] as never);
  vi.mocked(api.fetchAdminAiStatus).mockResolvedValue({ status: { ok: true }, request_logs_total: 0, request_failures: 0 } as never);
});

test('AdminAuditSection renders audits and narrows by search, status, and period', async () => {
  render(<AdminConsoleTabs />);

  fireEvent.click(await screen.findByRole('tab', { name: '감사' }));
  expect(await screen.findByRole('heading', { name: '감사 로그' })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: '현재 결과 CSV 내보내기' })).toBeInTheDocument();
  expect(screen.getByLabelText('감사 검색')).toBeInTheDocument();
  expect(screen.getByText('backup.create')).toBeInTheDocument();
  expect(screen.getByText('user.update')).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText('감사 검색'), { target: { value: 'backup' } });
  expect(screen.getByText('backup.create')).toBeInTheDocument();
  expect(screen.queryByText('user.update')).not.toBeInTheDocument();
  expect(screen.getByText('결과 1 / 3건')).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText('감사 검색'), { target: { value: '' } });
  fireEvent.change(screen.getByLabelText('감사 상태 필터'), { target: { value: 'failed' } });
  expect(screen.getByText('user.update')).toBeInTheDocument();
  expect(screen.queryByText('backup.create')).not.toBeInTheDocument();

  fireEvent.change(screen.getByLabelText('감사 상태 필터'), { target: { value: '' } });
  fireEvent.change(screen.getByLabelText('감사 기간 시작'), { target: { value: '2026-07-02' } });
  fireEvent.change(screen.getByLabelText('감사 기간 끝'), { target: { value: '2026-07-04' } });
  expect(screen.getByText('user.update')).toBeInTheDocument();
  expect(screen.queryByText('backup.create')).not.toBeInTheDocument();
  expect(screen.queryByText('session.purge')).not.toBeInTheDocument();
});

test('AdminAuditSection CSV button exports current filtered audits', async () => {
  const createObjectURL = vi.fn((_blob: Blob) => 'blob:audit');
  const revokeObjectURL = vi.fn();
  Object.defineProperty(window.URL, 'createObjectURL', { configurable: true, value: createObjectURL });
  Object.defineProperty(window.URL, 'revokeObjectURL', { configurable: true, value: revokeObjectURL });

  render(<AdminConsoleTabs />);
  fireEvent.click(await screen.findByRole('tab', { name: '감사' }));
  await screen.findByRole('heading', { name: '감사 로그' });
  fireEvent.change(screen.getByLabelText('감사 검색'), { target: { value: 'backup' } });
  fireEvent.click(screen.getByRole('button', { name: '현재 결과 CSV 내보내기' }));

  await waitFor(() => expect(createObjectURL).toHaveBeenCalledTimes(1));
  const exportedBlob = createObjectURL.mock.calls[0][0];
  expect(exportedBlob).toBeInstanceOf(Blob);
  const exportedText = await readBlobText(exportedBlob);
  expect(exportedText.split('\n')[0]).toBe('id,actor_username,actor_role,action,target_type,target_id,status,ip_address,created_at');
  expect(exportedText).toContain('backup.create');
  expect(exportedText).not.toContain('user.update');
  expect(exportedText).not.toContain('session.purge');
  expect(revokeObjectURL).toHaveBeenCalledWith('blob:audit');
});

test('buildAuditCsv writes exact header and escapes comma and quote fields', () => {
  expect(buildAuditCsv([
    { id: 9, actor_username: 'op,erator', actor_role: 'admin', action: 'backup."create"', target_type: 'backup', target_id: null, status: 'success', ip_address: undefined, created_at: '2026-07-05T00:00:00Z' },
  ])).toBe('id,actor_username,actor_role,action,target_type,target_id,status,ip_address,created_at\n9,"op,erator",admin,"backup.""create""",backup,,success,,2026-07-05T00:00:00Z');
});


test('buildAuditCsv quotes newline and empty-input returns header only', () => {
  expect(buildAuditCsv([])).toBe('id,actor_username,actor_role,action,target_type,target_id,status,ip_address,created_at');
  const expected = [
    'id,actor_username,actor_role,action,target_type,target_id,status,ip_address,created_at',
    '5,"a\nb",,x,t,"r""q",ok,,2026-07-05T00:00:00Z',
  ].join('\n');
  expect(buildAuditCsv([
    { id: 5, actor_username: 'a\nb', actor_role: null, action: 'x', target_type: 't', target_id: 'r"q', status: 'ok', ip_address: null, created_at: '2026-07-05T00:00:00Z' },
  ])).toBe(expected);
});
