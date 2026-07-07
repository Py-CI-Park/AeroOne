import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

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

test('renders login and hides Admin when session fetch rejects', async () => {
  fetchClientSessionMock.mockRejectedValue(new Error('backend down'));

  render(<AdminNavLink />);

  await waitFor(() => expect(fetchClientSessionMock).toHaveBeenCalledTimes(1));
  expect(screen.getByRole('link', { name: '로그인' })).toHaveAttribute('href', '/login');
  expect(screen.queryByRole('link', { name: 'Admin' })).not.toBeInTheDocument();
});

test('renders login and hides Admin when authentication is unknown', async () => {
  fetchClientSessionMock.mockResolvedValue({
    authenticated: null,
    username: null,
    role: null,
    isAdmin: false,
    permissions: [],
    resources: [],
  });

  render(<AdminNavLink />);

  await waitFor(() => expect(fetchClientSessionMock).toHaveBeenCalledTimes(1));
  expect(screen.getByRole('link', { name: '로그인' })).toHaveAttribute('href', '/login');
  expect(screen.queryByRole('link', { name: 'Admin' })).not.toBeInTheDocument();
});

test('renders login and hides Admin when unauthenticated', async () => {
  fetchClientSessionMock.mockResolvedValue({
    authenticated: false,
    username: null,
    role: null,
    isAdmin: false,
    permissions: [],
    resources: [],
  });

  render(<AdminNavLink />);

  await waitFor(() => expect(fetchClientSessionMock).toHaveBeenCalledTimes(1));
  expect(screen.getByRole('link', { name: '로그인' })).toHaveAttribute('href', '/login');
  expect(screen.queryByRole('link', { name: 'Admin' })).not.toBeInTheDocument();
});

test('renders Admin only when the session is confirmed admin', async () => {
  fetchClientSessionMock.mockResolvedValue({
    authenticated: true,
    username: 'admin',
    role: 'admin',
    isAdmin: true,
    permissions: [],
    resources: [],
  });

  render(<AdminNavLink active />);

  const admin = await screen.findByRole('link', { name: 'Admin' });
  expect(screen.getByText('admin')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: '로그아웃' })).toBeInTheDocument();
  expect(admin).toHaveAttribute('href', '/admin');
  expect(admin).toHaveAttribute('aria-current', 'page');
  expect(screen.queryByRole('link', { name: '로그인' })).not.toBeInTheDocument();
});

test('renders login identity and logout for authenticated non-admin sessions without Admin link', async () => {
  fetchClientSessionMock.mockResolvedValue({
    authenticated: true,
    username: 'analyst',
    role: 'user',
    isAdmin: false,
    permissions: [],
    resources: [],
  });

  render(<AdminNavLink />);

  await waitFor(() => expect(screen.queryByRole('link', { name: '로그인' })).not.toBeInTheDocument());
  expect(screen.getByText('analyst')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: '로그아웃' })).toBeInTheDocument();
  expect(screen.queryByRole('link', { name: 'Admin' })).not.toBeInTheDocument();
});

test('posts logout and redirects to login', async () => {
  fetchClientSessionMock.mockResolvedValue({
    authenticated: true,
    username: 'admin',
    role: 'admin',
    isAdmin: true,
    permissions: [],
    resources: [],
  });
  logoutMock.mockResolvedValue({ status: 'ok' });

  render(<AdminNavLink />);

  fireEvent.click(await screen.findByRole('button', { name: '로그아웃' }));

  await waitFor(() => expect(logoutMock).toHaveBeenCalledTimes(1));
  expect(locationAssignMock).toHaveBeenCalledWith('/login');
});
