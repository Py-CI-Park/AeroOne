import React from 'react';
import { act, render, screen, within } from '@testing-library/react';

import HomePage from '@/app/page';

const { cookieThemeMock, isAdminMock, authenticatedMock, usernameMock, fetchPublicServiceModulesMock, fetchClientSessionMock, fetchMyRecentReadsMock, fetchLauncherHealthMock, MODULES } = vi.hoisted(() => ({
  cookieThemeMock: vi.fn<() => string | undefined>(),
  isAdminMock: vi.fn<() => boolean>(),
  authenticatedMock: vi.fn<() => boolean>(),
  usernameMock: vi.fn<() => string | undefined>(),
  fetchPublicServiceModulesMock: vi.fn(),
  fetchClientSessionMock: vi.fn(),
  fetchMyRecentReadsMock: vi.fn(),
  fetchLauncherHealthMock: vi.fn(),
  MODULES: [
    { id: 1, key: 'newsletter', title: 'Newsletter', href: '/newsletters', badge: 'Active', is_enabled: true, section: 'Newsletter', status: 'active', sort_order: 10, is_external: false, launcher_kind: 'none', visibility: 'public' },
    { id: 2, key: 'civil-aircraft', title: 'Civil Aircraft Spec Catalog', description: 'Commercial aircraft specs & market competition analysis.', href: '/reports/civil-aircraft', badge: 'Active', is_enabled: true, section: 'Document', status: 'active', sort_order: 20, is_external: false, launcher_kind: 'none', visibility: 'public' },
    { id: 3, key: 'document', title: 'Document', description: 'Browse HTML documents organized in folders.', href: '/documents', badge: 'Active', is_enabled: true, section: 'Document', status: 'active', sort_order: 30, is_external: false, launcher_kind: 'none', visibility: 'public' },
    { id: 4, key: 'nsa', title: 'NSA', description: 'Access-controlled HTML documents.', href: '/nsa', badge: 'Active', is_enabled: true, section: 'Document', status: 'active', sort_order: 40, is_external: false, launcher_kind: 'none', visibility: 'public', required_permission: 'collections.nsa.read', resource_type: 'collection', resource_id: 'nsa' },
    { id: 5, key: 'viewer', title: 'Viewer', description: '로컬 Markdown·HTML 파일을 열어 보고 편집 (서버 sanitize 미리보기).', href: '/viewer', badge: 'Active', is_enabled: true, section: 'Development', status: 'development', sort_order: 50, is_external: false, launcher_kind: 'none', visibility: 'admin' },
    { id: 6, key: 'ai', title: 'AeroAI', description: '사내 폐쇄망 문서를 근거로 답하는 AI 어시스턴트.', href: '/ai', badge: 'Active', is_enabled: true, section: 'Development', status: 'development', sort_order: 60, is_external: false, launcher_kind: 'none', visibility: 'admin' },
    { id: 14, key: 'aero-work', title: 'Aero Work', description: '대화 한 줄로 일정·문서(HWPX)·지식 검색을 잇는 업무 워크스페이스.', href: '/aero-work', badge: 'Active', is_enabled: true, section: 'Development', status: 'development', sort_order: 42, is_external: false, launcher_kind: 'none', visibility: 'admin' },
    { id: 7, key: 'open-notebook', title: 'Notebook', description: 'NotebookLM 대안 — 소스 정리·요약·벡터 검색 (별도 폐쇄망 앱).', href: '', badge: 'Active', is_enabled: true, section: 'Development', status: 'development', sort_order: 70, is_external: true, launcher_kind: 'open_notebook', visibility: 'admin' },
    { id: 11, key: 'openwebui', title: 'AI', description: '', href: '', badge: 'Active', is_enabled: true, section: 'AI', status: 'development', sort_order: 75, is_external: true, launcher_kind: 'open_webui', visibility: 'public', required_permission: 'dashboard.openwebui.launch' },
    { id: 8, key: 'ladder', title: 'Ladder', description: 'Coffee-bet ladder game (사다리타기).', href: '/games/ladder', badge: 'Active', is_enabled: true, section: 'ETC', status: 'development', sort_order: 80, is_external: false, launcher_kind: 'none', visibility: 'admin' },
    { id: 9, key: 'announcement', title: 'Announcement', description: 'Company-wide announcements module.', href: '#', badge: 'Coming soon', is_enabled: false, section: 'ETC', status: 'coming_soon', sort_order: 90, is_external: false, launcher_kind: 'none', visibility: 'admin' },
    { id: 10, key: 'schedule', title: 'Schedule', description: 'Shared calendar & event tracking.', href: '#', badge: 'Coming soon', is_enabled: false, section: 'ETC', status: 'coming_soon', sort_order: 100, is_external: false, launcher_kind: 'none', visibility: 'admin' },
    { id: 13, key: 'office-tools', title: 'Office Studio', description: '보고서·차트·다이어그램을 한 곳에서 (샘플 예제 포함).', href: '/office-tools', badge: 'Active', is_enabled: true, section: 'Development', status: 'development', sort_order: 45, is_external: false, launcher_kind: 'none', visibility: 'admin' },
    // Leantime 카드는 폐쇄망 릴리스에서 제외됨(service_modules 삭제) — 픽스처에서도 제거해 대시보드가 노출하지 않음을 반영.
  ],
}));

