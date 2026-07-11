import React from 'react';
import { render, screen, within } from '@testing-library/react';

import HomePage from '@/app/page';

const { cookieThemeMock, isAdminMock, fetchPublicServiceModulesMock, fetchClientSessionMock, MODULES } = vi.hoisted(() => ({
  cookieThemeMock: vi.fn<() => string | undefined>(),
  isAdminMock: vi.fn<() => boolean>(),
  fetchPublicServiceModulesMock: vi.fn(),
  fetchClientSessionMock: vi.fn(),
  MODULES: [
    { id: 1, key: 'newsletter', title: 'Newsletter', href: '/newsletters', badge: 'Active', is_enabled: true, section: 'Newsletter', status: 'active', sort_order: 10, is_external: false, visibility: 'public' },
    { id: 2, key: 'civil-aircraft', title: 'Civil Aircraft Spec Catalog', description: 'Commercial aircraft specs & market competition analysis.', href: '/reports/civil-aircraft', badge: 'Active', is_enabled: true, section: 'Document', status: 'active', sort_order: 20, is_external: false, visibility: 'public' },
    { id: 3, key: 'document', title: 'Document', description: 'Browse HTML documents organized in folders.', href: '/documents', badge: 'Active', is_enabled: true, section: 'Document', status: 'active', sort_order: 30, is_external: false, visibility: 'public' },
    { id: 4, key: 'nsa', title: 'NSA', description: 'Access-controlled HTML documents.', href: '/nsa', badge: 'Active', is_enabled: true, section: 'Document', status: 'active', sort_order: 40, is_external: false, visibility: 'public', required_permission: 'collections.nsa.read', resource_type: 'collection', resource_id: 'nsa' },
    { id: 5, key: 'viewer', title: 'Viewer', description: '로컬 Markdown·HTML 파일을 열어 보고 편집 (서버 sanitize 미리보기).', href: '/viewer', badge: 'Active', is_enabled: true, section: 'Development', status: 'development', sort_order: 50, is_external: false, visibility: 'admin' },
    { id: 6, key: 'ai', title: 'AeroAI', description: '사내 폐쇄망 문서를 근거로 답하는 AI 어시스턴트.', href: '/ai', badge: 'Active', is_enabled: true, section: 'Development', status: 'development', sort_order: 60, is_external: false, visibility: 'admin' },
    { id: 7, key: 'open-notebook', title: 'Notebook', description: 'NotebookLM 대안 — 소스 정리·요약·벡터 검색 (별도 폐쇄망 앱).', href: '', badge: 'Active', is_enabled: true, section: 'Development', status: 'development', sort_order: 70, is_external: true, visibility: 'admin' },
    { id: 8, key: 'ladder', title: 'Ladder', description: 'Coffee-bet ladder game (사다리타기).', href: '/games/ladder', badge: 'Active', is_enabled: true, section: 'Development', status: 'development', sort_order: 80, is_external: false, visibility: 'admin' },
    { id: 9, key: 'announcement', title: 'Announcement', description: 'Company-wide announcements module.', href: '#', badge: 'Coming soon', is_enabled: false, section: 'Development', status: 'coming_soon', sort_order: 90, is_external: false, visibility: 'admin' },
    { id: 10, key: 'schedule', title: 'Schedule', description: 'Shared calendar & event tracking.', href: '#', badge: 'Coming soon', is_enabled: false, section: 'Development', status: 'coming_soon', sort_order: 100, is_external: false, visibility: 'admin' },
    { id: 11, key: 'office-tools', title: '오피스 도구', description: '보고서·차트·다이어그램을 한 곳에서 (샘플 예제 포함).', href: '/office-tools', badge: 'Active', is_enabled: true, section: 'Development', status: 'development', sort_order: 110, is_external: false, visibility: 'admin' },
    { id: 12, key: 'leantime', title: 'Leantime', description: '프로젝트 관리(외부 폐쇄망 앱). 운영자 설치 필요.', href: 'http://localhost:8081', badge: 'External', is_enabled: true, section: 'Development', status: 'development', sort_order: 140, is_external: true, visibility: 'admin' },
  ],
}));

vi.mock('next/headers', () => ({
  cookies: vi.fn(() => ({
    getAll: () => (cookieThemeMock() ? [{ name: 'aeroone_theme', value: cookieThemeMock() }] : []),
  })),
}));

