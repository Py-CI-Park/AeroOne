import React from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { AdminConsoleTabs } from '@/components/admin/admin-console-tabs';
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
    fetchUnifiedSearch: vi.fn(),
    createServiceModule: vi.fn(),
    updateServiceModule: vi.fn(),
    deleteServiceModule: vi.fn(),
    fetchAssetHealth: vi.fn(),
    fetchConfigHealth: vi.fn(),
    fetchBackups: vi.fn(),
    fetchCategories: vi.fn(),
    fetchTags: vi.fn(),
    fetchAdminAiStatus: vi.fn(),
    fetchLlmConnections: vi.fn().mockResolvedValue([]),
    updateAdminUser: vi.fn(),
    resetAdminUserPassword: vi.fn(),
    createAdminUser: vi.fn(),
    upsertAdminGroup: vi.fn(),
    createResourceGrant: vi.fn(),
    deleteResourceGrant: vi.fn(),
    addUserGroup: vi.fn(),
    removeUserGroup: vi.fn(),
  };
});

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.fetchAdminSummary).mockResolvedValue({ app_version: '1.11.0', app_env: 'test', database_url: 'sqlite:///test.db', db_ok: true, newsletter_total: 1, latest_newsletter_title: '최근 뉴스', active_modules: 3, coming_soon_modules: 0, asset_health: {}, read_summary: {}, ai_status: { status: 'ok' }, recent_audit_events: [] } as never);
  vi.mocked(api.fetchAdminUsers).mockResolvedValue([
    { id: 3, username: 'operator', email: 'op@example.com', role: 'admin', is_active: true, permissions: ['admin.read'] },
    { id: 1, username: 'analyst', email: 'analyst@example.com', role: 'user', is_active: true, permissions: [] },
    { id: 2, username: 'alpha', email: 'alpha@example.com', role: 'admin', is_active: true, permissions: ['admin.read'] },
  ] as never);
  vi.mocked(api.fetchConnectedUsers).mockResolvedValue({ active_sessions: [], active_count: 0, recent_login_events: [], login_failure_count: 0, read_tracking_summary: { rows: 0, total_reads: 0 } } as never);
  vi.mocked(api.fetchAdminPermissions).mockResolvedValue([{ key: 'admin.read', description: 'Admin read' }, { key: 'collections.nsa.read', description: 'NSA read' }] as never);
  vi.mocked(api.fetchAdminGroups).mockResolvedValue([
    { id: 2, key: 'ops', name: 'Operators', description: 'Operations team', is_active: true, permissions: ['admin.read'] },
    { id: 1, key: 'audit', name: 'Auditors', description: 'Audit team', is_active: true, permissions: [] },
    { id: 3, key: 'aaa', name: 'Operators', description: 'Name tie', is_active: true, permissions: ['collections.nsa.read'] },
  ] as never);
  vi.mocked(api.fetchRbacMatrix).mockResolvedValue([{ user_id: 3, username: 'operator', role: 'admin', role_permissions: [], direct_permissions: ['admin.read'], group_permissions: [], effective_permissions: [{ key: 'admin.read', sources: ['direct'] }], resource_grants: [] }] as never);
  vi.mocked(api.listResourceGrants).mockResolvedValue([
    { id: 2, subject_type: 'group', subject_id: 2, resource_type: 'collection', resource_id: 'zeta', permission_key: 'collections.zeta.read' },
    { id: 1, subject_type: 'group', subject_id: 2, resource_type: 'collection', resource_id: 'alpha', permission_key: 'collections.alpha.read' },
    { id: 3, subject_type: 'user', subject_id: 3, resource_type: 'document', resource_id: 'finance', permission_key: 'documents.finance.read' },
  ] as never);
  vi.mocked(api.fetchAuditEvents).mockResolvedValue([] as never);
  vi.mocked(api.fetchServiceModulesAdmin).mockResolvedValue([
    { id: 5, key: 'dashboard', title: 'Dashboard', description: 'Main', href: '/', section: 'Core', status: 'active', badge: 'Live', sort_order: 2, is_enabled: true, is_external: false, visibility: 'admin' },
    { id: 6, key: 'analytics', title: 'Analytics', description: 'Reports', href: '/analytics', section: 'Core', status: 'active', badge: 'New', sort_order: 1, is_enabled: true, is_external: false, visibility: 'admin' },
    { id: 7, key: 'alpha', title: 'Alpha Module', description: 'Tie break', href: '/alpha', section: 'Core', status: 'active', badge: '', sort_order: 2, is_enabled: true, is_external: false, visibility: 'admin' },
  ] as never);
  vi.mocked(api.fetchAssetHealth).mockResolvedValue({ ok: 1, missing: 0, checksum_mismatch: 0, misconfig: 0, items: [] } as never);
  vi.mocked(api.fetchConfigHealth).mockResolvedValue({ roots: [] } as never);
  vi.mocked(api.fetchBackups).mockResolvedValue([] as never);
  vi.mocked(api.fetchCategories).mockResolvedValue([] as never);
  vi.mocked(api.fetchTags).mockResolvedValue([] as never);
  vi.mocked(api.fetchAdminAiStatus).mockResolvedValue({ status: { ok: true }, request_logs_total: 0, request_failures: 0 } as never);
  vi.mocked(api.fetchUnifiedSearch).mockResolvedValue({
    results: [
      { source: 'newsletter', title: 'Zulu Alert', snippet: 'civil update', url: '/news/zulu', score: 0.8 },
      { source: 'document', title: 'Bravo Manual', snippet: 'maintenance', url: '/docs/bravo', score: 0.9 },
      { source: 'document', title: 'Alpha Manual', snippet: 'aircraft snippet', url: '/docs/alpha', score: 0.7 },
    ],
  } as never);
  vi.mocked(api.createServiceModule).mockResolvedValue({} as never);
});

