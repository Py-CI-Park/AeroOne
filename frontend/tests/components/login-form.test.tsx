import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import { LoginForm } from '@/components/auth/login-form';

const { fetchClientSessionMock, loginMock, locationAssignMock } = vi.hoisted(() => ({
  fetchClientSessionMock: vi.fn(),
  loginMock: vi.fn(),
  locationAssignMock: vi.fn(),
}));

vi.mock('@/lib/api', () => ({
  fetchClientSession: fetchClientSessionMock,
  login: loginMock,
}));

beforeEach(() => {
  loginMock.mockReset();
  fetchClientSessionMock.mockReset();
  fetchClientSessionMock.mockResolvedValue({ authenticated: true });
  locationAssignMock.mockReset();
});

Object.defineProperty(window, 'location', {
  value: {
    ...window.location,
    assign: locationAssignMock,
  },
  writable: true,
});

test('does not prefill the default administrator password', () => {
  render(<LoginForm />);

  expect(screen.getByPlaceholderText('아이디')).toHaveValue('admin');
  expect(screen.getByPlaceholderText('비밀번호')).toHaveValue('');
  expect(screen.getByRole('form', { name: 'AeroOne 접속' })).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: '계정 접속' })).toBeInTheDocument();
  expect(screen.queryByText('관리자 로그인')).not.toBeInTheDocument();
});

test('redirects to the dashboard by default after successful login', async () => {
  loginMock.mockResolvedValue({ access_token: 'ok' });

  render(<LoginForm />);

  fireEvent.change(screen.getByPlaceholderText('비밀번호'), { target: { value: 'secret' } });
  fireEvent.click(screen.getByRole('button', { name: '로그인' }));

  await waitFor(() => expect(loginMock).toHaveBeenCalledWith('admin', 'secret'));
  expect(locationAssignMock).toHaveBeenCalledWith('/');
});

test('redirects to a valid same-origin next target after successful login', async () => {
  loginMock.mockResolvedValue({ access_token: 'ok' });

  render(<LoginForm next="/documents/123?tab=preview#section" />);

  fireEvent.change(screen.getByPlaceholderText('비밀번호'), { target: { value: 'secret' } });
  fireEvent.click(screen.getByRole('button', { name: '로그인' }));

  await waitFor(() => expect(loginMock).toHaveBeenCalledWith('admin', 'secret'));
  expect(locationAssignMock).toHaveBeenCalledWith('/documents/123?tab=preview#section');
});

test('rejects a protocol-relative next target and falls back to the dashboard', async () => {
  loginMock.mockResolvedValue({ access_token: 'ok' });

  render(<LoginForm next="//evil.example" />);

  fireEvent.change(screen.getByPlaceholderText('비밀번호'), { target: { value: 'secret' } });
  fireEvent.click(screen.getByRole('button', { name: '로그인' }));

  await waitFor(() => expect(loginMock).toHaveBeenCalledWith('admin', 'secret'));
  expect(locationAssignMock).toHaveBeenCalledWith('/');
});

test('rejects a javascript: next target and falls back to the dashboard', async () => {
  loginMock.mockResolvedValue({ access_token: 'ok' });

  render(<LoginForm next="javascript:alert(1)" />);

  fireEvent.change(screen.getByPlaceholderText('비밀번호'), { target: { value: 'secret' } });
  fireEvent.click(screen.getByRole('button', { name: '로그인' }));

  await waitFor(() => expect(loginMock).toHaveBeenCalledWith('admin', 'secret'));
  expect(locationAssignMock).toHaveBeenCalledWith('/');
});

test('rejects an encoded traversal next target and falls back to the dashboard', async () => {
  loginMock.mockResolvedValue({ access_token: 'ok' });

  render(<LoginForm next="/%2F%2Fevil.example" />);

  fireEvent.change(screen.getByPlaceholderText('비밀번호'), { target: { value: 'secret' } });
  fireEvent.click(screen.getByRole('button', { name: '로그인' }));

  await waitFor(() => expect(loginMock).toHaveBeenCalledWith('admin', 'secret'));
  expect(locationAssignMock).toHaveBeenCalledWith('/');
});

test('keeps the error message on failed login and does not navigate', async () => {
  loginMock.mockRejectedValue(new Error('로그인 실패'));

  render(<LoginForm next="/dashboard" />);

  fireEvent.change(screen.getByPlaceholderText('비밀번호'), { target: { value: 'wrong' } });
  fireEvent.click(screen.getByRole('button', { name: '로그인' }));

  await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('로그인 실패'));
  expect(locationAssignMock).not.toHaveBeenCalled();
});

test('does not navigate when the session cookie is not confirmed after login', async () => {
  loginMock.mockResolvedValue({ access_token: 'ok' });
  fetchClientSessionMock.mockResolvedValue({ authenticated: false });

  render(<LoginForm next="/admin" />);

  fireEvent.change(screen.getByPlaceholderText('비밀번호'), { target: { value: 'secret' } });
  fireEvent.click(screen.getByRole('button', { name: '로그인' }));

  await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('로그인 상태를 확인하지 못했습니다'));
  expect(fetchClientSessionMock).toHaveBeenCalledTimes(5);
  expect(locationAssignMock).not.toHaveBeenCalled();
});
