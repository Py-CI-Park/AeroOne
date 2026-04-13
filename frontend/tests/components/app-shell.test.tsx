import React from 'react';
import { render, screen } from '@testing-library/react';

import { AppShell } from '@/components/layout/app-shell';

test('renders the default shell with light theme classes and no theme selector', () => {
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
  expect(screen.queryByTestId('newsletter-theme-selector')).not.toBeInTheDocument();
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

test('renders compact theme selector after login when opted in', () => {
  render(
    <AppShell title="Theme Shell" theme="dark" showThemeSelector themeSlug="newsletter-20260330">
      <p>content</p>
    </AppShell>,
  );

  const login = screen.getByRole('link', { name: '로그인' });
  const selector = screen.getByTestId('newsletter-theme-selector');
  const toggle = screen.getByRole('link', { name: '라이트 테마로 전환' });

  expect(login.compareDocumentPosition(selector) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(toggle).toHaveAttribute('href', '/newsletters?slug=newsletter-20260330&theme=light');
  expect(toggle).toHaveTextContent('☀');
  expect(screen.queryByRole('link', { name: '다크 테마로 전환' })).not.toBeInTheDocument();
});