function expectInDocumentOrder(elements: HTMLElement[]) {
  for (let index = 0; index < elements.length - 1; index += 1) {
    expect(elements[index].compareDocumentPosition(elements[index + 1]) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  }
}

function groupNameText(text: string) {
  return screen.getAllByText(text).find((element) => element.tagName.toLowerCase() === 'strong') as HTMLElement;
}

function grantRowText(text: string) {
  return screen.getByText((_, element) => element?.textContent === text);
}

test('admin list UX adversarially preserves filtering, deterministic sorting, states, row actions, and a11y across representative tabs', async () => {
  render(<AdminConsoleTabs />);

  const modulesTab = await screen.findByRole('tab', { name: '모듈' });
  const usersTab = screen.getByRole('tab', { name: '사용자' });
  const rbacTab = screen.getByRole('tab', { name: 'RBAC' });

  expect(screen.getByRole('tablist', { name: '관리자 콘솔 탭' })).toBeInTheDocument();
  expect(modulesTab).toHaveAttribute('aria-selected', 'true');
  expect(usersTab).toHaveAttribute('aria-selected', 'false');
  expect(screen.getByRole('tabpanel', { name: '모듈' })).toBeInTheDocument();

  expectInDocumentOrder([screen.getByText('analytics'), screen.getByText('alpha'), screen.getByText('dashboard')]);
  fireEvent.change(screen.getByLabelText('모듈 정렬'), { target: { value: 'key-desc' } });
  expectInDocumentOrder([screen.getByText('dashboard'), screen.getByText('analytics'), screen.getByText('alpha')]);
  fireEvent.change(screen.getByLabelText('모듈 검색'), { target: { value: 'dash' } });
  expect(screen.getByText('dashboard')).toBeInTheDocument();
  expect(screen.queryByText('analytics')).not.toBeInTheDocument();
  expect(screen.getByText('결과 1 / 3건')).toBeInTheDocument();
  expect(within(screen.getByText('dashboard').closest('div[class*="rounded-lg"]') as HTMLElement).getByRole('button', { name: '저장' })).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('모듈 검색'), { target: { value: 'no-module-match' } });
  expect(screen.getByText('검색 조건에 맞는 모듈이 없습니다.')).toBeInTheDocument();

  fireEvent.click(usersTab);
  expect(await screen.findByRole('tabpanel', { name: '사용자' })).toBeInTheDocument();
  expect(usersTab).toHaveAttribute('aria-selected', 'true');
  expect(modulesTab).toHaveAttribute('aria-selected', 'false');
  expectInDocumentOrder([screen.getByText('alpha'), screen.getByText('analyst'), screen.getByText('operator')]);
  fireEvent.change(screen.getByLabelText('사용자 정렬'), { target: { value: 'role-asc' } });
  expectInDocumentOrder([screen.getByText('alpha'), screen.getByText('operator'), screen.getByText('analyst')]);
  fireEvent.change(screen.getByLabelText('사용자 검색'), { target: { value: 'analyst' } });
  expect(screen.getByText('analyst')).toBeInTheDocument();
  expect(screen.queryByText('operator')).not.toBeInTheDocument();
  expect(screen.getByText('결과 1 / 3건')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: '비밀번호 재설정' })).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('사용자 검색'), { target: { value: 'no-user-match' } });
  expect(screen.getByText('검색 조건에 맞는 사용자가 없습니다.')).toBeInTheDocument();

  fireEvent.click(rbacTab);
  expect(await screen.findByRole('tabpanel', { name: 'RBAC' })).toBeInTheDocument();
  expect(rbacTab).toHaveAttribute('aria-selected', 'true');
  expect(usersTab).toHaveAttribute('aria-selected', 'false');
  expectInDocumentOrder([groupNameText('Auditors'), groupNameText('Operators'), screen.getAllByText('Operators').find((element) => element.tagName.toLowerCase() === 'strong' && element !== groupNameText('Operators')) as HTMLElement]);
  fireEvent.change(screen.getByLabelText('그룹 정렬'), { target: { value: 'key-asc' } });
  expectInDocumentOrder([groupNameText('Operators'), groupNameText('Auditors'), screen.getAllByText('Operators').find((element) => element.tagName.toLowerCase() === 'strong' && element !== groupNameText('Operators')) as HTMLElement]);
  fireEvent.change(screen.getByLabelText('그룹 검색'), { target: { value: 'audit' } });
  expect(groupNameText('Auditors')).toBeInTheDocument();
  expect(screen.queryByText('Operations team')).not.toBeInTheDocument();
  expect(screen.getByText('결과 1 / 3건')).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('그룹 검색'), { target: { value: 'no-group-match' } });
  expect(screen.getByText('검색 조건에 맞는 그룹이 없습니다.')).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText('리소스 권한 정렬'), { target: { value: 'resource-asc' } });
  expectInDocumentOrder([
    grantRowText('group:2 → collection/alpha · collections.alpha.read'),
    grantRowText('group:2 → collection/zeta · collections.zeta.read'),
    grantRowText('user:3 → document/finance · documents.finance.read'),
  ]);
  fireEvent.change(screen.getByLabelText('리소스 권한 검색'), { target: { value: 'finance' } });
  expect(grantRowText('user:3 → document/finance · documents.finance.read')).toBeInTheDocument();
  expect(screen.queryByText((_, element) => element?.textContent === 'group:2 → collection/alpha · collections.alpha.read')).not.toBeInTheDocument();
  expect(screen.getByText('결과 1 / 3건')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: '삭제' })).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('리소스 권한 검색'), { target: { value: 'no-grant-match' } });
  expect(screen.getByText('검색 조건에 맞는 리소스 권한이 없습니다.')).toBeInTheDocument();

  fireEvent.click(screen.getByRole('tab', { name: '모듈' }));
  fireEvent.change(await screen.findByLabelText('new module key'), { target: { value: 'toast-module' } });
  fireEvent.change(screen.getByLabelText('new module title'), { target: { value: 'Toast Module' } });
  fireEvent.change(screen.getByLabelText('new module href'), { target: { value: '/toast' } });
  fireEvent.click(screen.getByRole('button', { name: '모듈 추가' }));
  await waitFor(() => expect(api.createServiceModule).toHaveBeenCalledTimes(1));
  expect(await screen.findByRole('status')).toHaveAttribute('aria-live', 'polite');
});

