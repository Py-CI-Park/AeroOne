import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import { LoginForm } from '@/components/auth/login-form';

const { loginMock, routerPushMock } = vi.hoisted(() => ({
  loginMock: vi.fn(),
  routerPushMock: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: routerPushMock,
  }),
}));

vi.mock('@/lib/api', () => ({
  login: loginMock,
}));

beforeEach(() => {
  loginMock.mockReset();
  routerPushMock.mockReset();
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
  expect(routerPushMock).toHaveBeenCalledWith('/admin');
});
