import React from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { AdminConsoleTabs } from '@/components/admin/admin-console-tabs';
import { PermissionCheckboxGrid } from '@/components/admin/widgets/permission-checkbox-grid';
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
    fetchAssetHealth: vi.fn(),
    fetchConfigHealth: vi.fn(),
    fetchBackups: vi.fn(),
    fetchCategories: vi.fn(),
    fetchTags: vi.fn(),
    fetchAdminAiStatus: vi.fn(),
    fetchLlmConnections: vi.fn().mockResolvedValue([]),
    updateAdminUser: vi.fn(),
    upsertAdminGroup: vi.fn(),
    createResourceGrant: vi.fn(),
    createServiceModule: vi.fn(),
    updateServiceModule: vi.fn(),
    addUserGroup: vi.fn(),
    removeUserGroup: vi.fn(),
  };
});

beforeEach(() => {
  vi.clearAllMocks();
  mockAdminData();
});

function mockAdminData() {
  vi.mocked(api.fetchAdminSummary).mockResolvedValue({ app_version: '1.11.0', app_env: 'test', database_url: 'sqlite:///test.db', db_ok: true, newsletter_total: 0, latest_newsletter_title: null, active_modules: 0, coming_soon_modules: 0, asset_health: {}, read_summary: {}, ai_status: { status: 'ok' }, recent_audit_events: [] } as never);
  vi.mocked(api.fetchAdminUsers).mockResolvedValue([
    { id: 1, username: 'operator', email: 'op@example.com', role: 'admin', is_active: true, permissions: ['admin.read'] },
    { id: 9, username: 'analyst', email: null, role: 'user', is_active: true, permissions: [] },
  ] as never);
  vi.mocked(api.fetchConnectedUsers).mockResolvedValue({ active_sessions: [], active_count: 0, recent_login_events: [], login_failure_count: 0, read_tracking_summary: { rows: 0, total_reads: 0 } } as never);
  vi.mocked(api.fetchAdminPermissions).mockResolvedValue([
    { key: 'admin.read' },
    { key: 'admin.write' },
    { key: 'ai.use' },
    { key: 'collections.nsa.read' },
    { key: 'collections.read' },
    { key: 'documents.delete' },
  ] as never);
  vi.mocked(api.fetchAdminGroups).mockResolvedValue([
    { id: 2, key: 'ops', name: 'Operators', is_active: true, permissions: ['admin.read'] },
    { id: 4, key: 'nsa', name: 'NSA Readers', is_active: true, permissions: [] },
  ] as never);
  vi.mocked(api.fetchRbacMatrix).mockResolvedValue([{ user_id: 1, username: 'operator', role: 'admin', role_permissions: [], direct_permissions: ['admin.read'], group_permissions: [], effective_permissions: [{ key: 'admin.read', sources: ['direct'] }], resource_grants: [] }] as never);
  vi.mocked(api.listResourceGrants).mockResolvedValue([] as never);
  vi.mocked(api.fetchAuditEvents).mockResolvedValue([] as never);
  vi.mocked(api.fetchServiceModulesAdmin).mockResolvedValue([] as never);
  vi.mocked(api.fetchAssetHealth).mockResolvedValue({ ok: 0, missing: 0, checksum_mismatch: 0, misconfig: 0, items: [] } as never);
  vi.mocked(api.fetchConfigHealth).mockResolvedValue({ roots: [] } as never);
  vi.mocked(api.fetchBackups).mockResolvedValue([] as never);
  vi.mocked(api.fetchCategories).mockResolvedValue([] as never);
  vi.mocked(api.fetchTags).mockResolvedValue([] as never);
  vi.mocked(api.fetchAdminAiStatus).mockResolvedValue({ status: { ok: true }, request_logs_total: 0, request_failures: 0 } as never);
  vi.mocked(api.updateAdminUser).mockResolvedValue({ id: 1, username: 'operator', email: 'op@example.com', role: 'admin', is_active: true, permissions: ['admin.read', 'admin.write'] } as never);
  vi.mocked(api.upsertAdminGroup).mockResolvedValue({ id: 2, key: 'ops', name: 'Operators', is_active: true, permissions: ['admin.read', 'ai.use'] } as never);
  vi.mocked(api.createResourceGrant).mockResolvedValue({ id: 7, subject_type: 'user', subject_id: 1, resource_type: 'collection', resource_id: 'nsa', permission_key: 'collections.nsa.read' } as never);
  vi.mocked(api.createServiceModule).mockResolvedValue({ id: 11, key: 'new-module', title: 'New Module', description: null, href: '/new', section: 'Development', status: 'development', badge: '', sort_order: 0, is_enabled: true, is_external: false, visibility: 'admin' } as never);
  vi.mocked(api.updateServiceModule).mockResolvedValue({ id: 10, key: 'dashboard', title: 'Dashboard', description: null, href: '/', section: 'Development', status: 'active', badge: '', sort_order: 0, is_enabled: true, is_external: false, visibility: 'admin' } as never);
  vi.mocked(api.addUserGroup).mockResolvedValue({ id: 1, username: 'operator', email: 'op@example.com', role: 'admin', is_active: true, permissions: [] } as never);
  vi.mocked(api.removeUserGroup).mockResolvedValue({ id: 1, username: 'operator', email: 'op@example.com', role: 'admin', is_active: true, permissions: [] } as never);
}

