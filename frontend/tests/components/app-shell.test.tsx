import React from 'react';
import { render, screen, within } from '@testing-library/react';

import { AppShell } from '@/components/layout/app-shell';

test('renders the default shell with light theme classes and a theme selector', () => {
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
  const nav = screen.getByRole('navigation');
  expect(within(nav).getByRole('link', { name: '대시보드' })).toHaveAttribute('href', '/');
  expect(within(nav).queryByText('Newsletter')).not.toBeInTheDocument();
  expect(within(nav).queryByRole('link', { name: 'Newsletter' })).not.toBeInTheDocument();
  expect(screen.queryByRole('link', { name: '뉴스레터' })).not.toBeInTheDocument();
  expect(screen.queryByRole('link', { name: '관리자' })).not.toBeInTheDocument();
  expect(screen.queryByRole('link', { name: '로그인' })).not.toBeInTheDocument();
  expect(screen.getByTestId('newsletter-theme-selector')).toBeInTheDocument();
});

test('can opt out of the theme selector', () => {
  render(
    <AppShell title="Plain Shell" showThemeSelector={false}>
      <p>content</p>
    </AppShell>,
  );

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

test('renders compact theme selector after dashboard link when a path is provided', () => {
  render(
    <AppShell title="Theme Shell" theme="dark" themePath="/newsletters?slug=newsletter-20260330">
      <p>content</p>
    </AppShell>,
  );

  const dashboard = screen.getByRole('link', { name: '대시보드' });
  const selector = screen.getByTestId('newsletter-theme-selector');
  const toggle = screen.getByRole('link', { name: '라이트 테마로 전환' });

  expect(dashboard.compareDocumentPosition(selector) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(toggle).toHaveAttribute('href', '/theme?theme=light&next=%2Fnewsletters%3Fslug%3Dnewsletter-20260330');
  expect(toggle).toHaveTextContent('☀');
  expect(screen.queryByRole('link', { name: '다크 테마로 전환' })).not.toBeInTheDocument();
});
