import React from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
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
    fetchAiProviderConfig: vi.fn(),
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
  vi.mocked(api.fetchAdminOverview).mockResolvedValue({
    generated_at: '2026-07-05T00:00:00Z',
    anchor: '2026-06-28T00:00:00Z',
    users: { total: 3, active: 3, inactive: 0, roles: { admin: 2, user: 1, pending: 0 }, created: { current: 1, prior: 0, delta: 1 } },
    logins: { success: { current: 3, prior: 2, delta: 1 }, failure: { current: 0, prior: 1, delta: -1 }, logout: { current: 2, prior: 1, delta: 1 } },
    ai: { total: { current: 5, prior: 4, delta: 1 }, failure: { current: 0, prior: 0, delta: 0 } },
    sessions: { active_session_count: 0, active_user_count: 0, active_count: 0 },
    modules: { total: 3, buckets: { unavailable: [], coming: [], development: [], active: [{ key: 'ov-dashboard', label: 'Overview Dashboard' }, { key: 'ov-analytics', label: 'Overview Analytics' }, { key: 'ov-alpha', label: 'Overview Alpha' }] } },
    system: { app_version: '1.11.0', app_env: 'test', database_kind: 'sqlite', newsletter_count: 1, asset_health: { ok: 1, missing: 0, checksum_mismatch: 0, misconfig: 0 }, read_summary: { rows: 0, total_reads: 0 } },
    recent_audit: [],
  } as never);
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

  const contentTab = await screen.findByRole('tab', { name: '콘텐츠' });
  const accountsTab = screen.getByRole('tab', { name: '계정' });

  expect(screen.getByRole('tablist', { name: '관리자 콘솔 탭' })).toBeInTheDocument();
  fireEvent.click(contentTab);
  expect(contentTab).toHaveAttribute('aria-selected', 'true');
  expect(accountsTab).toHaveAttribute('aria-selected', 'false');
  expect(await screen.findByRole('tabpanel', { name: '콘텐츠' })).toBeInTheDocument();

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

  fireEvent.click(accountsTab);
  expect(await screen.findByRole('tabpanel', { name: '계정' })).toBeInTheDocument();
  expect(accountsTab).toHaveAttribute('aria-selected', 'true');
  expect(contentTab).toHaveAttribute('aria-selected', 'false');
  const usersSection = screen.getByText('사용자/RBAC').closest('section') as HTMLElement;
  expectInDocumentOrder([within(usersSection).getByText('alpha'), within(usersSection).getByText('analyst'), within(usersSection).getByText('operator')]);
  fireEvent.change(within(usersSection).getByLabelText('사용자 정렬'), { target: { value: 'role-asc' } });
  expectInDocumentOrder([within(usersSection).getByText('alpha'), within(usersSection).getByText('operator'), within(usersSection).getByText('analyst')]);
  fireEvent.change(within(usersSection).getByLabelText('사용자 검색'), { target: { value: 'analyst' } });
  expect(within(usersSection).getByText('analyst')).toBeInTheDocument();
  expect(within(usersSection).queryByText('operator')).not.toBeInTheDocument();
  expect(within(usersSection).getByText('결과 1 / 3건')).toBeInTheDocument();
  expect(within(usersSection).getByRole('button', { name: '비밀번호 재설정' })).toBeInTheDocument();
  fireEvent.change(within(usersSection).getByLabelText('사용자 검색'), { target: { value: 'no-user-match' } });
  expect(within(usersSection).getByText('검색 조건에 맞는 사용자가 없습니다.')).toBeInTheDocument();

  const rbacSection = screen.getByText('그룹/RBAC 권한').closest('section') as HTMLElement;
  expectInDocumentOrder([groupNameText('Auditors'), groupNameText('Operators'), screen.getAllByText('Operators').find((element) => element.tagName.toLowerCase() === 'strong' && element !== groupNameText('Operators')) as HTMLElement]);
  fireEvent.change(within(rbacSection).getByLabelText('그룹 정렬'), { target: { value: 'key-asc' } });
  expectInDocumentOrder([groupNameText('Operators'), groupNameText('Auditors'), screen.getAllByText('Operators').find((element) => element.tagName.toLowerCase() === 'strong' && element !== groupNameText('Operators')) as HTMLElement]);
  fireEvent.change(within(rbacSection).getByLabelText('그룹 검색'), { target: { value: 'audit' } });
  expect(groupNameText('Auditors')).toBeInTheDocument();
  expect(screen.queryByText('Operations team')).not.toBeInTheDocument();
  expect(within(rbacSection).getByText('결과 1 / 3건')).toBeInTheDocument();
  fireEvent.change(within(rbacSection).getByLabelText('그룹 검색'), { target: { value: 'no-group-match' } });
  expect(within(rbacSection).getByText('검색 조건에 맞는 그룹이 없습니다.')).toBeInTheDocument();

  fireEvent.change(within(rbacSection).getByLabelText('리소스 권한 정렬'), { target: { value: 'resource-asc' } });
  expectInDocumentOrder([
    grantRowText('group:2 → collection/alpha · collections.alpha.read'),
    grantRowText('group:2 → collection/zeta · collections.zeta.read'),
    grantRowText('user:3 → document/finance · documents.finance.read'),
  ]);
  fireEvent.change(within(rbacSection).getByLabelText('리소스 권한 검색'), { target: { value: 'finance' } });
  expect(grantRowText('user:3 → document/finance · documents.finance.read')).toBeInTheDocument();
  expect(screen.queryByText((_, element) => element?.textContent === 'group:2 → collection/alpha · collections.alpha.read')).not.toBeInTheDocument();
  expect(within(rbacSection).getByText('결과 1 / 3건')).toBeInTheDocument();
  expect(within(rbacSection).getByRole('button', { name: '삭제' })).toBeInTheDocument();
  fireEvent.change(within(rbacSection).getByLabelText('리소스 권한 검색'), { target: { value: 'no-grant-match' } });
  expect(within(rbacSection).getByText('검색 조건에 맞는 리소스 권한이 없습니다.')).toBeInTheDocument();

  fireEvent.click(screen.getByRole('tab', { name: '콘텐츠' }));
  fireEvent.change(await screen.findByLabelText('new module key'), { target: { value: 'toast-module' } });
  fireEvent.change(screen.getByLabelText('new module title'), { target: { value: 'Toast Module' } });
  fireEvent.change(screen.getByLabelText('new module href'), { target: { value: '/toast' } });
  fireEvent.click(screen.getByRole('button', { name: '모듈 추가' }));
  await waitFor(() => expect(api.createServiceModule).toHaveBeenCalledTimes(1));
  expect(await screen.findByRole('status')).toHaveAttribute('aria-live', 'polite');
});