test('admin search section filters displayed results, keeps count/state, and sorts deterministically', async () => {
  render(<AdminConsoleTabs />);

  fireEvent.click(await screen.findByRole('tab', { name: '검색' }));
  expect(await screen.findByText('통합 검색 / AI 운영')).toBeInTheDocument();
  expect(screen.getByText('결과 0 / 0건')).toBeInTheDocument();
  expect(screen.getByText('2글자 이상 입력하면 뉴스레터와 문서를 한 번에 검색합니다. NSA는 권한이 있을 때만 포함됩니다.')).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText('통합 검색어'), { target: { value: 'manual' } });
  fireEvent.click(screen.getByRole('button', { name: '검색' }));

  await waitFor(() => expect(api.fetchUnifiedSearch).toHaveBeenCalledWith('manual', false));
  expectInDocumentOrder([screen.getByText('Alpha Manual'), screen.getByText('Bravo Manual'), screen.getByText('Zulu Alert')]);
  expect(screen.getByText('결과 3 / 3건')).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText('결과 내 검색'), { target: { value: 'aircraft' } });
  expect(screen.getByText('Alpha Manual')).toBeInTheDocument();
  expect(screen.queryByText('Bravo Manual')).not.toBeInTheDocument();
  expect(screen.getByText('결과 1 / 3건')).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText('결과 내 검색'), { target: { value: 'no-result-match' } });
  expect(screen.getByText('결과 내 검색 조건에 맞는 통합 검색 결과가 없습니다.')).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText('결과 내 검색'), { target: { value: '' } });
  fireEvent.change(screen.getByLabelText('검색 결과 정렬'), { target: { value: 'title-asc' } });
  expectInDocumentOrder([screen.getByText('Alpha Manual'), screen.getByText('Bravo Manual'), screen.getByText('Zulu Alert')]);
});

test('admin tablist keyboard navigation uses roving tabindex and activates ArrowRight Home End targets', async () => {
  render(<AdminConsoleTabs />);

  const modulesTab = await screen.findByRole('tab', { name: '모듈' });
  const usersTab = screen.getByRole('tab', { name: '사용자' });
  const auditTab = screen.getByRole('tab', { name: '감사' });

  expect(modulesTab).toHaveAttribute('tabindex', '0');
  expect(usersTab).toHaveAttribute('tabindex', '-1');

  fireEvent.keyDown(modulesTab, { key: 'ArrowRight' });
  await waitFor(() => expect(usersTab).toHaveAttribute('aria-selected', 'true'));
  expect(usersTab).toHaveAttribute('tabindex', '0');
  expect(modulesTab).toHaveAttribute('tabindex', '-1');

  fireEvent.keyDown(usersTab, { key: 'End' });
  await waitFor(() => expect(auditTab).toHaveAttribute('aria-selected', 'true'));
  expect(auditTab).toHaveAttribute('aria-current', 'page');

  fireEvent.keyDown(auditTab, { key: 'Home' });
  await waitFor(() => expect(modulesTab).toHaveAttribute('aria-selected', 'true'));
  expect(modulesTab).toHaveAttribute('tabindex', '0');
});
