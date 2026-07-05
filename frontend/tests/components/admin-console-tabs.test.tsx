import React from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { AdminConsoleTabs } from '@/components/admin/admin-console-tabs';
import { AdminHomeConsole } from '@/components/admin/admin-home-console';
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
    createServiceModule: vi.fn(),
    fetchAssetHealth: vi.fn(),
    fetchConfigHealth: vi.fn(),
    fetchBackups: vi.fn(),
    fetchCategories: vi.fn(),
    fetchTags: vi.fn(),
    fetchAdminAiStatus: vi.fn(),
  };
});

beforeEach(() => {
  vi.clearAllMocks();
});

function mockAdminData() {
  vi.mocked(api.fetchAdminSummary).mockResolvedValue({ app_version: '1.11.0', app_env: 'test', database_url: 'sqlite:///test.db', db_ok: true, newsletter_total: 1, latest_newsletter_title: '최근 뉴스', active_modules: 0, coming_soon_modules: 0, asset_health: {}, read_summary: {}, ai_status: { status: 'ok' }, recent_audit_events: [] } as never);
  vi.mocked(api.fetchAdminUsers).mockResolvedValue([{ id: 1, username: 'operator', email: 'op@example.com', role: 'admin', is_active: true, permissions: ['admin.read'] }, { id: 2, username: 'analyst', email: 'analyst@example.com', role: 'user', is_active: true, permissions: [] }] as never);
  vi.mocked(api.fetchConnectedUsers).mockResolvedValue({ active_sessions: [{ user_id: 1, username: 'operator', last_seen_at: '2026-07-05T00:00:00Z' }], active_count: 1, recent_login_events: [{ id: 9, user_id: 1, username: 'operator', status: 'success', created_at: '2026-07-05T00:00:00Z' }], login_failure_count: 0, read_tracking_summary: { rows: 1, total_reads: 3 } } as never);
  vi.mocked(api.fetchAdminPermissions).mockResolvedValue([{ key: 'admin.read', description: 'Admin read' }] as never);
  vi.mocked(api.fetchAdminGroups).mockResolvedValue([{ id: 2, key: 'ops', name: 'Operators', is_active: true, permissions: ['admin.read'] }] as never);
  vi.mocked(api.fetchRbacMatrix).mockResolvedValue([{ user_id: 1, username: 'operator', role: 'admin', role_permissions: [], direct_permissions: ['admin.read'], group_permissions: [], effective_permissions: [{ key: 'admin.read', sources: ['direct'] }], resource_grants: [] }] as never);
  vi.mocked(api.listResourceGrants).mockResolvedValue([{ id: 3, subject_type: 'group', subject_id: 2, resource_type: 'collection', resource_id: 'nsa', permission_key: 'collections.nsa.read' }] as never);
  vi.mocked(api.fetchAuditEvents).mockResolvedValue([{ id: 4, actor_username: 'operator', action: 'backup.create', target_type: 'backup', target_id: '1', status: 'success', created_at: '2026-07-05T00:00:00Z' }] as never);
  vi.mocked(api.fetchServiceModulesAdmin).mockResolvedValue([{ id: 5, key: 'dashboard', title: 'Dashboard', description: 'Main', href: '/', section: 'Core', status: 'active', badge: 'Live', sort_order: 2, is_enabled: true, is_external: false, visibility: 'admin' }, { id: 6, key: 'analytics', title: 'Analytics', description: 'Reports', href: '/analytics', section: 'Core', status: 'active', badge: 'New', sort_order: 1, is_enabled: true, is_external: false, visibility: 'admin' }] as never);
  vi.mocked(api.fetchAssetHealth).mockResolvedValue({ ok: 1, missing: 0, checksum_mismatch: 0, misconfig: 0, items: [] } as never);
  vi.mocked(api.fetchConfigHealth).mockResolvedValue({ roots: [{ kind: 'import', resolved_path: 'D:/_database/newsletter', exists: true, readable: true }] } as never);
  vi.mocked(api.fetchBackups).mockResolvedValue([{ id: 6, filename: 'backup.zip', sha256: '1234567890abcdef', file_size: 123, status: 'created', created_at: '2026-07-05T00:00:00Z' }] as never);
  vi.mocked(api.fetchCategories).mockResolvedValue([{ id: 7, name: '분류', description: '설명', sort_order: 0, is_active: true }] as never);
  vi.mocked(api.fetchTags).mockResolvedValue([{ id: 8, name: '태그', sort_order: 0, is_active: true }] as never);
  vi.mocked(api.fetchAdminAiStatus).mockResolvedValue({ status: { ok: true }, request_logs_total: 2, request_failures: 0 } as never);
  vi.mocked(api.createServiceModule).mockResolvedValue({ id: 10, key: 'new-module', title: 'New Module', description: null, href: '/new', section: 'Development', status: 'development', badge: null, sort_order: 0, is_enabled: true, is_external: false, visibility: 'admin' } as never);
}