vi.mock('@/lib/server-auth', () => ({
  resolveIsAdmin: () => Promise.resolve(isAdminMock()),
}));

vi.mock('@/lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api')>();
  return {
    ...actual,
    fetchPublicServiceModules: fetchPublicServiceModulesMock,
    fetchClientSession: fetchClientSessionMock,
  };
});

beforeEach(() => {
  cookieThemeMock.mockReturnValue(undefined);
  isAdminMock.mockReturnValue(false);
  // Simulate the backend /service-modules/public per-caller filtering: admins get all
  // modules; non-admins get only public, non-permission-gated modules.
  fetchPublicServiceModulesMock.mockImplementation(() =>
    Promise.resolve(isAdminMock() ? MODULES : MODULES.filter((m) => m.visibility === 'public' && !m.required_permission)),
  );
  fetchClientSessionMock.mockReturnValue(new Promise(() => {}));
});

afterEach(() => {
  vi.unstubAllEnvs();
  cookieThemeMock.mockReset();
  isAdminMock.mockReset();
  fetchPublicServiceModulesMock.mockReset();
  fetchClientSessionMock.mockReset();
});

test('removes the home hero copy while keeping the Newsletter link and theme selector', async () => {
  render(await HomePage({ searchParams: Promise.resolve({}) }));

  expect(screen.queryByText('AeroOne Internal Platform')).not.toBeInTheDocument();
  expect(screen.queryByText('사내 문서형 서비스 시작점')).not.toBeInTheDocument();

  const newsletterLink = within(screen.getByRole('main')).getByRole('link', { name: /Newsletter/i });

  expect(newsletterLink).toHaveAttribute('href', '/newsletters');
  expect(newsletterLink).toHaveTextContent('Active');
  expect(within(newsletterLink).queryByTestId('service-card-description')).not.toBeInTheDocument();
  expect(screen.getByTestId('newsletter-theme-selector')).toBeInTheDocument();
});

test('non-admin dashboard hides required-permission NSA plus development and coming-soon cards', async () => {
  isAdminMock.mockReturnValue(false);
  render(await HomePage({ searchParams: Promise.resolve({}) }));

  const main = screen.getByRole('main');
  expect(within(main).getByRole('link', { name: /Newsletter/i })).toBeInTheDocument();
  expect(within(main).queryByRole('link', { name: /NSA/i })).not.toBeInTheDocument();

  // Development and coming-soon are operator-only surfaces.
  expect(screen.queryByRole('heading', { name: 'Development' })).not.toBeInTheDocument();
  expect(screen.queryByRole('link', { name: /Viewer/i })).not.toBeInTheDocument();
  expect(screen.queryByRole('link', { name: /AeroAI/i })).not.toBeInTheDocument();
  expect(screen.queryByRole('heading', { name: 'Announcement' })).not.toBeInTheDocument();
  expect(screen.getByText('3 active · 0 coming soon')).toBeInTheDocument();
});

test('non-admin fallback dashboard drops required-permission NSA cards', async () => {
  fetchPublicServiceModulesMock.mockRejectedValue(new Error('DB unavailable'));
  isAdminMock.mockReturnValue(false);

  render(await HomePage({ searchParams: Promise.resolve({}) }));

  const main = screen.getByRole('main');
  expect(within(main).getByRole('link', { name: /Newsletter/i })).toBeInTheDocument();
  expect(within(main).queryByRole('link', { name: /NSA/i })).not.toBeInTheDocument();
  expect(screen.getByText(/대시보드 모듈 DB 를 읽지 못해 내장 fallback 목록을 표시합니다/)).toBeInTheDocument();
  expect(screen.getByText('3 active · 0 coming soon')).toBeInTheDocument();
});
test('degraded fallback keeps login visible, Admin hidden, and the main nav to 3 items', async () => {
  fetchPublicServiceModulesMock.mockRejectedValue(new Error('DB unavailable'));
  isAdminMock.mockReturnValue(false);

  render(await HomePage({ searchParams: Promise.resolve({}) }));

  const nav = screen.getByRole('navigation', { name: '주요 메뉴' });
  const navLinks = within(nav).getAllByRole('link');

  expect(navLinks).toHaveLength(3);
  expect(within(nav).getByRole('link', { name: 'Dashboard' })).toBeInTheDocument();
  expect(within(nav).getByRole('link', { name: 'Newsletter' })).toBeInTheDocument();
  expect(within(nav).getByRole('link', { name: 'Document' })).toBeInTheDocument();
  expect(screen.getByRole('link', { name: '로그인' })).toHaveAttribute('href', '/login');
  expect(screen.queryByRole('link', { name: 'Admin' })).not.toBeInTheDocument();
});

