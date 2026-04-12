import React from 'react';
import { render, screen } from '@testing-library/react';

import { AppShell } from '@/components/layout/app-shell';

test('renders the default shell with light theme classes', () => {
  render(
    <AppShell title="Light Shell">
      <p>content</p>
    </AppShell>,
  );

  const shell = screen.getByTestId('app-shell');
  const header = screen.getByTestId('app-shell-header');

  expect(shell).toHaveClass('bg-slate-100');
  expect(header).toHaveClass('bg-white');
  expect(screen.getByRole('heading', { name: 'Light Shell' })).toHaveClass('text-slate-900');
  expect(screen.getByText('사내 뉴스레터 / 문서 플랫폼')).toBeInTheDocument();
});

test('renders a dark shell when theme is dark', () => {
  render(
    <AppShell title="Dark Shell" theme="dark">
      <p>content</p>
    </AppShell>,
  );

  const shell = screen.getByTestId('app-shell');
  const header = screen.getByTestId('app-shell-header');

  expect(shell).toHaveClass('bg-slate-950');
  expect(header).toHaveClass('bg-slate-950');
  expect(screen.getByRole('heading', { name: 'Dark Shell' })).toHaveClass('text-slate-100');
});