const parityMatrix = [
  {
    tab: '모듈',
    expected: ['대시보드 모듈 DB 관리', 'dashboard module row', 'module row save', 'module create'],
    assertPresent: async () => {
      expect(await screen.findByText('대시보드 모듈 DB 관리')).toBeInTheDocument();
      expect(screen.getByText('dashboard')).toBeInTheDocument();
      expect(screen.getAllByRole('button', { name: '저장' }).length).toBeGreaterThan(0);
      expect(screen.getByRole('button', { name: '모듈 추가' })).toBeInTheDocument();
    },
  },
  {
    tab: '사용자',
    expected: ['사용자/RBAC', 'user-create', 'operator user row', 'user row save', 'password reset'],
    assertPresent: async () => {
      fireEvent.click(screen.getByRole('tab', { name: '사용자' }));
      expect(await screen.findByText('사용자/RBAC')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '사용자 생성' })).toBeInTheDocument();
      expect(screen.getByText('operator')).toBeInTheDocument();
      expect(screen.getAllByRole('button', { name: '저장' }).length).toBeGreaterThan(0);
      expect(screen.getAllByRole('button', { name: '비밀번호 재설정' }).length).toBeGreaterThan(0);
    },
  },
  {
    tab: 'RBAC',
    expected: ['resource grant create', 'membership add/remove', 'grant delete', 'RBAC matrix'],
    assertPresent: async () => {
      fireEvent.click(screen.getByRole('tab', { name: 'RBAC' }));
      expect(await screen.findByText('그룹/RBAC 권한')).toBeInTheDocument();
      expect(screen.getByText('RBAC 매트릭스 / 리소스 권한')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '리소스 권한 부여' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '그룹 추가' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '그룹 제거' })).toBeInTheDocument();
      expect(screen.getAllByText('operator').length).toBeGreaterThan(0);
      expect(screen.getAllByText(/collections\.nsa\.read/).length).toBeGreaterThan(0);
      expect(screen.getByRole('button', { name: '삭제' })).toBeInTheDocument();
    },
  },
  {
    tab: '세션',
    expected: ['purge button', 'active sessions', 'recent login events', 'read tracking'],
    assertPresent: async () => {
      fireEvent.click(screen.getByRole('tab', { name: '세션' }));
      expect(await screen.findByText('접속자/세션')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '오래된 세션/로그 정리' })).toBeInTheDocument();
      expect(screen.getByText('Active sessions')).toBeInTheDocument();
      expect(screen.getByText('Recent login events')).toBeInTheDocument();
      expect(screen.getByText('Anonymous read tracking')).toBeInTheDocument();
      expect(screen.getAllByText('operator').length).toBeGreaterThan(0);
    },
  },
  {
    tab: '시스템',
    expected: ['config-health', 'asset/config root', 'AI status', 'password change'],
    assertPresent: async () => {
      fireEvent.click(screen.getByRole('tab', { name: '시스템' }));
      expect(await screen.findByText('DB/자산 경로 상태')).toBeInTheDocument();
      expect(screen.getByText('config-health')).toBeInTheDocument();
      expect(screen.getByText('import')).toBeInTheDocument();
      expect(screen.getByText('AI 운영 상태')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '비밀번호 변경' })).toBeInTheDocument();
      expect(screen.getByLabelText('current password')).toBeInTheDocument();
    },
  },
  {
    tab: '분류',
    expected: ['category create', 'tag create', 'category row save', 'tag row save'],
    assertPresent: async () => {
      fireEvent.click(screen.getByRole('tab', { name: '분류' }));
      expect(await screen.findByText('카테고리/태그 관리')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '카테고리 생성' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '태그 생성' })).toBeInTheDocument();
      expect(screen.getByDisplayValue('분류')).toBeInTheDocument();
      expect(screen.getByDisplayValue('태그')).toBeInTheDocument();
      expect(screen.getAllByRole('button', { name: '저장' })).toHaveLength(2);
    },
  },
  {
    tab: '검색',
    expected: ['search input', 'NSA toggle', 'search button'],
    assertPresent: async () => {
      fireEvent.click(screen.getByRole('tab', { name: '검색' }));
      expect(await screen.findByText('통합 검색 / AI 운영')).toBeInTheDocument();
      expect(screen.getByPlaceholderText('뉴스레터·Document·Civil 검색')).toBeInTheDocument();
      expect(screen.getByLabelText('NSA 포함')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '검색' })).toBeInTheDocument();
    },
  },
  {
    tab: '백업',
    expected: ['create backup', 'backup list', 'validate', 'restore dry run', 'audit log'],
    assertPresent: async () => {
      fireEvent.click(screen.getByRole('tab', { name: '백업' }));
      expect(await screen.findByRole('heading', { name: '백업' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '백업 생성' })).toBeInTheDocument();
      expect(screen.getByText('backup.zip')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '검증' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '복원 점검' })).toBeInTheDocument();
      expect(screen.getByText('최근 감사 로그')).toBeInTheDocument();
      expect(screen.getByText('backup.create')).toBeInTheDocument();
    },
  },
] as const;