test('adds an active Civil Aircraft Spec Catalog card linking to the report page', async () => {
  render(await HomePage({ searchParams: Promise.resolve({}) }));

  const main = screen.getByRole('main');
  const reportLink = within(main).getByRole('link', { name: /Civil Aircraft Spec Catalog/i });

  expect(reportLink).toHaveAttribute('href', '/reports/civil-aircraft');
  expect(reportLink).toHaveTextContent('Active');
  expect(within(reportLink).getByTestId('service-card-description')).toHaveTextContent(/Commercial aircraft specs/i);
});

test('operator dashboard groups cards into ordered sections and keeps coming-soon in Development', async () => {
  isAdminMock.mockReturnValue(true);
  render(await HomePage({ searchParams: Promise.resolve({}) }));

  const newsletterSection = screen.getAllByRole('heading', { name: 'Newsletter' })[0];
  const documentSection = screen.getAllByRole('heading', { name: 'Document' })[0];
  const developmentSection = screen.getByRole('heading', { name: 'Development' });
  const nsaLink = screen.getByRole('link', { name: /NSA/i });
  const aiLink = screen.getByRole('link', { name: /AeroAI/i });
  const viewerLink = screen.getByRole('link', { name: /Viewer/i });
  const ladderLink = screen.getByRole('link', { name: /Ladder/i });
  const notebookLink = screen.getByRole('link', { name: /Notebook/i });
  const announcement = screen.getByRole('heading', { name: 'Announcement' });
  const schedule = screen.getByRole('heading', { name: 'Schedule' });

  expect(newsletterSection.compareDocumentPosition(documentSection) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(documentSection.compareDocumentPosition(developmentSection) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(nsaLink.compareDocumentPosition(developmentSection) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(developmentSection.compareDocumentPosition(viewerLink) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(developmentSection.compareDocumentPosition(aiLink) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(developmentSection.compareDocumentPosition(notebookLink) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(developmentSection.compareDocumentPosition(ladderLink) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();

  expect(screen.queryByRole('heading', { name: 'Coming soon' })).not.toBeInTheDocument();
  expect(screen.queryByRole('link', { name: /Announcement/i })).not.toBeInTheDocument();
  expect(announcement.closest('[aria-disabled="true"]')).not.toBeNull();
  expect(schedule.closest('[aria-disabled="true"]')).toHaveTextContent('Coming soon');
  expect(screen.getByText('10 active · 2 coming soon')).toBeInTheDocument();
});

test('operator dashboard shows the unified office-tools hub card in Development', async () => {
  isAdminMock.mockReturnValue(true);
  render(await HomePage({ searchParams: Promise.resolve({}) }));

  const main = screen.getByRole('main');
  const hubLink = within(main).getByRole('link', { name: /오피스 도구/ });

  expect(hubLink).toHaveAttribute('href', '/office-tools');
});

test('non-admin dashboard hides the admin-only office-tools hub card', async () => {
  isAdminMock.mockReturnValue(false);
  render(await HomePage({ searchParams: Promise.resolve({}) }));

  expect(screen.queryByRole('link', { name: /오피스 도구/ })).not.toBeInTheDocument();
});

test('operator dashboard shows an external Leantime card opening the co-deploy app on port 8081', async () => {
  isAdminMock.mockReturnValue(true);
  render(await HomePage({ searchParams: Promise.resolve({}) }));

  const main = screen.getByRole('main');
  const leantimeLink = within(main).getByRole('link', { name: /Leantime/i });

  expect(leantimeLink).toHaveAttribute('target', '_blank');
  expect(leantimeLink).toHaveAttribute('rel', expect.stringContaining('noopener'));
  expect(leantimeLink.getAttribute('href')).toMatch(/:8081$/);
  expect(within(leantimeLink).getByTestId('service-card-description')).toHaveTextContent(/프로젝트 관리/);
});

test('non-admin dashboard hides the admin-only Leantime card', async () => {
  isAdminMock.mockReturnValue(false);
  render(await HomePage({ searchParams: Promise.resolve({}) }));

  expect(screen.queryByRole('link', { name: /Leantime/i })).not.toBeInTheDocument();
});

test('adds an active NSA card linking to /nsa', async () => {
  isAdminMock.mockReturnValue(true);
  render(await HomePage({ searchParams: Promise.resolve({}) }));

  const main = screen.getByRole('main');
  const nsaLink = within(main).getByRole('link', { name: /NSA/i });

  expect(nsaLink).toHaveAttribute('href', '/nsa');
  expect(nsaLink).toHaveTextContent('Active');
  expect(within(nsaLink).getByTestId('service-card-description')).toHaveTextContent(/Access-controlled HTML documents/i);
});

test('operator dashboard shows an active Ladder card linking to /games/ladder', async () => {
  isAdminMock.mockReturnValue(true);
  render(await HomePage({ searchParams: Promise.resolve({}) }));

  const main = screen.getByRole('main');
  const ladderLink = within(main).getByRole('link', { name: /Ladder/i });

  expect(ladderLink).toHaveAttribute('href', '/games/ladder');
  expect(ladderLink).toHaveTextContent('Active');
  expect(within(ladderLink).getByTestId('service-card-description')).toHaveTextContent(/Coffee-bet ladder game/i);
});

test('adds an active Document card linking to the documents page', async () => {
  render(await HomePage({ searchParams: Promise.resolve({}) }));

  const main = screen.getByRole('main');
  const documentLink = within(main).getByRole('link', { name: /Browse HTML documents organized in folders/i });

  expect(documentLink).toHaveAttribute('href', '/documents');
  expect(documentLink).toHaveTextContent('Active');
  expect(within(documentLink).getByTestId('service-card-description')).toHaveTextContent(/HTML documents organized in folders/i);
});

test('operator dashboard shows an active Viewer card linking to /viewer', async () => {
  isAdminMock.mockReturnValue(true);
  render(await HomePage({ searchParams: Promise.resolve({}) }));

  const main = screen.getByRole('main');
  const viewerLink = within(main).getByRole('link', { name: /Viewer/i });

  expect(viewerLink).toHaveAttribute('href', '/viewer');
  expect(viewerLink).toHaveTextContent('Active');
  expect(within(viewerLink).getByTestId('service-card-description')).toHaveTextContent(/로컬 Markdown·HTML 파일을 열어/);
});

test('operator dashboard shows an active AeroAI card linking to /ai', async () => {
  isAdminMock.mockReturnValue(true);
  render(await HomePage({ searchParams: Promise.resolve({}) }));

  const main = screen.getByRole('main');
  const aiLink = within(main).getByRole('link', { name: /AeroAI/i });

  expect(aiLink).toHaveAttribute('href', '/ai');
  expect(aiLink).toHaveTextContent('Active');
  expect(within(aiLink).getByTestId('service-card-description')).toHaveTextContent(/문서를 근거로 답하는 AI 어시스턴트/);
});

test('operator dashboard shows an external Notebook card opening the co-deploy app on port 8502', async () => {
  isAdminMock.mockReturnValue(true);
  render(await HomePage({ searchParams: Promise.resolve({}) }));

  const main = screen.getByRole('main');
  const notebookLink = within(main).getByRole('link', { name: /Notebook/i });

  expect(notebookLink).toHaveAttribute('target', '_blank');
  expect(notebookLink).toHaveAttribute('rel', expect.stringContaining('noopener'));
  expect(notebookLink.getAttribute('href')).toMatch(/^http:\/\/[^/]+:8502$/);
  expect(notebookLink).toHaveTextContent('Active');
  expect(within(notebookLink).getByTestId('service-card-description')).toHaveTextContent(/NotebookLM 대안/);
});

test('home page uses dark theme from cookie', async () => {
  cookieThemeMock.mockReturnValue('dark');

  render(await HomePage({ searchParams: Promise.resolve({}) }));

  expect(screen.getByRole('link', { name: '라이트 테마로 전환' })).toBeInTheDocument();
});