async function openTab(name: string) {
  render(<AdminConsoleTabs />);
  fireEvent.click(await screen.findByRole('tab', { name }));
}

test('permission checkbox grid round-trips selected permission keys without adding or dropping entries', () => {
  const observed: string[][] = [];
  const Harness = () => {
    const [value, setValue] = React.useState<string[]>(['admin.read']);
    return (
      <>
        <PermissionCheckboxGrid
          permissions={[{ key: 'admin.read' }, { key: 'ai.use' }, { key: 'collections.nsa.read' }, { key: 'collections.read' }]}
          value={value}
          onChange={(next) => {
            observed.push(next);
            setValue(next);
          }}
          label="roundtrip permissions"
        />
        <output aria-label="serialized permissions">{value.join(', ')}</output>
      </>
    );
  };

  render(<Harness />);
  expect(screen.getByText('문서 열람')).toBeInTheDocument();
  expect(screen.getByText('기타')).toBeInTheDocument();
  expect(screen.getAllByText('AI 사용').length).toBeGreaterThan(0);
  expect(screen.getByText('NSA 문서 열람')).toBeInTheDocument();
  expect(screen.getByText('collections.nsa.read')).toHaveClass('font-mono');
  expect(screen.getByLabelText('roundtrip permissions collections.nsa.read')).toBeInTheDocument();
  fireEvent.click(screen.getByLabelText('roundtrip permissions collections.nsa.read'));
  fireEvent.click(screen.getByLabelText('roundtrip permissions ai.use'));
  fireEvent.click(screen.getByLabelText('roundtrip permissions admin.read'));

  expect(screen.getByLabelText('serialized permissions')).toHaveTextContent('ai.use, collections.nsa.read');
  expect(observed.at(-1)).toEqual(['ai.use', 'collections.nsa.read']);
});

test('permission grid selects and serializes user and group permissions without CSV textareas', async () => {
  await openTab('사용자');

  expect(await screen.findByText('사용자/RBAC')).toBeInTheDocument();
  expect(screen.queryByRole('textbox', { name: 'operator permissions' })).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('사용자 검색'), { target: { value: 'operator' } });
  fireEvent.click(screen.getByRole('button', { name: '권한 수정' }));
  fireEvent.click(screen.getByLabelText('operator permissions admin.write'));
  fireEvent.click(screen.getByRole('button', { name: '저장' }));

  await waitFor(() => expect(api.updateAdminUser).toHaveBeenCalled());
  expect(vi.mocked(api.updateAdminUser).mock.calls[0][1]).toMatchObject({ permissions: ['admin.read', 'admin.write'] });

  fireEvent.click(screen.getByRole('tab', { name: 'RBAC' }));
  expect(await screen.findByText('그룹/RBAC 권한')).toBeInTheDocument();
  expect(screen.queryByPlaceholderText('permission keys, comma-separated')).not.toBeInTheDocument();
  fireEvent.click(screen.getByLabelText('group permissions ai.use'));
  fireEvent.change(screen.getByPlaceholderText('group key'), { target: { value: 'ops' } });
  fireEvent.change(screen.getByPlaceholderText('group name'), { target: { value: 'Operators' } });
  fireEvent.click(screen.getByRole('button', { name: '그룹 저장' }));

  await waitFor(() => expect(api.upsertAdminGroup).toHaveBeenCalled());
  expect(vi.mocked(api.upsertAdminGroup).mock.calls[0][0]).toMatchObject({ permissions: ['ai.use'] });
});

test('resource grant form never offers global or non-resource keys and blocks tampered permission keys', async () => {
  await openTab('RBAC');
  expect(await screen.findByText('RBAC 매트릭스 / 리소스 권한')).toBeInTheDocument();

  const permissionSelect = screen.getByLabelText('grant permission key');
  const optionValues = within(permissionSelect).getAllByRole('option').map((option) => (option as HTMLOptionElement).value);
  expect(optionValues).toEqual(['', 'collections.nsa.read', 'collections.read']);
  expect(optionValues).not.toContain('admin.read');
  expect(optionValues).not.toContain('admin.write');
  expect(optionValues).not.toContain('ai.use');
  expect(optionValues).not.toContain('documents.delete');
  expect(optionValues.every((value) => value === '' || value.startsWith('collections.'))).toBe(true);

  permissionSelect.appendChild(new Option('admin.write', 'admin.write'));
  fireEvent.change(permissionSelect, { target: { value: 'admin.write' } });
  fireEvent.change(screen.getByLabelText('grant subject'), { target: { value: '1' } });
  fireEvent.change(screen.getByLabelText('grant resource id'), { target: { value: 'nsa' } });
  fireEvent.click(screen.getByRole('button', { name: '리소스 권한 부여' }));

  expect(await screen.findByText('허용된 리소스 권한을 선택하세요.')).toBeInTheDocument();
  expect(api.createResourceGrant).not.toHaveBeenCalled();
});