vi.mock('next/headers', () => ({
  cookies: vi.fn(() => ({
    getAll: () => (cookieThemeMock() ? [{ name: 'aeroone_theme', value: cookieThemeMock() }] : []),
  })),
}));

vi.mock('@/lib/server-auth', () => ({
  resolveDashboardAuth: () => Promise.resolve({
    authenticated: authenticatedMock() || isAdminMock(),
    isAdmin: isAdminMock(),
    username: usernameMock(),
  }),
}));

vi.mock('@/lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api')>();
  return {
    ...actual,
    fetchPublicServiceModules: fetchPublicServiceModulesMock,
    fetchClientSession: fetchClientSessionMock,
    fetchMyRecentReads: fetchMyRecentReadsMock,
    fetchLauncherHealth: fetchLauncherHealthMock,
  };
});

beforeEach(() => {
  cookieThemeMock.mockReturnValue(undefined);
  isAdminMock.mockReturnValue(false);
  authenticatedMock.mockReturnValue(false);
  usernameMock.mockReturnValue(undefined);
  // Simulate the backend /service-modules/public per-caller filtering: admins get all
  // modules; non-admins get only public, non-permission-gated modules.
  fetchPublicServiceModulesMock.mockImplementation(() =>
    Promise.resolve(isAdminMock() ? MODULES : MODULES.filter((m) => m.visibility === 'public' && !m.required_permission)),
  );
  fetchClientSessionMock.mockReturnValue(new Promise(() => {}));
  // 홈 대시보드 테스트는 최근 본 뉴스레터 스트립 자체를 검증하지 않는다 — 영영 미해결
  // Promise 로 고정해 스트립이 조용히 렌더 생략 상태(null)로 머물게 하고, act() 경고 없이
  // 기존 섹션/카드 단언에 영향이 없게 한다.
  fetchMyRecentReadsMock.mockReturnValue(new Promise(() => {}));
  // 런처 헬스는 ready 로 목킹 — 외부 앱 카드 링크 단언(8502/8080)이 기존 의미를 유지한다.
  fetchLauncherHealthMock.mockImplementation((kind: string) => Promise.resolve({
    status: 'ready',
    port: kind === 'open_notebook' ? 8502 : 8080,
    probe_target: '',
    checked_at: '',
    latency_ms: 1,
    detail: null,
  }));
});

afterEach(() => {
  vi.unstubAllEnvs();
  cookieThemeMock.mockReset();
  isAdminMock.mockReset();
  authenticatedMock.mockReset();
  usernameMock.mockReset();
  fetchPublicServiceModulesMock.mockReset();
  fetchClientSessionMock.mockReset();
  fetchMyRecentReadsMock.mockReset();
  fetchLauncherHealthMock.mockReset();
});

// 대시보드 렌더 헬퍼 — ExternalLauncherCard 의 헬스 fetch 가 렌더 직후 상태를 갱신하므로
// act 로 마이크로태스크를 플러시해 "not wrapped in act" 경고 없이 안정 상태에서 단언한다.
async function renderHome(searchParams: Record<string, string> = {}) {
  const ui = await HomePage({ searchParams: Promise.resolve(searchParams) });
  render(ui);
  await act(async () => {});
}

