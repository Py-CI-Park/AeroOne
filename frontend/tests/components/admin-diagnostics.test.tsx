import React from 'react';
import { fireEvent, render, screen, within } from '@testing-library/react';
import { AdminNewsletterList } from '@/components/admin/admin-newsletter-list';
import { AdminHomeConsole } from '@/components/admin/admin-home-console';
import * as api from '@/lib/api';

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return {
    ...actual,
    fetchAdminNewsletters: vi.fn(),
    fetchAssetHealth: vi.fn(),
    fetchConfigHealth: vi.fn(),
    fetchAdminOverview: vi.fn(),
    fetchAdminUsers: vi.fn(),
    fetchConnectedUsers: vi.fn(),
    purgeSessions: vi.fn(),
    fetchAdminPermissions: vi.fn(),
    fetchAdminGroups: vi.fn(),
    fetchRbacMatrix: vi.fn(),
    listResourceGrants: vi.fn(),
    createResourceGrant: vi.fn(),
    deleteResourceGrant: vi.fn(),
    addUserGroup: vi.fn(),
    removeUserGroup: vi.fn(),
    fetchAuditEvents: vi.fn(),
    fetchServiceModulesAdmin: vi.fn(),
    fetchBackups: vi.fn(),
    fetchCategories: vi.fn(),
    fetchTags: vi.fn(),
    fetchAdminAiStatus: vi.fn(),
    fetchAiProviderConfig: vi.fn(),
    fetchLlmConnections: vi.fn().mockResolvedValue([]),
  };
});

const newsletters = [
  { id: 1, title: 'OK newsletter', slug: 'ok', source_type: 'html', tags: [], available_assets: [] },
  { id: 2, title: 'Missing newsletter', slug: 'missing', source_type: 'html', tags: [], available_assets: [] },
  { id: 3, title: 'Mismatch newsletter', slug: 'mismatch', source_type: 'html', tags: [], available_assets: [] },
  { id: 4, title: 'Misconfig newsletter', slug: 'misconfig', source_type: 'html', tags: [], available_assets: [] },
];

const health = {
  ok: 1,
  missing: 1,
  checksum_mismatch: 1,
  misconfig: 1,
  items: [
    { newsletter_id: 1, newsletter_title: 'OK newsletter', asset_type: 'html', file_path: 'ok.html', exists: true, ok: true, status: 'ok', root_kind: 'import', remediation: '정상입니다.' },
    { newsletter_id: 2, newsletter_title: 'Missing newsletter', asset_type: 'html', file_path: 'missing.html', exists: false, ok: false, status: 'missing', root_kind: 'import', remediation: '해석된 자산 경로에 파일이 없습니다.', resolved_path: 'D:/import/missing.html', error_code: 'FILE_NOT_FOUND' },
    { newsletter_id: 3, newsletter_title: 'Mismatch newsletter', asset_type: 'html', file_path: 'mismatch.html', exists: true, ok: false, status: 'checksum_mismatch', root_kind: 'import', remediation: '파일은 있지만 DB 체크섬과 다릅니다.', resolved_path: 'D:/import/mismatch.html', error_code: 'CHECKSUM_MISMATCH' },
    { newsletter_id: 4, newsletter_title: 'Misconfig newsletter', asset_type: 'html', file_path: 'bad.html', exists: false, ok: false, status: 'misconfig', root_kind: 'import', remediation: '루트 경로를 확인하세요. 환경변수 override 오설정을 점검하세요.', resolved_root: 'Z:/missing', error_code: 'ROOT_MISSING' },
  ],
} as const;

test('admin newsletter list renders status-specific asset diagnostics', async () => {
  vi.mocked(api.fetchAdminNewsletters).mockResolvedValue(newsletters as never);
  vi.mocked(api.fetchAssetHealth).mockResolvedValue(health as never);

  render(<AdminNewsletterList />);

  expect(await screen.findByText('OK newsletter')).toBeInTheDocument();
  expect(screen.getByText('OK')).toBeInTheDocument();
  expect(screen.getByText('파일 없음')).toBeInTheDocument();
  expect(screen.getByText('체크섬 불일치')).toBeInTheDocument();
  expect(screen.getByText('설정 오류')).toBeInTheDocument();
  expect(screen.getAllByText('점검 필요 = DB 자산을 해석된 루트/경로에서 검증할 수 없음.')).toHaveLength(3);
  expect(screen.getByText('D:/import/missing.html')).toBeInTheDocument();
  expect(screen.getByText('Z:/missing')).toBeInTheDocument();
});

