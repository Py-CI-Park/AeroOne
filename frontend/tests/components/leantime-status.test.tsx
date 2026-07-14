import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { LeantimeStatus } from '@/components/office-tools/leantime-status';

const { fetchLeantimeHealthMock } = vi.hoisted(() => ({ fetchLeantimeHealthMock: vi.fn() }));

vi.mock('@/lib/api', () => ({ fetchLeantimeHealth: fetchLeantimeHealthMock }));

afterEach(() => {
  fetchLeantimeHealthMock.mockReset();
});

const READY = {
  status: 'ready',
  probe_host: '127.0.0.1',
  port: 8081,
  probe_target: '127.0.0.1:8081',
  launch_url: 'http://127.0.0.1:8081',
  checked_at: '2026-07-14T00:00:00Z',
  latency_ms: 42,
  detail: '정상 응답',
  app_identified: true,
};

const STARTING = {
  status: 'starting',
  probe_host: '127.0.0.1',
  port: 8081,
  probe_target: '127.0.0.1:8081',
  launch_url: 'http://127.0.0.1:8081',
  checked_at: '2026-07-14T00:00:00Z',
  latency_ms: null,
  detail: 'TCP 는 연결되지만 HTTP 응답이 아직 없습니다.',
  app_identified: false,
};

const UNHEALTHY = {
  status: 'unhealthy',
  probe_host: '127.0.0.1',
  port: 8081,
  probe_target: '127.0.0.1:8081',
  launch_url: 'http://127.0.0.1:8081',
  checked_at: '2026-07-14T00:00:00Z',
  latency_ms: 15,
  detail: 'Leantime 으로 식별되지 않는 응답입니다.',
  app_identified: false,
};

const ABSENT = {
  status: 'absent',
  probe_host: '127.0.0.1',
  port: 8081,
  probe_target: '127.0.0.1:8081',
  launch_url: 'http://127.0.0.1:8081',
  checked_at: '2026-07-14T00:00:00Z',
  latency_ms: null,
  detail: '연결이 거부되었습니다.',
  app_identified: false,
};

const ERROR = {
  status: 'error',
  probe_host: '127.0.0.1',
  port: 8081,
  probe_target: '127.0.0.1:8081',
  launch_url: 'http://127.0.0.1:8081',
  checked_at: '2026-07-14T00:00:00Z',
  latency_ms: null,
  detail: '설정 오류가 발생했습니다.',
  app_identified: false,
};

test('shows 구동 중 badge and an enabled 열기 link when Leantime is ready', async () => {
  fetchLeantimeHealthMock.mockResolvedValue(READY);
  render(<LeantimeStatus />);

  await waitFor(() => expect(screen.getByText('구동 중')).toBeInTheDocument());
  const link = screen.getByRole('link', { name: /Leantime 새 탭으로 열기/ });
  expect(link).toHaveAttribute('target', '_blank');
  expect(link.getAttribute('href')).toMatch(/:8081$/);
});

test('shows 기동 중 badge and a disabled 열기 control when Leantime is starting', async () => {
  fetchLeantimeHealthMock.mockResolvedValue(STARTING);
  render(<LeantimeStatus />);

  await waitFor(() => expect(screen.getByText('기동 중')).toBeInTheDocument());
  expect(screen.queryByRole('link', { name: /Leantime 새 탭으로 열기/ })).not.toBeInTheDocument();
  expect(screen.getByText(/Leantime 열기 \(미구동\)/)).toBeInTheDocument();
  expect(screen.getByText(new RegExp(STARTING.detail))).toBeInTheDocument();
});

test('shows 응답 이상 badge, detail reason, and a disabled 열기 control when Leantime is unhealthy', async () => {
  fetchLeantimeHealthMock.mockResolvedValue(UNHEALTHY);
  render(<LeantimeStatus />);

  await waitFor(() => expect(screen.getByText('응답 이상')).toBeInTheDocument());
  expect(screen.queryByRole('link', { name: /Leantime 새 탭으로 열기/ })).not.toBeInTheDocument();
  expect(screen.getByText(/Leantime 열기 \(미구동\)/)).toBeInTheDocument();
  expect(screen.getByText(new RegExp(UNHEALTHY.detail))).toBeInTheDocument();
});

test('shows 미설치 badge and a disabled 열기 control when Leantime is absent', async () => {
  fetchLeantimeHealthMock.mockResolvedValue(ABSENT);
  render(<LeantimeStatus />);

  await waitFor(() => expect(screen.getByText('미설치 · 미구동')).toBeInTheDocument());
  // 미구동이면 링크가 아니라 비활성 안내(눌러도 빈 화면이 뜨지 않게).
  expect(screen.queryByRole('link', { name: /Leantime 새 탭으로 열기/ })).not.toBeInTheDocument();
  expect(screen.getByText(/Leantime 열기 \(미구동\)/)).toBeInTheDocument();
});

test('shows 확인 실패 badge, detail reason, and a disabled 열기 control when the probe errors', async () => {
  fetchLeantimeHealthMock.mockResolvedValue(ERROR);
  render(<LeantimeStatus />);

  await waitFor(() => expect(screen.getByText('확인 실패')).toBeInTheDocument());
  expect(screen.queryByRole('link', { name: /Leantime 새 탭으로 열기/ })).not.toBeInTheDocument();
  expect(screen.getByText(new RegExp(ERROR.detail))).toBeInTheDocument();
});

test('re-checks health when 다시 확인 is pressed', async () => {
  fetchLeantimeHealthMock.mockResolvedValueOnce(ABSENT).mockResolvedValueOnce(READY);
  render(<LeantimeStatus />);

  await waitFor(() => expect(screen.getByText('미설치 · 미구동')).toBeInTheDocument());
  await userEvent.click(screen.getByRole('button', { name: '다시 확인' }));
  await waitFor(() => expect(screen.getByText('구동 중')).toBeInTheDocument());
  expect(fetchLeantimeHealthMock).toHaveBeenCalledTimes(2);
});

test('falls back to the 확인 실패 state with no launch link when the health fetch rejects', async () => {
  fetchLeantimeHealthMock.mockRejectedValue(new Error('down'));
  render(<LeantimeStatus />);

  await waitFor(() => expect(screen.getByText('확인 실패')).toBeInTheDocument());
  expect(screen.queryByRole('link', { name: /Leantime 새 탭으로 열기/ })).not.toBeInTheDocument();
});
