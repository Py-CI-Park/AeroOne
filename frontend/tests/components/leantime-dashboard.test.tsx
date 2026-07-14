import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { ApiError } from '@/lib/api';
import { LeantimeDashboard } from '@/components/office-tools/leantime-dashboard';

const {
  fetchLeantimeProjectsMock,
  fetchLeantimeTasksMock,
  fetchLeantimeCalendarMock,
} = vi.hoisted(() => ({
  fetchLeantimeProjectsMock: vi.fn(),
  fetchLeantimeTasksMock: vi.fn(),
  fetchLeantimeCalendarMock: vi.fn(),
}));

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return {
    ...actual,
    fetchLeantimeProjects: fetchLeantimeProjectsMock,
    fetchLeantimeTasks: fetchLeantimeTasksMock,
    fetchLeantimeCalendar: fetchLeantimeCalendarMock,
  };
});


const ENVELOPE_OK: { degraded: boolean; reason: string | null; source: string; fetched_at: string } = {
  degraded: false,
  reason: null,
  source: 'leantime',
  fetched_at: '2026-07-14T00:00:00Z',
};

function readyEnvelope<T>(items: T[], overrides: Partial<typeof ENVELOPE_OK> = {}) {
  return { ...ENVELOPE_OK, ...overrides, items };
}