test('admin home console lists config-health roots', async () => {
  vi.mocked(api.fetchAdminOverview).mockResolvedValue({
    generated_at: '2026-07-04T00:00:00Z',
    anchor: '2026-06-27T00:00:00Z',
    users: { total: 1, active: 1, inactive: 0, roles: { admin: 1, user: 0, pending: 0 }, created: { current: 0, prior: 0, delta: 0 } },
    logins: { success: { current: 1, prior: 0, delta: 1 }, failure: { current: 1, prior: 0, delta: 1 }, logout: { current: 0, prior: 0, delta: 0 } },
    ai: { total: { current: 0, prior: 0, delta: 0 }, failure: { current: 0, prior: 0, delta: 0 } },
    sessions: { active_session_count: 1, active_user_count: 1, active_count: 1 },
    modules: { total: 0, buckets: { unavailable: [], coming: [], development: [], active: [] } },
    system: { app_version: '1.9.0', app_env: 'test', database_kind: 'sqlite', newsletter_count: 0, asset_health: { ok: 0, missing: 0, checksum_mismatch: 0, misconfig: 0 }, read_summary: { rows: 0, total_reads: 0 } },
    recent_audit: [],
  } as never);
  vi.mocked(api.fetchAdminUsers).mockResolvedValue([] as never);
  vi.mocked(api.fetchConnectedUsers).mockResolvedValue({ active_sessions: [{ user_id: 1, username: 'admin', last_seen_at: '2026-07-04T00:00:00Z' }], active_count: 1, recent_login_events: [{ id: 1, user_id: 1, username: 'admin', status: 'success', created_at: '2026-07-04T00:00:00Z' }, { id: 2, user_id: null, username: 'admin', status: 'failure', created_at: '2026-07-04T00:01:00Z' }], login_failure_count: 1, read_tracking_summary: { rows: 2, total_reads: 7 } } as never);
  vi.mocked(api.fetchAdminPermissions).mockResolvedValue([] as never);
  vi.mocked(api.fetchAdminGroups).mockResolvedValue([{ id: 2, key: 'nsa-readers', name: 'NSA Readers', is_active: true, permissions: ['collections.nsa.read'] }] as never);
  vi.mocked(api.fetchRbacMatrix).mockResolvedValue([{ user_id: 9, username: 'operator', role: 'user', role_permissions: ['ai.use'], direct_permissions: ['search.use'], group_permissions: [{ group: 'nsa-readers', key: 'collections.nsa.read' }], effective_permissions: [{ key: 'ai.use', sources: ['role:user'] }, { key: 'search.use', sources: ['direct'] }, { key: 'collections.nsa.read', sources: ['group:nsa-readers'] }], resource_grants: [{ resource_type: 'collection', resource_id: 'nsa', permission_key: 'collections.nsa.read', source: 'group:nsa-readers' }] }] as never);
  vi.mocked(api.listResourceGrants).mockResolvedValue([{ id: 4, subject_type: 'group', subject_id: 2, resource_type: 'collection', resource_id: 'nsa', permission_key: 'collections.nsa.read' }] as never);
  vi.mocked(api.fetchAuditEvents).mockResolvedValue([] as never);
  vi.mocked(api.fetchServiceModulesAdmin).mockResolvedValue([] as never);
  vi.mocked(api.fetchAssetHealth).mockResolvedValue(health as never);
  vi.mocked(api.fetchConfigHealth).mockResolvedValue({ roots: [
    { kind: 'import', resolved_path: 'D:/_database/newsletter', exists: true, readable: true },
    { kind: 'markdown', resolved_path: 'D:/storage/markdown/newsletters', exists: false, readable: false },
  ] } as never);
  vi.mocked(api.fetchBackups).mockResolvedValue([] as never);
  vi.mocked(api.fetchCategories).mockResolvedValue([] as never);
  vi.mocked(api.fetchTags).mockResolvedValue([] as never);
  vi.mocked(api.fetchAdminAiStatus).mockResolvedValue({ status: {}, request_logs_total: 0, request_failures: 0 } as never);
  vi.mocked(api.fetchAiProviderConfig).mockResolvedValue({ selected_kind: 'ollama', compatible_state: 'absent', compatible_display_url: null, compatible_model: null, compatible_generation: null, compatible_test_proof_at: null, compatible_test_proof_model: null, config_version: 1, updated_at: '2026-07-04T00:00:00Z' } as never);

  render(<AdminHomeConsole />);

  fireEvent.click(await screen.findByRole('tab', { name: '시스템' }));
  const panel = await screen.findByText('DB/자산 경로 상태');
  const section = panel.closest('section')!;
  expect(within(section).getByText('import')).toBeInTheDocument();
  expect(within(section).getByText('D:/_database/newsletter')).toBeInTheDocument();
  expect(within(section).getByText('markdown')).toBeInTheDocument();
  expect(within(section).getByText('D:/storage/markdown/newsletters')).toBeInTheDocument();
  expect(within(section).getByText('exists false · readable false')).toBeInTheDocument();

  fireEvent.click(screen.getByRole('tab', { name: '세션' }));
  expect(await screen.findByText('접속자/세션')).toBeInTheDocument();
  expect(screen.getByText('익명 읽음 추적')).toBeInTheDocument();
  expect(screen.getByText('IP/뉴스레터 집계 행 2개')).toBeInTheDocument();

  fireEvent.click(screen.getByRole('tab', { name: 'RBAC' }));
  expect(await screen.findByText('RBAC 매트릭스 / 리소스 권한')).toBeInTheDocument();
  expect(screen.getAllByText(/operator/).length).toBeGreaterThan(0);
  expect(screen.getAllByText('collections.nsa.read').length).toBeGreaterThan(0);
  expect(screen.getAllByText(/출처 group:nsa-readers/).length).toBeGreaterThan(0);
});
