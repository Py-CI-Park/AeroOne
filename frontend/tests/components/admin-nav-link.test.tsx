import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';

import { AdminNavLink } from '@/components/layout/admin-nav-link';

const { fetchClientSessionMock } = vi.hoisted(() => ({
  fetchClientSessionMock: vi.fn(),
}));

vi.mock('@/lib/api', () => ({
  fetchClientSession: fetchClientSessionMock,
}));

beforeEach(() => {
  fetchClientSessionMock.mockReset();
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
    role: 'admin',
    isAdmin: true,
    permissions: [],
    resources: [],
  });

  render(<AdminNavLink active />);

  const admin = await screen.findByRole('link', { name: 'Admin' });
  expect(admin).toHaveAttribute('href', '/admin');
  expect(admin).toHaveAttribute('aria-current', 'page');
  expect(screen.queryByRole('link', { name: '로그인' })).not.toBeInTheDocument();
});

test('hides Admin and login for authenticated non-admin sessions', async () => {
  fetchClientSessionMock.mockResolvedValue({
    authenticated: true,
    role: 'user',
    isAdmin: false,
    permissions: [],
    resources: [],
  });

  render(<AdminNavLink />);

  await waitFor(() => expect(screen.queryByRole('link', { name: '로그인' })).not.toBeInTheDocument());
  expect(screen.queryByRole('link', { name: 'Admin' })).not.toBeInTheDocument();
});
