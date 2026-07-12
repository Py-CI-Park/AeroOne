import React from 'react';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { AppShell } from '@/components/layout/app-shell';
const { fetchClientSessionMock, logoutMock } = vi.hoisted(() => ({
  fetchClientSessionMock: vi.fn(),
  logoutMock: vi.fn(),
}));

vi.mock('@/lib/api', () => ({
  fetchClientSession: fetchClientSessionMock,
  logout: logoutMock,
}));

beforeEach(() => {
  fetchClientSessionMock.mockReset();
  logoutMock.mockReset();
  fetchClientSessionMock.mockReturnValue(new Promise(() => {}));
});


// Claude Design 핸드오프 적용 후 셸 계약:
// - 테마는 data-theme 속성으로 표현 (토큰 CSS 변수가 색을 스위치).
// - 헤더 nav 는 Dashboard + Newsletter 영문 라벨 (디자인 시안 기준).
// - 관리자 링크는 헤더 메인 nav 가 아니라 확인된 관리자용 클라이언트 링크로만 노출한다.
test('renders the default shell with light data-theme and a theme selector', async () => {
  fetchClientSessionMock.mockResolvedValue({
    authenticated: false,
    username: null,
    role: null,
    is_admin: false,
    can_view_document: true,
    can_view_nsa: false,
    can_use_ai: false,
    permissions: [],
    resources: [],
  });

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
  expect(screen.queryByRole('link', { name: 'Admin' })).not.toBeInTheDocument();
  expect(await screen.findByRole('link', { name: '로그인' })).toHaveAttribute('href', '/login');
  expect(screen.getByTestId('newsletter-theme-selector')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: '검색' })).not.toBeInTheDocument();
});

test('opens the usage manual popup from the header', async () => {
  const user = userEvent.setup();

  render(
    <AppShell title="Manual Shell">
      <p>content</p>
    </AppShell>,
  );

  const manualButton = screen.getByRole('button', { name: '사용법' });
  const themeToggle = screen.getByRole('link', { name: '다크 테마로 전환' });
  expect(themeToggle.compareDocumentPosition(manualButton) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();

  await user.click(manualButton);

  expect(screen.getByRole('dialog', { name: '전체 기능 사용법' })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'AeroAI' })).toBeInTheDocument();

  await user.click(screen.getByRole('button', { name: 'AeroAI' }));

  expect(screen.getByRole('heading', { name: 'AeroAI 채팅과 문서 근거 (개발중)' })).toBeInTheDocument();
  expect(screen.getByText(/개발중 섹션의 Active 카드/)).toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: '대시보드' }));
  expect(screen.getAllByText(/현재 서비스 중/).length).toBeGreaterThan(0);
  expect(screen.getByText(/Viewer, AeroAI, Notebook, Ladder/)).toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: '관리자' }));
  expect(screen.getByText(/자격 증명 사고 대응 런북/)).toBeInTheDocument();
  expect(screen.queryByText(/초기 비밀번호는 \d+/)).not.toBeInTheDocument();

  await user.click(screen.getByRole('button', { name: '닫기' }));

  expect(screen.queryByRole('dialog', { name: '전체 기능 사용법' })).not.toBeInTheDocument();
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

test('top nav renders exactly 3 links: Dashboard, Newsletter, Document — Admin is operator-only and not in the main nav', () => {
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
  expect(within(nav).queryByRole('link', { name: 'Admin' })).not.toBeInTheDocument();
  expect(within(nav).queryByRole('link', { name: /NSA/i })).not.toBeInTheDocument();
  expect(within(nav).queryByRole('link', { name: /Ladder/i })).not.toBeInTheDocument();
  expect(within(nav).queryByRole('link', { name: /Civil/i })).not.toBeInTheDocument();
});

test('uses a wrapping header/nav layout so narrow dashboard screens do not overflow', () => {
  render(
    <AppShell title="Responsive Shell">
      <p>content</p>
    </AppShell>,
  );

  const header = screen.getByTestId('app-shell-header');
  const nav = screen.getByRole('navigation');

  expect(header).toHaveClass('flex-wrap');
  expect(header).toHaveClass('sm:flex-nowrap');
  expect(nav).toHaveClass('w-full');
  expect(nav).toHaveClass('overflow-x-auto');
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