test('adds the anonymous cinematic flight deck while keeping the full Newsletter card and theme selector', async () => {
  await renderHome();

  expect(screen.getByRole('heading', { name: 'AeroOne 대시보드' })).toHaveClass('sr-only');
  expect(screen.queryByText('AeroOne의 문서와 업무 서비스를 한곳에서 확인하세요.')).not.toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'AeroOne 로그인' })).toHaveAttribute('href', '/login');
  expect(screen.getByRole('link', { name: '민수기체 빠른 실행' })).toHaveAttribute('href', '/reports/civil-aircraft');
  expect(screen.getByRole('link', { name: '뉴스레터 빠른 실행' })).toHaveAttribute('href', '/newsletters');

  const newsletterLink = within(screen.getByRole('region', { name: '전체 서비스' }))
    .getByRole('link', { name: /Newsletter/i });
  expect(newsletterLink).toHaveAttribute('href', '/newsletters');
  expect(newsletterLink).toHaveTextContent('Active');
  expect(within(newsletterLink).queryByTestId('service-card-description')).not.toBeInTheDocument();
  expect(screen.getByTestId('newsletter-theme-selector')).toBeInTheDocument();
});

test('personalizes the flight deck for signed-in users without exposing the login CTA', async () => {
  authenticatedMock.mockReturnValue(true);
  usernameMock.mockReturnValue('민지');

  await renderHome();

  expect(screen.getByRole('heading', { name: '민지님, 업무를 이어가세요.' })).toBeInTheDocument();
  expect(screen.queryByRole('link', { name: 'AeroOne 로그인' })).not.toBeInTheDocument();
});

test('shows admin context and only filtered modules in Featured priority order', async () => {
  isAdminMock.mockReturnValue(true);
  usernameMock.mockReturnValue('운영팀');

  await renderHome();

  expect(screen.getByRole('heading', { name: '운영팀님, 서비스 운영 현황을 확인하세요.' })).toBeInTheDocument();
  const featured = screen.getByRole('region', { name: 'Featured' });
  expect(within(featured).getAllByRole('link').map((link) => link.getAttribute('href'))).toEqual([
    '/reports/civil-aircraft',
    '/ai',
    '/aero-work',
    '/newsletters',
  ]);
});

test('non-admin dashboard hides required-permission NSA plus development and coming-soon cards', async () => {
  isAdminMock.mockReturnValue(false);
  await renderHome();

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

  await renderHome();

  const main = screen.getByRole('main');
  expect(within(main).getByRole('link', { name: /Newsletter/i })).toBeInTheDocument();
  expect(within(main).queryByRole('link', { name: /NSA/i })).not.toBeInTheDocument();
  expect(screen.getByText(/대시보드 모듈 DB 를 읽지 못해 내장 fallback 목록을 표시합니다/)).toBeInTheDocument();
  expect(screen.getByText('3 active · 0 coming soon')).toBeInTheDocument();
});
test('degraded fallback keeps login visible, Admin hidden, and the main nav to 3 items', async () => {
  fetchPublicServiceModulesMock.mockRejectedValue(new Error('DB unavailable'));
  isAdminMock.mockReturnValue(false);

  await renderHome();

  const nav = screen.getByRole('navigation', { name: '주요 메뉴' });
  const navLinks = within(nav).getAllByRole('link');

  expect(navLinks).toHaveLength(3);
  expect(within(nav).getByRole('link', { name: 'Dashboard' })).toBeInTheDocument();
  expect(within(nav).getByRole('link', { name: 'Newsletter' })).toBeInTheDocument();
  expect(within(nav).getByRole('link', { name: 'Document' })).toBeInTheDocument();
  expect(screen.getByRole('link', { name: '로그인' })).toHaveAttribute('href', '/login');
  expect(screen.queryByRole('link', { name: 'Admin' })).not.toBeInTheDocument();
});

test('degraded fallback (admin, API rejected) also omits the excluded Leantime card', async () => {
  // 성공 API fixture 뿐 아니라 실제 page.tsx FALLBACK_MODULES 경로에서도 Leantime 이
  // 재등장하지 않음을 잠근다 — FALLBACK 에 항목이 되살아나면 이 단언이 잡는다.
  fetchPublicServiceModulesMock.mockRejectedValue(new Error('DB unavailable'));
  isAdminMock.mockReturnValue(true);

  await renderHome();

  expect(screen.queryByRole('link', { name: /Leantime/i })).not.toBeInTheDocument();
  // 대조: 유지되는 Aero Work 카드는 degraded fallback 에서도 보인다.
  expect(screen.getByRole('link', { name: /Aero Work/i })).toBeInTheDocument();
});

test('adds an active Civil Aircraft Spec Catalog card linking to the report page', async () => {
  await renderHome();

  const main = screen.getByRole('main');
  const reportLink = within(main).getByRole('link', { name: /Civil Aircraft Spec Catalog/i });

  expect(reportLink).toHaveAttribute('href', '/reports/civil-aircraft');
  expect(reportLink).toHaveTextContent('Active');
  expect(within(reportLink).getByTestId('service-card-description')).toHaveTextContent(/Commercial aircraft specs/i);
});