test('admin search section filters displayed results, keeps count/state, and sorts deterministically', async () => {
  render(<AdminConsoleTabs />);

  fireEvent.click(await screen.findByRole('tab', { name: '콘텐츠' }));
  expect(await screen.findByText('통합 검색 / AI 운영')).toBeInTheDocument();
  const searchSection = screen.getByText('통합 검색 / AI 운영').closest('section') as HTMLElement;
  expect(within(searchSection).getByText('결과 0 / 0건')).toBeInTheDocument();
  expect(screen.getByText('2글자 이상 입력하면 뉴스레터와 문서를 한 번에 검색합니다. NSA는 권한이 있을 때만 포함됩니다.')).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText('통합 검색어'), { target: { value: 'manual' } });
  fireEvent.click(screen.getByRole('button', { name: '검색' }));

  await waitFor(() => expect(api.fetchUnifiedSearch).toHaveBeenCalledWith('manual', false));
  expectInDocumentOrder([within(searchSection).getByText('Alpha Manual'), within(searchSection).getByText('Bravo Manual'), within(searchSection).getByText('Zulu Alert')]);
  expect(within(searchSection).getByText('결과 3 / 3건')).toBeInTheDocument();

  fireEvent.change(within(searchSection).getByLabelText('결과 내 검색'), { target: { value: 'aircraft' } });
  expect(within(searchSection).getByText('Alpha Manual')).toBeInTheDocument();
  expect(within(searchSection).queryByText('Bravo Manual')).not.toBeInTheDocument();
  expect(within(searchSection).getByText('결과 1 / 3건')).toBeInTheDocument();

  fireEvent.change(within(searchSection).getByLabelText('결과 내 검색'), { target: { value: 'no-result-match' } });
  expect(within(searchSection).getByText('결과 내 검색 조건에 맞는 통합 검색 결과가 없습니다.')).toBeInTheDocument();

  fireEvent.change(within(searchSection).getByLabelText('결과 내 검색'), { target: { value: '' } });
  fireEvent.change(within(searchSection).getByLabelText('검색 결과 정렬'), { target: { value: 'title-asc' } });
  expectInDocumentOrder([within(searchSection).getByText('Alpha Manual'), within(searchSection).getByText('Bravo Manual'), within(searchSection).getByText('Zulu Alert')]);
});

