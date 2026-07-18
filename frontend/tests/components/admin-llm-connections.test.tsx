import React from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';

import { AdminConsoleTabs } from '@/components/admin/admin-console-tabs';
import * as api from '@/lib/api';

// admin-console-tabs 의 refresh() 가 호출하는 모든 fetcher 를 모킹한다.
// AI 탭의 "AI 연결" 카드가 소비하는 fetchLlmConnections + CRUD/verify 도 함께 모킹한다.
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
    fetchLlmConnections: vi.fn(),
    createLlmConnection: vi.fn(),
    updateLlmConnection: vi.fn(),
    deleteLlmConnection: vi.fn(),
    setDefaultLlmConnection: vi.fn(),
    verifyLlmConnection: vi.fn(),
  };
});

const sampleConnection = {
  id: 1,
  name: '사내 gpt-oss',
  base_url: 'https://gpt-oss.intra/v1',
  default_model: null,
  is_enabled: true,
  is_default: true,
  verify_tls: true,
  api_key_masked: 'sk-...cdef',
  created_at: '2026-07-05T00:00:00Z',
  updated_at: '2026-07-05T00:00:00Z',
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.fetchAdminOverview).mockResolvedValue({
    generated_at: '2026-07-05T00:00:00Z',
    anchor: '2026-06-28T00:00:00Z',
    users: { total: 0, active: 0, inactive: 0, roles: { admin: 0, user: 0, pending: 0 }, created: { current: 0, prior: 0, delta: 0 } },
    logins: { success: { current: 0, prior: 0, delta: 0 }, failure: { current: 0, prior: 0, delta: 0 }, logout: { current: 0, prior: 0, delta: 0 } },
    ai: { total: { current: 0, prior: 0, delta: 0 }, failure: { current: 0, prior: 0, delta: 0 } },
    sessions: { active_session_count: 0, active_user_count: 0, active_count: 0 },
    modules: { total: 0, buckets: { unavailable: [], coming: [], development: [], active: [] } },
    system: { app_version: '1.13.0', app_env: 'test', database_kind: 'sqlite', newsletter_count: 0, asset_health: { ok: 0, missing: 0, checksum_mismatch: 0, misconfig: 0 }, read_summary: { rows: 0, total_reads: 0 } },
    recent_audit: [],
  } as never);
  vi.mocked(api.fetchAdminUsers).mockResolvedValue([] as never);
  vi.mocked(api.fetchConnectedUsers).mockResolvedValue({ active_sessions: [], active_count: 0, recent_login_events: [], login_failure_count: 0, read_tracking_summary: { rows: 0, total_reads: 0 } } as never);
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
  vi.mocked(api.fetchAiProviderConfig).mockResolvedValue({ selected_kind: 'ollama', compatible_state: 'absent', compatible_display_url: null, compatible_model: null, compatible_generation: null, compatible_test_proof_at: null, compatible_test_proof_model: null, config_version: 1, updated_at: '2026-07-04T00:00:00Z' } as never);
  vi.mocked(api.fetchLlmConnections).mockResolvedValue([sampleConnection] as never);
  vi.mocked(api.createLlmConnection).mockResolvedValue(sampleConnection as never);
  vi.mocked(api.updateLlmConnection).mockResolvedValue(sampleConnection as never);
  vi.mocked(api.setDefaultLlmConnection).mockResolvedValue(sampleConnection as never);
  vi.mocked(api.verifyLlmConnection).mockResolvedValue({ ok: true, models: ['gemma4:12b', 'llama3'], detail: null } as never);
});

async function openSystemTab() {
  render(<AdminConsoleTabs />);
  fireEvent.click(await screen.findByRole('tab', { name: 'AI' }));
  await screen.findByText('AI 연결');
}

test('AI 연결 카드는 마스킹 키만 표시하고 키 입력은 password 타입이다', async () => {
  await openSystemTab();

  expect(screen.getByText('사내 gpt-oss')).toBeInTheDocument();
  // 목록에는 평문이 아닌 마스킹 값만 노출된다.
  expect(screen.getByText('sk-...cdef')).toBeInTheDocument();
  expect(screen.getByLabelText('llm connection api_key')).toHaveAttribute('type', 'password');
  expect(screen.getByLabelText('사내 gpt-oss new api_key')).toHaveAttribute('type', 'password');
});

test('연결 추가 폼은 base_url 검증 후 createLlmConnection 을 호출한다', async () => {
  await openSystemTab();

  // 잘못된 base_url 은 API 호출 전에 차단된다.
  fireEvent.change(screen.getByLabelText('llm connection name'), { target: { value: '로컬 Ollama' } });
  fireEvent.change(screen.getByLabelText('llm connection base_url'), { target: { value: 'ftp://bad' } });
  fireEvent.click(screen.getByRole('button', { name: '연결 추가' }));
  await screen.findByRole('alert');
  expect(api.createLlmConnection).not.toHaveBeenCalled();

  // 올바른 값이면 payload 를 그대로 전달한다.
  fireEvent.change(screen.getByLabelText('llm connection base_url'), { target: { value: 'http://127.0.0.1:11434/v1' } });
  fireEvent.click(screen.getByRole('button', { name: '연결 추가' }));

  await waitFor(() => expect(api.createLlmConnection).toHaveBeenCalledTimes(1));
  expect(api.createLlmConnection).toHaveBeenCalledWith(
    expect.objectContaining({ name: '로컬 Ollama', base_url: 'http://127.0.0.1:11434/v1', verify_tls: true }),
    expect.any(String),
  );
});

test('검증 버튼은 verifyLlmConnection 을 호출하고 모델 드롭다운을 채운다', async () => {
  await openSystemTab();

  const select = screen.getByLabelText('사내 gpt-oss model');
  expect(within(select).queryByRole('option', { name: 'gemma4:12b' })).toBeNull();

  fireEvent.click(screen.getByRole('button', { name: '검증' }));

  await waitFor(() => expect(api.verifyLlmConnection).toHaveBeenCalledWith(1, expect.any(String)));
  expect(await within(select).findByRole('option', { name: 'gemma4:12b' })).toBeInTheDocument();
  expect(within(select).getByRole('option', { name: 'llama3' })).toBeInTheDocument();
});
