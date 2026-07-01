import React from 'react';
import { render, screen, within } from '@testing-library/react';

import HomePage from '@/app/page';

const { cookieThemeMock } = vi.hoisted(() => ({
  cookieThemeMock: vi.fn<() => string | undefined>(),
}));

vi.mock('next/headers', () => ({
  cookies: vi.fn(() => ({
    getAll: () => (cookieThemeMock() ? [{ name: 'aeroone_theme', value: cookieThemeMock() }] : []),
  })),
}));

beforeEach(() => {
  cookieThemeMock.mockReturnValue(undefined);
});

afterEach(() => {
  vi.unstubAllEnvs();
  cookieThemeMock.mockReset();
});

test('removes the home hero copy while keeping the Newsletter link and theme selector', async () => {
  render(await HomePage({ searchParams: Promise.resolve({}) }));

  expect(screen.queryByText('AeroOne Internal Platform')).not.toBeInTheDocument();
  expect(screen.queryByText('사내 문서형 서비스 시작점')).not.toBeInTheDocument();
  expect(
    screen.queryByText(/현재는 뉴스레터 서비스부터 시작합니다/),
  ).not.toBeInTheDocument();

  const newsletterLink = within(screen.getByRole('main')).getByRole('link', { name: /Newsletter/i });

  expect(newsletterLink).toHaveAttribute('href', '/newsletters');
  expect(newsletterLink).not.toHaveTextContent('Open the latest issue and browse previous issues by date.');
  expect(newsletterLink).toHaveTextContent('Active');
  expect(newsletterLink).not.toHaveTextContent('뉴스레터 서비스');
  expect(newsletterLink).not.toHaveTextContent('뉴스레터');
  expect(within(newsletterLink).queryByTestId('service-card-description')).not.toBeInTheDocument();
  expect(screen.queryByTestId('service-card-icon')).not.toBeInTheDocument();
  expect(screen.getByTestId('newsletter-theme-selector')).toBeInTheDocument();
});

test('adds an active Civil Aircraft Spec Catalog card linking to the report page', async () => {
  render(await HomePage({ searchParams: Promise.resolve({}) }));

  const main = screen.getByRole('main');
  const reportLink = within(main).getByRole('link', { name: /Civil Aircraft Spec Catalog/i });

  expect(reportLink).toHaveAttribute('href', '/reports/civil-aircraft');
  expect(reportLink).toHaveTextContent('Active');
  expect(within(reportLink).getByTestId('service-card-description')).toHaveTextContent(/Commercial aircraft specs/i);

  // 상단 요약 카운트는 MODULES 에서 파생 — 개발중 섹션 재분류 후에도 활성 8개 / coming 2개.
  expect(screen.getByText('8 active · 2 coming soon')).toBeInTheDocument();
});