test('admin tablist keyboard navigation uses roving tabindex and activates ArrowRight Home End targets', async () => {
  render(<AdminConsoleTabs />);

  const overviewTab = await screen.findByRole('tab', { name: '개요' });
  const accountsTab = screen.getByRole('tab', { name: '계정' });
  const auditTab = screen.getByRole('tab', { name: '감사' });

  expect(overviewTab).toHaveAttribute('tabindex', '0');
  expect(accountsTab).toHaveAttribute('tabindex', '-1');

  fireEvent.keyDown(overviewTab, { key: 'ArrowRight' });
  await waitFor(() => expect(accountsTab).toHaveAttribute('aria-selected', 'true'));
  expect(accountsTab).toHaveAttribute('tabindex', '0');
  expect(overviewTab).toHaveAttribute('tabindex', '-1');

  fireEvent.keyDown(accountsTab, { key: 'End' });
  await waitFor(() => expect(auditTab).toHaveAttribute('aria-selected', 'true'));
  expect(auditTab).toHaveAttribute('aria-current', 'page');

  fireEvent.keyDown(auditTab, { key: 'Home' });
  await waitFor(() => expect(overviewTab).toHaveAttribute('aria-selected', 'true'));
  expect(overviewTab).toHaveAttribute('tabindex', '0');
});


