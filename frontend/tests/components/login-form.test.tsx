import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import { LoginForm } from '@/components/auth/login-form';

const { loginMock, locationAssignMock } = vi.hoisted(() => ({
  loginMock: vi.fn(),
  locationAssignMock: vi.fn(),
}));

vi.mock('@/lib/api', () => ({
  login: loginMock,
}));

beforeEach(() => {
  loginMock.mockReset();
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
});

test('redirects to the admin console after successful login', async () => {
  loginMock.mockResolvedValue({ access_token: 'ok' });

  render(<LoginForm />);

  fireEvent.change(screen.getByPlaceholderText('비밀번호'), { target: { value: 'secret' } });
  fireEvent.click(screen.getByRole('button', { name: '로그인' }));

  await waitFor(() => expect(loginMock).toHaveBeenCalledWith('admin', 'secret'));
  expect(locationAssignMock).toHaveBeenCalledWith('/admin');
});
