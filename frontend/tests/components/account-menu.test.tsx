import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { AccountMenu } from '@/components/layout/account-menu';

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

function adminSession() {
  return {
    authenticated: true,
    username: 'admin',
    role: 'admin',
    is_admin: true,
    can_view_document: true,
    can_view_nsa: true,
    can_use_ai: true,
    permissions: [],
    resources: [],
  };
}

function analystSession() {
  return {
    authenticated: true,
    username: 'analyst',
    role: 'user',
    is_admin: false,
    can_view_document: true,
    can_view_nsa: false,
    can_use_ai: false,
    permissions: [],
    resources: [],
  };
}

test('keeps the login entry visible and hides privileged surfaces while the session is unknown', () => {
  fetchClientSessionMock.mockReturnValue(new Promise(() => {}));

  render(<AccountMenu />);

  expect(screen.getByRole('link', { name: '로그인' })).toHaveAttribute('href', '/login');
  expect(screen.queryByRole('link', { name: 'Admin' })).not.toBeInTheDocument();
  expect(screen.queryByRole('link', { name: '내 활동' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /로그아웃/ })).not.toBeInTheDocument();
});

test('renders login and hides Admin when session fetch rejects', async () => {
  fetchClientSessionMock.mockRejectedValue(new Error('backend down'));

  render(<AccountMenu />);

  await waitFor(() => expect(fetchClientSessionMock).toHaveBeenCalledTimes(1));
  expect(screen.getByRole('link', { name: '로그인' })).toHaveAttribute('href', '/login');
  expect(screen.queryByRole('button', { name: /사용자/ })).not.toBeInTheDocument();
});

test('renders login when the session resolves ambiguous (authenticated: null)', async () => {
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

  render(<AccountMenu />);

  expect(await screen.findByRole('link', { name: '로그인' })).toHaveAttribute('href', '/login');
});

test('renders login when unauthenticated', async () => {
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

  render(<AccountMenu />);

  expect(await screen.findByRole('link', { name: '로그인' })).toHaveAttribute('href', '/login');
});

test('authenticated admin: trigger is a real button and opening reveals 내 활동 + Admin + 로그아웃', async () => {
  const user = userEvent.setup();
  fetchClientSessionMock.mockResolvedValue(adminSession());

  render(<AccountMenu active />);

  const trigger = await screen.findByRole('button', { name: /현재 로그인 사용자 admin/ });
  expect(trigger).toHaveAttribute('aria-haspopup', 'menu');
  expect(trigger).toHaveAttribute('aria-expanded', 'false');
  expect(screen.queryByRole('menu')).not.toBeInTheDocument();

  await user.click(trigger);

  expect(trigger).toHaveAttribute('aria-expanded', 'true');
  const menu = screen.getByRole('menu');
  const activity = screen.getByRole('menuitem', { name: '내 활동' });
  const admin = screen.getByRole('menuitem', { name: 'Admin' });
  expect(activity).toHaveAttribute('href', '/activity');
  expect(admin).toHaveAttribute('href', '/admin');
  expect(admin).toHaveAttribute('aria-current', 'page');
  expect(screen.getByRole('menuitem', { name: '로그아웃' })).toBeInTheDocument();
  expect(menu).toBeInTheDocument();
});

test('authenticated non-admin: 내 활동 link present, no Admin entry', async () => {
  const user = userEvent.setup();
  fetchClientSessionMock.mockResolvedValue(analystSession());

  render(<AccountMenu />);

  const trigger = await screen.findByRole('button', { name: /현재 로그인 사용자 analyst/ });
  await user.click(trigger);

  expect(screen.getByRole('menuitem', { name: '내 활동' })).toHaveAttribute('href', '/activity');
  expect(screen.queryByRole('menuitem', { name: 'Admin' })).not.toBeInTheDocument();
  expect(screen.getByRole('menuitem', { name: '로그아웃' })).toBeInTheDocument();
});

test('menu keyboard flow: Escape closes the menu and returns focus to the trigger', async () => {
  const user = userEvent.setup();
  fetchClientSessionMock.mockResolvedValue(analystSession());

  render(<AccountMenu />);

  const trigger = await screen.findByRole('button', { name: /현재 로그인 사용자 analyst/ });
  await user.click(trigger);
  expect(screen.getByRole('menu')).toBeInTheDocument();

  await user.keyboard('{Escape}');

  await waitFor(() => expect(screen.queryByRole('menu')).not.toBeInTheDocument());
  expect(trigger).toHaveAttribute('aria-expanded', 'false');
  expect(trigger).toHaveFocus();
});

test('clicking the trigger again toggles the menu closed', async () => {
  const user = userEvent.setup();
  fetchClientSessionMock.mockResolvedValue(analystSession());

  render(<AccountMenu />);

  const trigger = await screen.findByRole('button', { name: /현재 로그인 사용자 analyst/ });
  await user.click(trigger);
  expect(screen.getByRole('menu')).toBeInTheDocument();

  await user.click(trigger);

  expect(screen.queryByRole('menu')).not.toBeInTheDocument();
  expect(trigger).toHaveAttribute('aria-expanded', 'false');
});

test('posts logout and redirects to login', async () => {
  fetchClientSessionMock.mockResolvedValue(adminSession());
  logoutMock.mockResolvedValue({ status: 'ok' });

  render(<AccountMenu />);

  const trigger = await screen.findByRole('button', { name: /현재 로그인 사용자 admin/ });
  fireEvent.click(trigger);
  fireEvent.click(screen.getByRole('menuitem', { name: '로그아웃' }));

  await waitFor(() => expect(logoutMock).toHaveBeenCalledTimes(1));
  expect(locationAssignMock).toHaveBeenCalledWith('/login');
});

test('shows a visible failure state when logout rejects', async () => {
  fetchClientSessionMock.mockResolvedValue(adminSession());
  logoutMock.mockRejectedValue(new Error('logout failed'));

  render(<AccountMenu />);

  const trigger = await screen.findByRole('button', { name: /현재 로그인 사용자 admin/ });
  fireEvent.click(trigger);
  fireEvent.click(screen.getByRole('menuitem', { name: '로그아웃' }));

  expect(await screen.findByRole('alert')).toHaveTextContent('로그아웃 실패');
  expect(locationAssignMock).not.toHaveBeenCalled();
});