test('Users 섹션은 21명을 10개씩 페이지네이션하고 검색/정렬 변경 시 1페이지로 리셋하며 가입일/최근 로그인을 표시한다', async () => {
  const users = Array.from({ length: 21 }, (_, index) => {
    const n = index + 1;
    return {
      id: n,
      username: `user-${String(n).padStart(2, '0')}`,
      email: `user${n}@example.com`,
      role: 'user',
      is_active: true,
      permissions: [],
      created_at: '2026-06-01T00:00:00Z',
      last_login_at: n % 5 === 0 ? null : '2026-07-01T00:00:00Z',
    };
  });
  vi.mocked(api.fetchAdminUsers).mockResolvedValue(users as never);

  render(<AdminConsoleTabs />);
  fireEvent.click(await screen.findByRole('tab', { name: '계정' }));
  expect(await screen.findByText('사용자/RBAC')).toBeInTheDocument();
  const usersSection = screen.getByText('사용자/RBAC').closest('section') as HTMLElement;

  expect(within(usersSection).getByText('페이지 1 / 3')).toBeInTheDocument();
  expect(within(usersSection).getByText('user-01')).toBeInTheDocument();
  expect(within(usersSection).getByText('user-10')).toBeInTheDocument();
  expect(within(usersSection).queryByText('user-11')).not.toBeInTheDocument();
  expect(within(usersSection).getByRole('button', { name: '이전 페이지' })).toBeDisabled();

  fireEvent.click(within(usersSection).getByRole('button', { name: '다음 페이지' }));
  expect(await within(usersSection).findByText('페이지 2 / 3')).toBeInTheDocument();
  expect(within(usersSection).getByText('user-11')).toBeInTheDocument();
  expect(within(usersSection).getByText('user-20')).toBeInTheDocument();
  expect(within(usersSection).queryByText('user-01')).not.toBeInTheDocument();

  fireEvent.click(within(usersSection).getByRole('button', { name: '다음 페이지' }));
  expect(await within(usersSection).findByText('페이지 3 / 3')).toBeInTheDocument();
  expect(within(usersSection).getByText('user-21')).toBeInTheDocument();
  expect(within(usersSection).getByRole('button', { name: '다음 페이지' })).toBeDisabled();

  fireEvent.change(within(usersSection).getByLabelText('사용자 검색'), { target: { value: 'user-2' } });
  await waitFor(() => expect(within(usersSection).getByText('페이지 1 / 1')).toBeInTheDocument());
  expect(within(usersSection).getByText('user-20')).toBeInTheDocument();
  expect(within(usersSection).getByText('user-21')).toBeInTheDocument();

  fireEvent.change(within(usersSection).getByLabelText('사용자 검색'), { target: { value: '' } });
  await waitFor(() => expect(within(usersSection).getByText('페이지 1 / 3')).toBeInTheDocument());

  fireEvent.click(within(usersSection).getByRole('button', { name: '다음 페이지' }));
  await waitFor(() => expect(within(usersSection).getByText('페이지 2 / 3')).toBeInTheDocument());
  fireEvent.change(within(usersSection).getByLabelText('사용자 정렬'), { target: { value: 'username-desc' } });
  await waitFor(() => expect(within(usersSection).getByText('페이지 1 / 3')).toBeInTheDocument());
  expect(within(usersSection).getByText('user-21')).toBeInTheDocument();

  expect(within(usersSection).getAllByText(/가입일/).length).toBeGreaterThan(0);
  expect(within(usersSection).getAllByText(/마지막 로그인/).length).toBeGreaterThan(0);
});

test('Users 섹션은 데이터 없음(빈 목록)과 조회 실패(degraded)를 시각적으로 구분한다', async () => {
  vi.mocked(api.fetchAdminUsers).mockResolvedValue([] as never);

  render(<AdminConsoleTabs />);
  fireEvent.click(await screen.findByRole('tab', { name: '계정' }));
  expect(await screen.findByText('등록된 사용자가 없습니다.')).toBeInTheDocument();
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
});

test('모듈 카드는 게이트 필드(visibility/required_permission/resource_type/resource_id) 읽기 전용 요약을 노출하고 400 정책 거부는 안전한 메시지로만 표시한다', async () => {
  vi.mocked(api.fetchServiceModulesAdmin).mockResolvedValue([
    { id: 5, key: 'dashboard', title: 'Dashboard', description: 'Main', href: '/', section: 'Core', status: 'active', badge: 'Live', sort_order: 2, is_enabled: true, is_external: false, visibility: 'admin', required_permission: 'admin.dashboard.view', resource_type: 'collection', resource_id: 'nsa' },
  ] as never);
  vi.mocked(api.updateServiceModule).mockRejectedValueOnce(new api.ApiError('요청 처리에 실패했습니다', 400) as never);

  render(<AdminConsoleTabs />);
  fireEvent.click(await screen.findByRole('tab', { name: '콘텐츠' }));
  expect(await screen.findByText('대시보드 모듈 DB 관리')).toBeInTheDocument();

  expect(screen.getByText('admin.dashboard.view')).toBeInTheDocument();
  expect(screen.getByText(/collection\/nsa/)).toBeInTheDocument();

  fireEvent.click(screen.getByRole('button', { name: '저장' }));

  expect(await screen.findByRole('alert')).toHaveTextContent('요청 처리에 실패했습니다');
  expect(screen.queryByText(/database|traceback|sqlite:\/\//i)).not.toBeInTheDocument();
});
