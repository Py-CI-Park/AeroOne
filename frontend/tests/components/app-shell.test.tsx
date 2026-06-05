import React from 'react';
import { render, screen, within } from '@testing-library/react';

import { AppShell } from '@/components/layout/app-shell';

// Claude Design 핸드오프 적용 후 셸 계약:
// - 테마는 data-theme 속성으로 표현 (토큰 CSS 변수가 색을 스위치).
// - 헤더 nav 는 Dashboard + Newsletter 영문 라벨 (디자인 시안 기준).
// - 관리자/로그인 링크는 헤더에 노출하지 않음.
test('renders the default shell with light data-theme and a theme selector', () => {
  render(
    <AppShell title="Light Shell">
      <p>content</p>
    </AppShell>,
  );

  const shell = screen.getByTestId('app-shell');
  const header = screen.getByTestId('app-shell-header');

  expect(shell).toHaveClass('bg-surface-base');
  expect(header).toHaveClass('bg-surface-raised');
  expect(screen.getByRole('heading', { name: 'Light Shell' })).toHaveClass('text-ink-1');
  // 테마는 <html> 에 부착되므로 셸은 data-theme 를 갖지 않는다. light → 토글은 dark 전환을 제시.
  expect(shell).not.toHaveAttribute('data-theme');
  expect(screen.getByRole('link', { name: '다크 테마로 전환' })).toBeInTheDocument();

  const nav = screen.getByRole('navigation');
  expect(within(nav).getByRole('link', { name: 'Dashboard' })).toHaveAttribute('href', '/');
  expect(within(nav).getByRole('link', { name: 'Newsletter' })).toHaveAttribute('href', '/newsletters');
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

  expect(shell).toHaveClass('bg-surface-base');
  expect(header).toHaveClass('bg-surface-raised');
  expect(screen.getByRole('heading', { name: 'Dark Shell' })).toHaveClass('text-ink-1');
  // dark → 토글은 light 전환을 제시.
  expect(screen.getByRole('link', { name: '라이트 테마로 전환' })).toBeInTheDocument();
});

test('marks the active nav item and exposes the page title meta + actions', () => {
  render(
    <AppShell
      title="Newsletter"
      active="newsletters"
      titleMeta="142 issues"
      titleActions={<button type="button">Grid</button>}
    >
      <p>content</p>
    </AppShell>,
  );

  const nav = screen.getByRole('navigation');
  expect(within(nav).getByRole('link', { name: 'Newsletter' })).toHaveAttribute('aria-current', 'page');
  expect(within(nav).getByRole('link', { name: 'Dashboard' })).not.toHaveAttribute('aria-current');
  expect(screen.getByText('142 issues')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Grid' })).toBeInTheDocument();
});

test('top nav renders exactly 3 links: Dashboard, Newsletter, Document — and not NSA, Ladder, or Civil', () => {
  render(
    <AppShell title="Nav Guard">
      <p>content</p>
    </AppShell>,
  );

  const nav = screen.getByRole('navigation');
  const navLinks = within(nav).getAllByRole('link');

  expect(navLinks).toHaveLength(3);
  expect(within(nav).getByRole('link', { name: 'Dashboard' })).toBeInTheDocument();
  expect(within(nav).getByRole('link', { name: 'Newsletter' })).toBeInTheDocument();
  expect(within(nav).getByRole('link', { name: 'Document' })).toBeInTheDocument();
  expect(within(nav).queryByRole('link', { name: /NSA/i })).not.toBeInTheDocument();
  expect(within(nav).queryByRole('link', { name: /Ladder/i })).not.toBeInTheDocument();
  expect(within(nav).queryByRole('link', { name: /Civil/i })).not.toBeInTheDocument();
});

test('renders compact theme selector after dashboard link when a path is provided', () => {
  render(
    <AppShell title="Theme Shell" theme="dark" themePath="/newsletters?slug=newsletter-20260330">
      <p>content</p>
    </AppShell>,
  );

  const dashboard = screen.getByRole('link', { name: 'Dashboard' });
  const selector = screen.getByTestId('newsletter-theme-selector');
  const toggle = screen.getByRole('link', { name: '라이트 테마로 전환' });

  expect(dashboard.compareDocumentPosition(selector) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(toggle).toHaveAttribute('href', '/theme?theme=light&next=%2Fnewsletters%3Fslug%3Dnewsletter-20260330');
  expect(toggle).toHaveTextContent('☀');
  expect(screen.queryByRole('link', { name: '다크 테마로 전환' })).not.toBeInTheDocument();
});