test('groups dashboard cards into ordered sections and keeps coming-soon cards in development', async () => {
  render(await HomePage({ searchParams: Promise.resolve({}) }));

  // 섹션 제목과 카드 제목이 같은 이름(heading)이라 첫 번째(섹션 헤더)를 집는다.
  const newsletterSection = screen.getAllByRole('heading', { name: 'Newsletter' })[0];
  const documentSection = screen.getAllByRole('heading', { name: 'Document' })[0];
  const developmentSection = screen.getByRole('heading', { name: '개발중' });
  const nsaLink = screen.getByRole('link', { name: /NSA/i });
  const aiLink = screen.getByRole('link', { name: /AeroAI/i });
  const viewerLink = screen.getByRole('link', { name: /Viewer/i });
  const ladderLink = screen.getByRole('link', { name: /Ladder/i });
  const notebookLink = screen.getByRole('link', { name: /Notebook/i });
  const announcement = screen.getByRole('heading', { name: 'Announcement' });
  const schedule = screen.getByRole('heading', { name: 'Schedule' });

  // 섹션 순서: Newsletter → Document → 개발중. 개발중 안의 기존 기능 버튼은 active 링크로 유지된다.
  expect(newsletterSection.compareDocumentPosition(documentSection) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(documentSection.compareDocumentPosition(developmentSection) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(nsaLink.compareDocumentPosition(developmentSection) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(developmentSection.compareDocumentPosition(viewerLink) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(developmentSection.compareDocumentPosition(aiLink) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(developmentSection.compareDocumentPosition(notebookLink) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(developmentSection.compareDocumentPosition(ladderLink) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();

  // Coming soon 섹션은 별도로 만들지 않고, 개발중 섹션 안에서 비활성 카드로 남긴다.
  expect(screen.queryByRole('heading', { name: 'Coming soon' })).not.toBeInTheDocument();
  expect(screen.queryByRole('link', { name: /Announcement/i })).not.toBeInTheDocument();
  expect(screen.queryByRole('link', { name: /Schedule/i })).not.toBeInTheDocument();
  expect(announcement.closest('[aria-disabled="true"]')).not.toBeNull();
  expect(schedule.closest('[aria-disabled="true"]')).not.toBeNull();
  expect(announcement.closest('[aria-disabled="true"]')).toHaveTextContent('Coming soon');
  expect(schedule.closest('[aria-disabled="true"]')).toHaveTextContent('Coming soon');
});

test('adds an active NSA card linking to /nsa', async () => {
  render(await HomePage({ searchParams: Promise.resolve({}) }));

  const main = screen.getByRole('main');
  const nsaLink = within(main).getByRole('link', { name: /NSA/i });

  expect(nsaLink).toHaveAttribute('href', '/nsa');
  expect(nsaLink).toHaveTextContent('Active');
  expect(within(nsaLink).getByTestId('service-card-description')).toHaveTextContent(/Password-protected HTML documents/i);
});

test('adds an active Ladder card linking to /games/ladder', async () => {
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
  // Match by unique description text to avoid collision with the NSA card whose title also contains "Document".
  const documentLink = within(main).getByRole('link', { name: /Browse HTML documents organized in folders/i });

  expect(documentLink).toHaveAttribute('href', '/documents');
  expect(documentLink).toHaveTextContent('Active');
  expect(within(documentLink).getByTestId('service-card-description')).toHaveTextContent(/HTML documents organized in folders/i);
});

test('adds an active Viewer card linking to /viewer', async () => {
  render(await HomePage({ searchParams: Promise.resolve({}) }));

  const main = screen.getByRole('main');
  const viewerLink = within(main).getByRole('link', { name: /Viewer/i });

  expect(viewerLink).toHaveAttribute('href', '/viewer');
  expect(viewerLink).toHaveTextContent('Active');
  expect(within(viewerLink).getByTestId('service-card-description')).toHaveTextContent(/로컬 Markdown·HTML 파일을 열어/);
});

test('adds an active AeroAI card linking to /ai', async () => {
  render(await HomePage({ searchParams: Promise.resolve({}) }));

  const main = screen.getByRole('main');
  const aiLink = within(main).getByRole('link', { name: /AeroAI/i });

  expect(aiLink).toHaveAttribute('href', '/ai');
  expect(aiLink).toHaveTextContent('Active');
  expect(within(aiLink).getByTestId('service-card-description')).toHaveTextContent(/문서를 근거로 답하는 AI 어시스턴트/);
});

test('adds an external Notebook card opening the co-deploy app on port 8502 in a new tab', async () => {
  render(await HomePage({ searchParams: Promise.resolve({}) }));

  const main = screen.getByRole('main');
  const notebookLink = within(main).getByRole('link', { name: /Notebook/i });

  // 별도 폐쇄망 앱이라 같은 호스트의 :8502 로 새 탭 이동(외부 절대 URL).
  expect(notebookLink).toHaveAttribute('target', '_blank');
  expect(notebookLink).toHaveAttribute('rel', expect.stringContaining('noopener'));
  expect(notebookLink.getAttribute('href')).toMatch(/^http:\/\/[^/]+:8502$/);
  expect(notebookLink).toHaveTextContent('Active');
  expect(within(notebookLink).getByTestId('service-card-description')).toHaveTextContent(/NotebookLM 대안/);
});

test('home page uses dark theme from cookie', async () => {
  cookieThemeMock.mockReturnValue('dark');

  render(await HomePage({ searchParams: Promise.resolve({}) }));

  // 테마는 <html>(layout) 에 부착 — 셸이 아니라 토글 방향으로 dark 반영을 확인.
  expect(screen.getByRole('link', { name: '라이트 테마로 전환' })).toBeInTheDocument();
});
