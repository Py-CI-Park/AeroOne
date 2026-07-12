import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { AdminNavLink } from '@/components/layout/admin-nav-link';

const { fetchClientSessionMock, logoutMock, locationAssignMock } = vi.hoisted(() => ({
  fetchClientSessionMock: vi.fn(),
  logoutMock: vi.fn(),
  locationAssignMock: vi.fn(),
}));

vi.mock('@/lib/api', () => ({
  fetchClientSession: fetchClientSessionMock,
  logout: logoutMock,
}));

beforeEach(() => {
  fetchClientSessionMock.mockReset();
  logoutMock.mockReset();
  locationAssignMock.mockReset();
});

Object.defineProperty(window, 'location', {
  value: {
    ...window.location,
    assign: locationAssignMock,
  },
  writable: true,
});

// AdminNavLink 는 AccountMenu 로 대체된 얇은 재노출(re-export) shim 이다. 트리거 버튼
// 뒤에 드롭다운(내 활동/Admin/로그아웃)을 숨겨두므로 여기서도 동일한 계약을 검증한다.

test('renders login and hides Admin when session fetch rejects', async () => {
  fetchClientSessionMock.mockRejectedValue(new Error('backend down'));

  render(<AdminNavLink />);

  await waitFor(() => expect(fetchClientSessionMock).toHaveBeenCalledTimes(1));
  expect(screen.getByRole('link', { name: '로그인' })).toHaveAttribute('href', '/login');
  expect(screen.queryByRole('menuitem', { name: 'Admin' })).not.toBeInTheDocument();
});

test('renders login and hides Admin when authentication is unknown', async () => {
  fetchClientSessionMock.mockResolvedValue({
    authenticated: null,
    username: null,
    role: null,
    is_admin: false,
    can_view_document: true,
    can_view_nsa: false,
    can_use_ai: false,
    permissions: [],
    resources: [],
  });

  render(<AdminNavLink />);

  expect(await screen.findByRole('link', { name: '로그인' })).toHaveAttribute('href', '/login');
  expect(screen.queryByRole('menuitem', { name: 'Admin' })).not.toBeInTheDocument();
});

test('renders login and hides Admin when unauthenticated', async () => {
  fetchClientSessionMock.mockResolvedValue({
    authenticated: false,
    username: null,
    role: null,
    is_admin: false,
    can_view_document: true,
    can_view_nsa: false,
    can_use_ai: false,
    permissions: [],
    resources: [],
  });

  render(<AdminNavLink />);

  expect(await screen.findByRole('link', { name: '로그인' })).toHaveAttribute('href', '/login');
  expect(screen.queryByRole('menuitem', { name: 'Admin' })).not.toBeInTheDocument();
});

test('renders Admin only when the session is confirmed admin', async () => {
  const user = userEvent.setup();
  fetchClientSessionMock.mockResolvedValue({
    authenticated: true,
    username: 'admin',
    role: 'admin',
    is_admin: true,
    can_view_document: true,
    can_view_nsa: true,
    can_use_ai: true,
    permissions: [],
    resources: [],
  });

  render(<AdminNavLink active />);

  const trigger = await screen.findByRole('button', { name: /현재 로그인 사용자 admin/ });
  expect(screen.getByText('admin')).toBeInTheDocument();
  expect(screen.queryByRole('link', { name: '로그인' })).not.toBeInTheDocument();

  await user.click(trigger);

  const admin = screen.getByRole('menuitem', { name: 'Admin' });
  expect(admin).toHaveAttribute('href', '/admin');
  expect(admin).toHaveAttribute('aria-current', 'page');
  expect(screen.getByRole('menuitem', { name: '내 활동' })).toHaveAttribute('href', '/activity');
  expect(screen.getByRole('menuitem', { name: '로그아웃' })).toBeInTheDocument();
});

test('renders login identity and logout for authenticated non-admin sessions without Admin link', async () => {
  const user = userEvent.setup();
  fetchClientSessionMock.mockResolvedValue({
    authenticated: true,
    username: 'analyst',
    role: 'user',
    is_admin: false,
    can_view_document: true,
    can_view_nsa: false,
    can_use_ai: false,
    permissions: [],
    resources: [],
  });

  render(<AdminNavLink />);

  const trigger = await screen.findByRole('button', { name: /현재 로그인 사용자 analyst/ });
  expect(screen.getByText('analyst')).toBeInTheDocument();
  expect(screen.queryByRole('link', { name: '로그인' })).not.toBeInTheDocument();

  await user.click(trigger);

  expect(screen.getByRole('menuitem', { name: '내 활동' })).toHaveAttribute('href', '/activity');
  expect(screen.getByRole('menuitem', { name: '로그아웃' })).toBeInTheDocument();
  expect(screen.queryByRole('menuitem', { name: 'Admin' })).not.toBeInTheDocument();
});

test('posts logout and redirects to login', async () => {
  fetchClientSessionMock.mockResolvedValue({
    authenticated: true,
    username: 'admin',
    role: 'admin',
    is_admin: true,
    can_view_document: true,
    can_view_nsa: true,
    can_use_ai: true,
    permissions: [],
    resources: [],
  });
  logoutMock.mockResolvedValue({ status: 'ok' });

  render(<AdminNavLink />);

  const trigger = await screen.findByRole('button', { name: /현재 로그인 사용자 admin/ });
  fireEvent.click(trigger);
  fireEvent.click(screen.getByRole('menuitem', { name: '로그아웃' }));

  await waitFor(() => expect(logoutMock).toHaveBeenCalledTimes(1));
  expect(locationAssignMock).toHaveBeenCalledWith('/login');
});