test('NSA preset grants only the scoped NSA collection permission and does not select global permission checkboxes', async () => {
  await openTab('RBAC');
  expect(await screen.findByText('RBAC 매트릭스 / 리소스 권한')).toBeInTheDocument();

  fireEvent.click(screen.getByRole('button', { name: 'NSA 열람권 부여' }));
  expect(screen.getByLabelText('grant resource type')).toHaveValue('collection');
  expect(screen.getByLabelText('grant resource id')).toHaveValue('nsa');
  expect(screen.getByLabelText('grant permission key')).toHaveValue('collections.nsa.read');
  expect(screen.getByLabelText('group permissions admin.read')).not.toBeChecked();
  expect(screen.getByLabelText('group permissions admin.write')).not.toBeChecked();

  fireEvent.change(screen.getByLabelText('grant subject'), { target: { value: '1' } });
  fireEvent.click(screen.getByRole('button', { name: '리소스 권한 부여' }));

  await waitFor(() => expect(api.createResourceGrant).toHaveBeenCalledTimes(1));
  expect(vi.mocked(api.createResourceGrant).mock.calls[0][0]).toMatchObject({
    subject_type: 'user',
    subject_id: 1,
    resource_type: 'collection',
    resource_id: 'nsa',
    permission_key: 'collections.nsa.read',
  });
});

test('resource grant form blocks empty and path-like resource ids inline', async () => {
  await openTab('RBAC');
  expect(await screen.findByText('RBAC 매트릭스 / 리소스 권한')).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText('grant subject'), { target: { value: '1' } });
  fireEvent.change(screen.getByLabelText('grant resource id'), { target: { value: '   ' } });
  fireEvent.click(screen.getByRole('button', { name: '리소스 권한 부여' }));
  expect(await screen.findByText('리소스 ID는 필수입니다.')).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText('grant resource id'), { target: { value: 'nsa/private' } });
  fireEvent.click(screen.getByRole('button', { name: '리소스 권한 부여' }));

  expect(await screen.findByText('리소스 ID에 공백/경로/특수문자를 사용할 수 없습니다.')).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText('grant resource id'), { target: { value: 'nsa*' } });
  fireEvent.click(screen.getByRole('button', { name: '리소스 권한 부여' }));
  expect(await screen.findByText('리소스 ID에 공백/경로/특수문자를 사용할 수 없습니다.')).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText('grant resource id'), { target: { value: '../nsa' } });
  fireEvent.click(screen.getByRole('button', { name: '리소스 권한 부여' }));
  expect(await screen.findByText('리소스 ID에 공백/경로/특수문자를 사용할 수 없습니다.')).toBeInTheDocument();
  expect(api.createResourceGrant).not.toHaveBeenCalled();
});
test('module status and visibility selects expose only defined values and invalid create is blocked inline', async () => {
  render(<AdminConsoleTabs />);

  expect(await screen.findByText('대시보드 모듈 DB 관리')).toBeInTheDocument();
  const statusValues = within(screen.getByLabelText('new module status')).getAllByRole('option').map((option) => (option as HTMLOptionElement).value);
  const visibilityValues = within(screen.getByLabelText('new module visibility')).getAllByRole('option').map((option) => (option as HTMLOptionElement).value);
  expect(statusValues).toEqual(['active', 'development', 'coming_soon', 'hidden']);
  expect(visibilityValues).toEqual(['public', 'admin']);
  expect(statusValues).not.toContain('super_admin');
  expect(visibilityValues).not.toContain('global');

  fireEvent.change(screen.getByLabelText('new module title'), { target: { value: 'Unsafe Module' } });
  fireEvent.change(screen.getByLabelText('new module href'), { target: { value: '/unsafe' } });
  fireEvent.click(screen.getByRole('button', { name: '모듈 추가' }));

  expect(await screen.findByText('key는 필수입니다.')).toBeInTheDocument();
  expect(api.createServiceModule).not.toHaveBeenCalled();
});

test('user/group picker shows names and emits numeric ids', async () => {
  await openTab('RBAC');
  expect(await screen.findByText('RBAC 매트릭스 / 리소스 권한')).toBeInTheDocument();

  const userSelect = screen.getByLabelText('membership user');
  const groupSelect = screen.getByLabelText('membership group');
  expect(within(userSelect).getByRole('option', { name: 'operator' })).toHaveValue('1');
  expect(within(groupSelect).getByRole('option', { name: 'Operators' })).toHaveValue('2');

  fireEvent.change(userSelect, { target: { value: '1' } });
  fireEvent.change(groupSelect, { target: { value: '2' } });
  fireEvent.click(screen.getByRole('button', { name: '그룹 추가' }));

  await waitFor(() => expect(api.addUserGroup).toHaveBeenCalled());
  expect(vi.mocked(api.addUserGroup).mock.calls[0][0]).toBe(1);
  expect(vi.mocked(api.addUserGroup).mock.calls[0][1]).toBe(2);
});
