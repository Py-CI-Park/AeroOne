import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';

import { ActivityWorkspace } from '@/components/activity/activity-workspace';
import { ApiError } from '@/lib/api';
import type { AuthActivityResponse } from '@/lib/types';

const { fetchAuthActivityMock } = vi.hoisted(() => ({
  fetchAuthActivityMock: vi.fn(),
}));

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return { ...actual, fetchAuthActivity: fetchAuthActivityMock };
});

const FULL: AuthActivityResponse = {
  identity: { username: 'jsmith', display_name: '김철수', role: 'admin' },
  active_sessions: [
    { state: 'current', last_activity_at: '2026-07-12T01:02:03Z', device_label: '현재 기기' },
    { state: 'active', last_activity_at: '2026-07-11T23:00:00Z', device_label: '다른 활성 기기' },
  ],
  auth_events: [
    { kind: 'login', outcome: 'success', occurred_at: '2026-07-12T01:00:00Z' },
    { kind: 'login', outcome: 'failure', occurred_at: '2026-07-11T22:00:00Z' },
    { kind: 'logout', outcome: 'success', occurred_at: '2026-07-11T21:00:00Z' },
  ],
  ai_requests: [
    { status: 'completed', module_key: null, occurred_at: '2026-07-12T00:30:00Z' },
    { status: 'failed', module_key: null, occurred_at: '2026-07-11T20:00:00Z' },
  ],
  accessible_modules: [
    { key: 'newsletters', label: 'Newsletter' },
    { key: 'documents', label: 'Document' },
  ],
};

const EMPTY: AuthActivityResponse = {
  identity: { username: 'newbie', display_name: null, role: 'pending' },
  active_sessions: [],
  auth_events: [],
  ai_requests: [],
  accessible_modules: [],
};

afterEach(() => {
  vi.restoreAllMocks();
  fetchAuthActivityMock.mockReset();
});

test('shows a loading state before the fetch resolves', async () => {
  let resolveFetch: (value: AuthActivityResponse) => void = () => {};
  fetchAuthActivityMock.mockReturnValue(
    new Promise<AuthActivityResponse>((resolve) => {
      resolveFetch = resolve;
    }),
  );

  render(<ActivityWorkspace />);

  expect(screen.getByTestId('activity-loading')).toBeInTheDocument();

  resolveFetch(EMPTY);
  await waitFor(() => expect(screen.queryByTestId('activity-loading')).not.toBeInTheDocument());
});

test('renders a login prompt with the exact next link on 401', async () => {
  fetchAuthActivityMock.mockRejectedValue(new ApiError('로그인이 필요합니다', 401));

  render(<ActivityWorkspace />);

  const prompt = await screen.findByTestId('activity-unauthorized');
  expect(prompt).toHaveTextContent('로그인이 필요합니다');
  const link = screen.getByRole('link', { name: '로그인 페이지로 이동' });
  expect(link).toHaveAttribute('href', '/login?next=%2Factivity');
});

test('renders a safe error message with a retry button that re-fetches on other errors', async () => {
  fetchAuthActivityMock.mockRejectedValueOnce(new ApiError('서버 오류가 발생했습니다', 500));
  fetchAuthActivityMock.mockResolvedValueOnce(EMPTY);

  render(<ActivityWorkspace />);

  const errorBox = await screen.findByTestId('activity-error');
  expect(errorBox).toHaveTextContent('서버 오류가 발생했습니다');
  expect(screen.queryByTestId('activity-unauthorized')).not.toBeInTheDocument();

  const { fireEvent } = await import('@testing-library/react');
  fireEvent.click(screen.getByTestId('activity-retry'));

  await waitFor(() => expect(fetchAuthActivityMock).toHaveBeenCalledTimes(2));
  await waitFor(() => expect(screen.getByTestId('activity-username')).toHaveTextContent('newbie'));
});

test('renders full fixture data with role labels, current device distinction, and module chips', async () => {
  fetchAuthActivityMock.mockResolvedValue(FULL);

  render(<ActivityWorkspace />);

  expect(await screen.findByTestId('activity-username')).toHaveTextContent('jsmith');
  expect(screen.getByTestId('activity-display-name')).toHaveTextContent('김철수');
  expect(screen.getByTestId('activity-role')).toHaveTextContent('관리자');

  const sessionsList = screen.getByTestId('activity-sessions-list');
  expect(sessionsList).toHaveTextContent('현재 기기');
  expect(sessionsList).toHaveTextContent('다른 활성 기기');
  expect(screen.getByTestId('activity-session-current-badge')).toHaveTextContent('현재 세션');

  const eventsTable = screen.getByTestId('activity-auth-events-table');
  expect(eventsTable).toHaveTextContent('로그인');
  expect(eventsTable).toHaveTextContent('로그아웃');
  expect(eventsTable).toHaveTextContent('성공');
  expect(eventsTable).toHaveTextContent('실패');

  const aiTable = screen.getByTestId('activity-ai-requests-table');
  expect(aiTable).toHaveTextContent('완료');
  expect(aiTable).toHaveTextContent('실패');
  // module_key null renders as an em dash placeholder rather than blank.
  expect(aiTable.textContent).toContain('—');

  const modulesList = screen.getByTestId('activity-modules-list');
  expect(modulesList).toHaveTextContent('Newsletter');
  expect(modulesList).toHaveTextContent('Document');

  // No pagination controls anywhere on this page.
  expect(screen.queryByRole('button', { name: /다음|이전|next|prev/i })).not.toBeInTheDocument();
  expect(screen.queryByTestId(/pagination/)).not.toBeInTheDocument();
});

test('renders explicit Korean empty states for every section when arrays are empty', async () => {
  fetchAuthActivityMock.mockResolvedValue(EMPTY);

  render(<ActivityWorkspace />);

  expect(await screen.findByTestId('activity-username')).toHaveTextContent('newbie');
  expect(screen.getByTestId('activity-role')).toHaveTextContent('승인 대기');
  expect(screen.queryByTestId('activity-display-name')).not.toBeInTheDocument();

  expect(screen.getByTestId('activity-sessions-empty')).toHaveTextContent('활성 세션이 없습니다.');
  expect(screen.getByTestId('activity-auth-events-empty')).toHaveTextContent('로그인 기록이 없습니다.');
  expect(screen.getByTestId('activity-ai-requests-empty')).toHaveTextContent('AI 요청 기록이 없습니다.');
  expect(screen.getByTestId('activity-modules-empty')).toHaveTextContent('이용 가능한 모듈이 없습니다.');
});