test('admin console tabs preserve feature parity controls for every decomposed section', async () => {
  mockAdminData();
  render(<AdminConsoleTabs />);

  for (const row of parityMatrix) {
    await row.assertPresent();
  }
});

test('admin list UX filters, sorts, renders empty state, and exposes tab/toast accessibility', async () => {
  mockAdminData();
  render(<AdminConsoleTabs />);

  const modulesTab = await screen.findByRole('tab', { name: '모듈' });
  expect(screen.getByRole('tablist', { name: '관리자 콘솔 탭' })).toBeInTheDocument();
  expect(modulesTab).toHaveAttribute('aria-selected', 'true');
  expect(modulesTab).toHaveAttribute('aria-current', 'page');
  expect(screen.getByRole('tabpanel', { name: '모듈' })).toBeInTheDocument();

  const analytics = await screen.findByText('analytics');
  const dashboard = screen.getByText('dashboard');
  expect(analytics.compareDocumentPosition(dashboard) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();

  fireEvent.change(screen.getByLabelText('모듈 정렬'), { target: { value: 'key-desc' } });
  expect(screen.getByText('dashboard').compareDocumentPosition(screen.getByText('analytics')) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();

  fireEvent.click(screen.getByRole('tab', { name: '사용자' }));
  expect(await screen.findByText('사용자/RBAC')).toBeInTheDocument();
  expect(screen.getByLabelText('사용자 검색')).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('사용자 검색'), { target: { value: 'analyst' } });
  expect(screen.getByText('analyst')).toBeInTheDocument();
  expect(screen.queryByText('operator')).not.toBeInTheDocument();
  expect(screen.getByText('결과 1 / 2건')).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText('사용자 검색'), { target: { value: 'nomatch' } });
  expect(screen.getByText('검색 조건에 맞는 사용자가 없습니다.')).toBeInTheDocument();

  fireEvent.click(screen.getByRole('tab', { name: '모듈' }));
  fireEvent.change(await screen.findByLabelText('new module key'), { target: { value: 'valid-module' } });
  fireEvent.change(screen.getByLabelText('new module title'), { target: { value: 'Valid Module' } });
  fireEvent.change(screen.getByLabelText('new module href'), { target: { value: '/valid' } });
  fireEvent.click(screen.getByRole('button', { name: '모듈 추가' }));
  expect(await screen.findByRole('status')).toHaveAttribute('aria-live', 'polite');
});
test('AdminHomeConsole renders the tab shell and tab switching preserves parent state', async () => {
  mockAdminData();
  render(<AdminHomeConsole />);

  expect(await screen.findByText('운영 콘솔은 DB, 자산, 권한, 감사, 백업 상태를 한 화면에 모읍니다.')).toBeInTheDocument();
  expect(screen.getByRole('tablist', { name: '관리자 콘솔 탭' })).toBeInTheDocument();
  for (const tab of ['모듈', '사용자', 'RBAC', '세션', '시스템', '분류', '검색', '백업']) {
    expect(screen.getByRole('tab', { name: tab })).toBeInTheDocument();
  }

  const newModuleKey = screen.getByLabelText('new module key');
  fireEvent.change(newModuleKey, { target: { value: 'qa-module' } });
  expect(newModuleKey).toHaveValue('qa-module');

  fireEvent.click(screen.getByRole('tab', { name: '사용자' }));
  expect(await screen.findByText('사용자/RBAC')).toBeInTheDocument();

  fireEvent.click(screen.getByRole('tab', { name: '모듈' }));
  expect(await screen.findByText('대시보드 모듈 DB 관리')).toBeInTheDocument();
  expect(screen.getByLabelText('new module key')).toHaveValue('qa-module');
});