test('operator dashboard groups cards into ordered Newsletter/Document/AI/Development/ETC sections', async () => {
  isAdminMock.mockReturnValue(true);
  await renderHome();

  const newsletterSection = screen.getAllByRole('heading', { name: 'Newsletter' })[0];
  const documentSection = screen.getAllByRole('heading', { name: 'Document' })[0];
  const developmentSection = screen.getByRole('heading', { name: 'Development' });
  const aiSection = screen.getAllByRole('heading', { name: 'AI' })[0];
  const etcSection = screen.getByRole('heading', { name: 'ETC' });
  const nsaLink = screen.getByRole('link', { name: /NSA/i });
  const aiLink = screen.getByRole('link', { name: /AeroAI/i });
  const viewerLink = screen.getByRole('link', { name: /Viewer/i });
  const ladderLink = screen.getByRole('link', { name: /Ladder/i });
  const notebookLink = await screen.findByRole('link', { name: /Notebook/i });
  const openwebuiLink = document.querySelector('main a[href*=":8080"]') as HTMLElement;
  const announcement = screen.getByRole('heading', { name: 'Announcement' });
  const schedule = screen.getByRole('heading', { name: 'Schedule' });

  expect(newsletterSection.compareDocumentPosition(documentSection) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(documentSection.compareDocumentPosition(aiSection) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(aiSection.compareDocumentPosition(developmentSection) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(developmentSection.compareDocumentPosition(etcSection) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(nsaLink.compareDocumentPosition(aiSection) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(developmentSection.compareDocumentPosition(aiLink) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(developmentSection.compareDocumentPosition(notebookLink) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(aiSection.compareDocumentPosition(openwebuiLink) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(developmentSection.compareDocumentPosition(viewerLink) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(etcSection.compareDocumentPosition(ladderLink) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();

  expect(screen.queryByRole('heading', { name: 'Coming soon' })).not.toBeInTheDocument();
  expect(screen.queryByRole('link', { name: /Announcement/i })).not.toBeInTheDocument();
  expect(announcement.closest('[aria-disabled="true"]')).not.toBeNull();
  expect(schedule.closest('[aria-disabled="true"]')).toHaveTextContent('Coming soon');
  // Leantime 카드 제외를 유지하면서 실제 Aero Work 카드를 포함해 활성 카드가 11개다.
  expect(screen.getByText('11 active · 2 coming soon')).toBeInTheDocument();
});

test('operator dashboard shows the unified office-tools hub card in Development', async () => {
  isAdminMock.mockReturnValue(true);
  await renderHome();

  const main = screen.getByRole('main');
  const hubLink = within(main).getByRole('link', { name: /Office Studio/ });

  expect(hubLink).toHaveAttribute('href', '/office-tools');
});

test('non-admin dashboard hides the admin-only office-tools hub card', async () => {
  isAdminMock.mockReturnValue(false);
  await renderHome();

  expect(screen.queryByRole('link', { name: /Office Studio/ })).not.toBeInTheDocument();
});

test('operator dashboard no longer shows the excluded Leantime card', async () => {
  isAdminMock.mockReturnValue(true);
  await renderHome();

  // Leantime 동거 카드는 폐쇄망 릴리스에서 제외되어 관리자에게도 노출되지 않는다.
  expect(screen.queryByRole('link', { name: /Leantime/i })).not.toBeInTheDocument();
});

test('non-admin dashboard hides the admin-only Leantime card', async () => {
  isAdminMock.mockReturnValue(false);
  await renderHome();

  expect(screen.queryByRole('link', { name: /Leantime/i })).not.toBeInTheDocument();
});

test('adds an active NSA card linking to /nsa', async () => {
  isAdminMock.mockReturnValue(true);
  await renderHome();

  const main = screen.getByRole('main');
  const nsaLink = within(main).getByRole('link', { name: /NSA/i });

  expect(nsaLink).toHaveAttribute('href', '/nsa');
  expect(nsaLink).toHaveTextContent('Active');
  expect(within(nsaLink).getByTestId('service-card-description')).toHaveTextContent(/Access-controlled HTML documents/i);
});

test('operator dashboard shows an active Ladder card linking to /games/ladder', async () => {
  isAdminMock.mockReturnValue(true);
  await renderHome();

  const main = screen.getByRole('main');
  const ladderLink = within(main).getByRole('link', { name: /Ladder/i });

  expect(ladderLink).toHaveAttribute('href', '/games/ladder');
  expect(ladderLink).toHaveTextContent('Active');
  expect(within(ladderLink).getByTestId('service-card-description')).toHaveTextContent(/Coffee-bet ladder game/i);
});

test('adds an active Document card linking to the documents page', async () => {
  await renderHome();

  const main = screen.getByRole('main');
  const documentLink = within(main).getByRole('link', { name: /Browse HTML documents organized in folders/i });

  expect(documentLink).toHaveAttribute('href', '/documents');
  expect(documentLink).toHaveTextContent('Active');
  expect(within(documentLink).getByTestId('service-card-description')).toHaveTextContent(/HTML documents organized in folders/i);
});

test('operator dashboard shows an active Viewer card linking to /viewer', async () => {
  isAdminMock.mockReturnValue(true);
  await renderHome();

  const main = screen.getByRole('main');
  const viewerLink = within(main).getByRole('link', { name: /Viewer/i });

  expect(viewerLink).toHaveAttribute('href', '/viewer');
  expect(viewerLink).toHaveTextContent('Active');
  expect(within(viewerLink).getByTestId('service-card-description')).toHaveTextContent(/로컬 Markdown·HTML 파일을 열어/);
});

test('operator dashboard shows an active AeroAI card linking to /ai', async () => {
  isAdminMock.mockReturnValue(true);
  await renderHome();

  const main = screen.getByRole('main');
  const aiLink = within(main).getByRole('link', { name: /AeroAI/i });

  expect(aiLink).toHaveAttribute('href', '/ai');
  expect(aiLink).toHaveTextContent('Active');
  expect(within(aiLink).getByTestId('service-card-description')).toHaveTextContent(/문서를 근거로 답하는 AI 어시스턴트/);
});

test('operator dashboard shows an external Notebook card opening the co-deploy app on port 8502', async () => {
  isAdminMock.mockReturnValue(true);
  await renderHome();

  const main = screen.getByRole('main');
  const notebookLink = await within(main).findByRole('link', { name: /Notebook/i });

  expect(notebookLink).toHaveAttribute('target', '_blank');
  expect(notebookLink).toHaveAttribute('rel', expect.stringContaining('noopener'));
  expect(notebookLink.getAttribute('href')).toMatch(/^http:\/\/[^/]+:8502$/);
  expect(notebookLink).toHaveTextContent('Active');
  expect(within(notebookLink).getByTestId('service-card-description')).toHaveTextContent(/NotebookLM 대안/);
});

test('operator dashboard shows an external OpenWebUI card opening the co-deploy app on port 8080, coexisting with Notebook', async () => {
  isAdminMock.mockReturnValue(true);
  await renderHome();

  const main = screen.getByRole('main');
  const notebookLink = await within(main).findByRole('link', { name: /Notebook/i });
  const openwebuiLink = document.querySelector('main a[href*=":8080"]') as HTMLElement;

  expect(openwebuiLink).toHaveAttribute('target', '_blank');
  expect(openwebuiLink).toHaveAttribute('rel', expect.stringContaining('noopener'));
  expect(openwebuiLink.getAttribute('href')).toMatch(/^http:\/\/[^/]+:8080$/);
  expect(openwebuiLink).toHaveTextContent('Active');
  expect(openwebuiLink).toHaveTextContent('AI');
  // Notebook (8502) and OpenWebUI (8080) are independent reserved launchers that coexist.
  expect(notebookLink.getAttribute('href')).not.toBe(openwebuiLink.getAttribute('href'));
});

test('non-admin dashboard (active session, no dashboard.openwebui.launch grant) hides the OpenWebUI card', async () => {
  isAdminMock.mockReturnValue(false);
  await renderHome();

  expect(document.querySelector('a[href*=":8080"]')).toBeNull();
});

test('degraded fallback hides the OpenWebUI card for non-admins even though it is visibility: public', async () => {
  fetchPublicServiceModulesMock.mockRejectedValue(new Error('DB unavailable'));
  isAdminMock.mockReturnValue(false);

  await renderHome();

  // required_permission is unverifiable in degraded mode, so the conservative fallback filter
  // must drop it for non-admins even though visibility is 'public'.
  expect(document.querySelector('a[href*=":8080"]')).toBeNull();
});

test('home page uses dark theme from cookie', async () => {
  cookieThemeMock.mockReturnValue('dark');

  await renderHome();

  expect(screen.getByRole('link', { name: '라이트 테마로 전환' })).toBeInTheDocument();
});