beforeEach(() => {
  fetchLeantimeProjectsMock.mockReset();
  fetchLeantimeTasksMock.mockReset();
  fetchLeantimeCalendarMock.mockReset();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

test('renders projects, tasks, and calendar items on successful load', async () => {
  fetchLeantimeProjectsMock.mockResolvedValue(
    readyEnvelope([{ id: '1', name: 'Alpha', state: 'active', client_name: 'Client A' }]),
  );
  fetchLeantimeTasksMock.mockResolvedValue(
    readyEnvelope([{ id: 't1', project_id: '1', headline: 'Ship it', status: 'open', date_to_finish: '2026-08-01' }]),
  );
  fetchLeantimeCalendarMock.mockResolvedValue(
    readyEnvelope([{ id: 'c1', name: 'Milestone', date_start: '2026-07-14', date_end: '2026-07-15' }]),
  );

  render(<LeantimeDashboard />);

  await waitFor(() => expect(screen.getByText('Alpha')).toBeInTheDocument());
  expect(screen.getByText('Ship it')).toBeInTheDocument();
  expect(screen.getByText('Milestone')).toBeInTheDocument();
});

test('shows empty states when a resource has no items', async () => {
  fetchLeantimeProjectsMock.mockResolvedValue(readyEnvelope([]));
  fetchLeantimeTasksMock.mockResolvedValue(readyEnvelope([]));
  fetchLeantimeCalendarMock.mockResolvedValue(readyEnvelope([]));

  render(<LeantimeDashboard />);

  await waitFor(() => expect(screen.getByText('표시할 프로젝트가 없습니다.')).toBeInTheDocument());
  expect(screen.getByText('표시할 담당 작업이 없습니다.')).toBeInTheDocument();
  expect(screen.getByText('표시할 기간 일정이 없습니다.')).toBeInTheDocument();
});

test.each([
  ['not_configured', 'Leantime 연동이 아직 구성되지 않았습니다. 관리자에게 설정을 요청하세요.'],
  ['credential_error', 'Leantime 접속 자격 증명에 문제가 있습니다. 관리자에게 문의하세요.'],
  ['auth_failed', 'Leantime 인증에 실패했습니다. 관리자에게 문의하세요.'],
  ['upstream_unavailable', 'Leantime 서버에 연결할 수 없습니다. 잠시 후 다시 시도하세요.'],
])('shows the correct Korean guidance for degraded reason=%s', async (reason, guidance) => {
  fetchLeantimeProjectsMock.mockResolvedValue(readyEnvelope([], { degraded: true, reason }));
  fetchLeantimeTasksMock.mockResolvedValue(readyEnvelope([]));
  fetchLeantimeCalendarMock.mockResolvedValue(readyEnvelope([]));

  render(<LeantimeDashboard />);

  await waitFor(() => expect(screen.getByText(guidance)).toBeInTheDocument());
});

test('shows a distinct permission state per resource on 403', async () => {
  fetchLeantimeProjectsMock.mockRejectedValue(new ApiError('Forbidden', 403));
  fetchLeantimeTasksMock.mockResolvedValue(readyEnvelope([]));
  fetchLeantimeCalendarMock.mockResolvedValue(readyEnvelope([]));

  render(<LeantimeDashboard />);

  await waitFor(() => expect(screen.getByText(/권한 없음/)).toBeInTheDocument());
  expect(screen.getByText(/leantime\.read 권한이 없어 프로젝트 정보를 볼 수 없습니다/)).toBeInTheDocument();
  // 다른 자원은 정상적으로 렌더된다(개별 자원별 오류 처리).
  expect(screen.getByText('표시할 담당 작업이 없습니다.')).toBeInTheDocument();
});

test('shows a session-expired state per resource on 401', async () => {
  fetchLeantimeProjectsMock.mockResolvedValue(readyEnvelope([]));
  fetchLeantimeTasksMock.mockRejectedValue(new ApiError('Unauthorized', 401));
  fetchLeantimeCalendarMock.mockResolvedValue(readyEnvelope([]));

  render(<LeantimeDashboard />);

  await waitFor(() => expect(screen.getByText('세션이 만료되었습니다. 다시 로그인한 뒤 새로고침해 주세요.')).toBeInTheDocument());
});

test('the deep-link href targets the current hostname and port', async () => {
  fetchLeantimeProjectsMock.mockResolvedValue(readyEnvelope([]));
  fetchLeantimeTasksMock.mockResolvedValue(readyEnvelope([]));
  fetchLeantimeCalendarMock.mockResolvedValue(readyEnvelope([]));

  render(<LeantimeDashboard port={9091} />);

  await waitFor(() => expect(screen.getByText('표시할 프로젝트가 없습니다.')).toBeInTheDocument());
  const link = screen.getByRole('link', { name: /원본 Leantime 새 탭으로 열기/ });
  expect(link).toHaveAttribute('target', '_blank');
  expect(link.getAttribute('href')).toBe(`${window.location.protocol}//${window.location.hostname}:9091`);
});

test('the refresh button refetches all three resources', async () => {
  fetchLeantimeProjectsMock.mockResolvedValue(readyEnvelope([]));
  fetchLeantimeTasksMock.mockResolvedValue(readyEnvelope([]));
  fetchLeantimeCalendarMock.mockResolvedValue(readyEnvelope([]));

  render(<LeantimeDashboard />);

  await waitFor(() => expect(fetchLeantimeProjectsMock).toHaveBeenCalledTimes(1));
  expect(fetchLeantimeTasksMock).toHaveBeenCalledTimes(1);
  expect(fetchLeantimeCalendarMock).toHaveBeenCalledTimes(1);

  await userEvent.click(screen.getByRole('button', { name: '새로고침' }));

  await waitFor(() => expect(fetchLeantimeProjectsMock).toHaveBeenCalledTimes(2));
  expect(fetchLeantimeTasksMock).toHaveBeenCalledTimes(2);
  expect(fetchLeantimeCalendarMock).toHaveBeenCalledTimes(2);
});

test('shows a generic error state without crashing when a resource rejects with a non-ApiError', async () => {
  fetchLeantimeProjectsMock.mockRejectedValue(new Error('network down'));
  fetchLeantimeTasksMock.mockResolvedValue(readyEnvelope([]));
  fetchLeantimeCalendarMock.mockResolvedValue(readyEnvelope([]));

  render(<LeantimeDashboard />);

  await waitFor(() => expect(screen.getByText(/프로젝트 정보를 불러오지 못했습니다\. \(network down\)/)).toBeInTheDocument());
});
