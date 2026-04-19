import React from 'react';
import { render, screen } from '@testing-library/react';

import { LoginForm } from '@/components/auth/login-form';

vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
  }),
}));

vi.mock('@/lib/api', () => ({
  login: vi.fn(),
}));

test('does not prefill the default administrator password', () => {
  render(<LoginForm />);

  expect(screen.getByPlaceholderText('아이디')).toHaveValue('admin');
  expect(screen.getByPlaceholderText('비밀번호')).toHaveValue('');
});
