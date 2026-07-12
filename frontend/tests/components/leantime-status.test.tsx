import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { LeantimeStatus } from '@/components/office-tools/leantime-status';

const { fetchLeantimeHealthMock } = vi.hoisted(() => ({ fetchLeantimeHealthMock: vi.fn() }));

vi.mock('@/lib/api', () => ({ fetchLeantimeHealth: fetchLeantimeHealthMock }));

afterEach(() => {
  fetchLeantimeHealthMock.mockReset();
});

const UP = { status: 'up', probe_host: '127.0.0.1', port: 8081, probe_target: '127.0.0.1:8081' };
const DOWN = { status: 'down', probe_host: '127.0.0.1', port: 8081, probe_target: '127.0.0.1:8081' };

test('shows 구동 중 badge and an enabled 열기 link when Leantime is up', async () => {
  fetchLeantimeHealthMock.mockResolvedValue(UP);
  render(<LeantimeStatus />);

  await waitFor(() => expect(screen.getByText('구동 중')).toBeInTheDocument());
  const link = screen.getByRole('link', { name: /Leantime 새 탭으로 열기/ });
  expect(link).toHaveAttribute('target', '_blank');
  expect(link.getAttribute('href')).toMatch(/:8081$/);
});

test('shows 미설치 badge and a disabled 열기 control when Leantime is down', async () => {
  fetchLeantimeHealthMock.mockResolvedValue(DOWN);
  render(<LeantimeStatus />);

  await waitFor(() => expect(screen.getByText('미설치 · 미구동')).toBeInTheDocument());
  // 미구동이면 링크가 아니라 비활성 안내(눌러도 빈 화면이 뜨지 않게).
  expect(screen.queryByRole('link', { name: /Leantime 새 탭으로 열기/ })).not.toBeInTheDocument();
  expect(screen.getByText(/Leantime 열기 \(미구동\)/)).toBeInTheDocument();
});

test('re-checks health when 다시 확인 is pressed', async () => {
  fetchLeantimeHealthMock.mockResolvedValueOnce(DOWN).mockResolvedValueOnce(UP);
  render(<LeantimeStatus />);

  await waitFor(() => expect(screen.getByText('미설치 · 미구동')).toBeInTheDocument());
  await userEvent.click(screen.getByRole('button', { name: '다시 확인' }));
  await waitFor(() => expect(screen.getByText('구동 중')).toBeInTheDocument());
  expect(fetchLeantimeHealthMock).toHaveBeenCalledTimes(2);
});

test('falls back to a disabled control when the health fetch fails', async () => {
  fetchLeantimeHealthMock.mockRejectedValue(new Error('down'));
  render(<LeantimeStatus />);

  await waitFor(() => expect(fetchLeantimeHealthMock).toHaveBeenCalled());
  expect(screen.queryByRole('link', { name: /Leantime 새 탭으로 열기/ })).not.toBeInTheDocument();
});