test('module status and visibility controls expose only allowed select options', async () => {
  mockAdminData();
  render(<AdminConsoleTabs />);

  expect(await screen.findByText('대시보드 모듈 DB 관리')).toBeInTheDocument();

  const statusOptions = within(screen.getByLabelText('new module status')).getAllByRole('option').map((option) => (option as HTMLOptionElement).value);
  expect(statusOptions).toEqual(['active', 'development', 'coming_soon', 'hidden']);

  const visibilityOptions = within(screen.getByLabelText('new module visibility')).getAllByRole('option').map((option) => (option as HTMLOptionElement).value);
  expect(visibilityOptions).toEqual(['public', 'admin']);

  const rowStatusOptions = within(screen.getByLabelText('dashboard status')).getAllByRole('option').map((option) => (option as HTMLOptionElement).value);
  expect(rowStatusOptions).toEqual(['active', 'development', 'coming_soon', 'hidden']);
});

test('module custom section path is explicit and validates non-empty custom input', async () => {
  mockAdminData();
  render(<AdminConsoleTabs />);

  expect(await screen.findByText('대시보드 모듈 DB 관리')).toBeInTheDocument();

  const sectionSelect = screen.getByLabelText('new module section');
  expect(within(sectionSelect).getAllByRole('option').map((option) => (option as HTMLOptionElement).value)).toEqual(['Newsletter', 'Document', 'Development', '__custom__']);

  fireEvent.change(sectionSelect, { target: { value: '__custom__' } });
  expect(screen.getByLabelText('new module section custom')).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText('new module key'), { target: { value: 'custom-module' } });
  fireEvent.change(screen.getByLabelText('new module title'), { target: { value: 'Custom Module' } });
  fireEvent.change(screen.getByLabelText('new module href'), { target: { value: '/custom' } });
  fireEvent.click(screen.getByRole('button', { name: '모듈 추가' }));

  expect(await screen.findByText('section은 필수입니다.')).toBeInTheDocument();
  expect(api.createServiceModule).not.toHaveBeenCalled();
});

test('invalid module create is blocked with inline validation before calling create handler', async () => {
  mockAdminData();
  render(<AdminConsoleTabs />);

  expect(await screen.findByText('대시보드 모듈 DB 관리')).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('new module title'), { target: { value: 'Missing Key Module' } });
  fireEvent.change(screen.getByLabelText('new module href'), { target: { value: '/missing-key' } });
  fireEvent.click(screen.getByRole('button', { name: '모듈 추가' }));

  expect(await screen.findByText('key는 필수입니다.')).toBeInTheDocument();
  expect(api.createServiceModule).not.toHaveBeenCalled();
});

test('valid module create still calls the shell create handler with the existing payload shape', async () => {
  mockAdminData();
  render(<AdminConsoleTabs />);

  expect(await screen.findByText('대시보드 모듈 DB 관리')).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('new module key'), { target: { value: 'valid-module' } });
  fireEvent.change(screen.getByLabelText('new module title'), { target: { value: 'Valid Module' } });
  fireEvent.change(screen.getByLabelText('new module href'), { target: { value: '/valid' } });
  fireEvent.change(screen.getByLabelText('new module status'), { target: { value: 'active' } });
  fireEvent.change(screen.getByLabelText('new module visibility'), { target: { value: 'public' } });
  fireEvent.click(screen.getByRole('button', { name: '모듈 추가' }));

  await waitFor(() => expect(api.createServiceModule).toHaveBeenCalledTimes(1));
  expect(api.createServiceModule).toHaveBeenCalledWith(
    expect.objectContaining({
      key: 'valid-module',
      title: 'Valid Module',
      section: 'Development',
      status: 'active',
      href: '/valid',
      description: null,
      sort_order: 0,
      is_external: false,
      visibility: 'public',
    }),
    expect.any(String),
  );
});

test('admin page keeps the server guard, sync AppShell, and client island import', () => {
  const pageSource = readFileSync(resolve(process.cwd(), 'app/admin/page.tsx'), 'utf8');
  const shellSource = readFileSync(resolve(process.cwd(), 'components/layout/app-shell.tsx'), 'utf8');

  expect(pageSource).toContain('requireAdminSession');
  expect(pageSource).toContain('<AdminHomeConsole />');
  expect(pageSource).toContain('<AppShell');
  expect(shellSource.startsWith("'use client'")).toBe(false);
  expect(shellSource.startsWith('"use client"')).toBe(false);
});
