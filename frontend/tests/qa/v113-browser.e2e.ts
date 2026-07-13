import { test, expect, type Page, type TestInfo } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const LOOPBACK = new Set(['localhost', '127.0.0.1', '::1']);
const QA_USERNAME = 'qa-admin';
const QA_PASSWORD = 'QA-admin-v1130-strong!';
const ROUTES = ['/login', '/activity', '/admin'];
const VIEWPORTS = [{ width: 375, height: 812 }, { width: 768, height: 1024 }, { width: 1280, height: 800 }];

type QaPage = Page & {
  __qaDone?: () => void;
  __qaNavigating?: boolean;
};

function installGuards(page: Page, testInfo: TestInfo) {
  const failures: string[] = [];
  const fail = (message: string) => failures.push(message);
  page.on('console', message => { if (message.type() === 'error') fail(`console error: ${message.text()}`); });
  page.on('pageerror', error => fail(`page error: ${error.message}`));
  page.on('requestfailed', request => {
    const url = new URL(request.url());
    const errorText = request.failure()?.errorText ?? 'unknown';
    const qaPage = page as QaPage;
    const expectedRscCancellation =
      errorText.includes('net::ERR_ABORTED')
      && url.searchParams.has('_rsc')
      && LOOPBACK.has(url.hostname);
    const expectedNavigationCancellation =
      errorText.includes('net::ERR_ABORTED')
      && qaPage.__qaNavigating === true
      && LOOPBACK.has(url.hostname);
    if (!expectedRscCancellation && !expectedNavigationCancellation) fail(`request failed (${errorText}): ${request.url()}`);
  });
  page.on('request', request => {
    const hostname = new URL(request.url()).hostname;
    if (!LOOPBACK.has(hostname)) fail(`non-loopback request: ${request.url()}`);
  });
  page.on('response', response => {
    if (response.status() >= 400) fail(`unexpected HTTP ${response.status()}: ${response.url()}`);
  });
  testInfo.attach('qa-network-guard', { body: 'loopback-only', contentType: 'text/plain' });
  return () => expect(failures, failures.join('\n')).toEqual([]);
}

async function gotoNetworkIdle(page: Page, route: string) {
  for (let attempt = 0; attempt < 3; attempt += 1) {
    try {
      return await page.goto(route, { waitUntil: 'networkidle' });
    } catch (error) {
      const aborted = error instanceof Error && error.message.includes('net::ERR_ABORTED');
      if (!aborted || attempt === 2) throw error;
      await page.waitForTimeout(50);
    }
  }
  throw new Error(`navigation retry exhausted: ${route}`);
}

async function visit(page: Page, route: string) {
  const qaPage = page as QaPage;
  qaPage.__qaNavigating = true;
  try {
    const response = await gotoNetworkIdle(page, route);
    expect(response?.status(), `${route} response`).toBeGreaterThanOrEqual(200);
    expect(response?.status(), `${route} response`).toBeLessThan(400);
    await expect(page.locator('body')).not.toHaveText('');
    await page.waitForTimeout(50);
  } finally {
    qaPage.__qaNavigating = false;
  }
}

async function login(page: Page) {
  await visit(page, '/login?next=/admin');
  await page.locator('input[autocomplete="username"]').fill(QA_USERNAME);
  await page.locator('input[autocomplete="current-password"]').fill(QA_PASSWORD);
  await page.getByRole('button', { name: '로그인' }).click();
  await page.waitForURL(url => url.pathname === '/admin');
  await page.waitForLoadState('networkidle');
  await expect.poll(
    async () => (await page.context().cookies()).map((cookie) => cookie.name),
  ).toContain('admin_session');
}
async function loginAs(page: Page, username: string, password: string, next = '/admin') {
  await visit(page, `/login?next=${encodeURIComponent(next)}`);
  await page.locator('input[autocomplete="username"]').fill(username);
  await page.locator('input[autocomplete="current-password"]').fill(password);
  await page.getByRole('button', { name: '로그인' }).click();
  await page.waitForURL(url => url.pathname === next);
  await page.waitForLoadState('networkidle');
}

async function assertPageQuality(page: Page, route: string, zoom = false) {
  const qaPage = page as QaPage;
  qaPage.__qaNavigating = true;
  try {
    const response = await gotoNetworkIdle(page, route);
    if (zoom) await page.evaluate(() => { document.documentElement.style.zoom = '200%'; });
    expect(response?.status(), `${route} response`).toBe(200);
    const quality = await page.evaluate(() => ({
      overflow: Math.max(0, document.documentElement.scrollWidth - window.innerWidth),
      replacement: document.body.innerText.includes('\ufffd'),
    }));
    expect(quality.overflow, `${route} horizontal overflow`).toBeLessThanOrEqual(1);
    expect(quality.replacement, `${route} replacement character`).toBe(false);
    await page.keyboard.press('Tab');
    await expect(page.locator(':focus')).toBeVisible();
    await page.waitForTimeout(50);
  } finally {
    qaPage.__qaNavigating = false;
  }
}

test.describe('smoke @smoke', () => {
  test.beforeEach(async ({ page }, testInfo) => { const done = installGuards(page, testInfo); testInfo.attach('guard-finalizer', { body: 'installed', contentType: 'text/plain' }); (page as QaPage).__qaDone = done; });
  test.afterEach(async ({ page }) => (page as QaPage).__qaDone?.());
  test('root and login respond with nonempty DOM @smoke', async ({ page }) => {
    await visit(page, '/');
    await visit(page, '/login');
  });
});

test.describe('route and viewport matrix @matrix', () => {
  test.beforeEach(async ({ page }, testInfo) => { const done = installGuards(page, testInfo); (page as QaPage).__qaDone = done; });
  test.afterEach(async ({ page }) => (page as QaPage).__qaDone?.());
  for (const viewport of VIEWPORTS) {
    test(`authenticated routes ${viewport.width}x${viewport.height} @matrix`, async ({ page }) => {
      await page.setViewportSize(viewport);
      await login(page);
      for (const route of ROUTES.slice(1)) await assertPageQuality(page, route);
    });
  }
  test('authenticated routes at representative 200% zoom @matrix', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await login(page);
    for (const route of ROUTES.slice(1)) {
      await assertPageQuality(page, route, true);
    }
  });
});

test.describe('accessibility @axe', () => {
  test.beforeEach(async ({ page }, testInfo) => { const done = installGuards(page, testInfo); (page as QaPage).__qaDone = done; });
  test.afterEach(async ({ page }) => (page as QaPage).__qaDone?.());
  test('moderate, serious, and critical violations are zero @axe', async ({ page }) => {
    await visit(page, '/login');
    const loginResult = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze();
    expect(loginResult.violations.filter(violation => ['moderate', 'serious', 'critical'].includes(violation.impact ?? ''))).toEqual([]);
    await login(page);
    for (const route of ROUTES.slice(1)) {
      await visit(page, route);
      const result = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze();
      const blocking = result.violations.filter(violation => ['moderate', 'serious', 'critical'].includes(violation.impact ?? ''));
      expect(blocking, `${route} accessibility violations`).toEqual([]);
    }
  });
});
test.describe('behavioral authorization matrix @matrix', () => {
  test.beforeEach(async ({ page }, testInfo) => { const done = installGuards(page, testInfo); (page as QaPage).__qaDone = done; });
  test.afterEach(async ({ page }) => (page as QaPage).__qaDone?.());

  test('anonymous redirect and invalid credentials remain safe @matrix', async ({ page }) => {
    await visit(page, '/activity');
    await expect(page).toHaveURL(/\/login\?next=%2Factivity/);
    const probe = await page.context().newPage();
    await probe.goto('/login?next=%2Factivity', { waitUntil: 'networkidle' });
    await probe.locator('input[autocomplete="username"]').fill('qa-normal');
    await probe.locator('input[autocomplete="current-password"]').fill('not-the-password');
    await probe.getByRole('button', { name: '로그인' }).click();
    await expect(probe.getByRole('alert')).toBeVisible();
    await expect(probe).toHaveURL(/\/login\?next=%2Factivity/);
    await expect(probe.getByRole('alert')).not.toContainText(/token|secret|password|hash|ip|user agent/i);
    await probe.close();
  });

  test('safe next succeeds and unsafe external next stays same-origin @matrix', async ({ page }) => {
    await loginAs(page, 'qa-normal', 'QA-normal-v1130-strong!', '/activity');
    await expect(page).toHaveURL(/\/activity$/);
    await page.getByRole('button', { name: /현재 로그인 사용자/ }).click();
    await page.getByRole('menuitem', { name: '로그아웃' }).click();
    await page.waitForURL(/\/login/);
    const probe = await page.context().newPage();
    await probe.goto('/login?next=https%3A%2F%2Fevil.example%2Fsteal', { waitUntil: 'networkidle' });
    await probe.locator('input[autocomplete="username"]').fill('qa-normal');
    await probe.locator('input[autocomplete="current-password"]').fill('QA-normal-v1130-strong!');
    await probe.getByRole('button', { name: '로그인' }).click();
    await probe.waitForLoadState('networkidle');
    expect(new URL(probe.url()).hostname).not.toBe('evil.example');
    expect(new URL(probe.url()).origin).toBe(new URL(page.url()).origin);
    await probe.close();
  });

  test('authenticated account and activity expose privacy-safe session evidence @matrix', async ({ page }) => {
    await loginAs(page, 'qa-normal', 'QA-normal-v1130-strong!', '/activity');
    await expect(page.locator('#activity-identity-heading')).toBeVisible();
    await expect(page.getByTestId('activity-username')).toHaveText('qa-normal');
    await expect(page.locator('#activity-sessions-heading')).toBeVisible();
    await expect(page.locator('#activity-auth-events-heading')).toBeVisible();
    const body = await page.locator('body').innerText();
    expect(body).not.toMatch(/\b(?:token|hash|prompt|user[- ]agent|ua|ip address|request body)\b/i);
    await page.getByRole('button', { name: /현재 로그인 사용자/ }).click();
    await expect(page.getByRole('menuitem', { name: '내 활동' })).toBeVisible();
    await expect(page.getByRole('menuitem', { name: 'Admin' })).toHaveCount(0);
  });

  test('normal user cannot see NSA, AI, or admin; qa-nsa sees empty NSA @matrix', async ({ page }) => {
    await loginAs(page, 'qa-normal', 'QA-normal-v1130-strong!', '/');
    await page.getByRole('button', { name: /현재 로그인 사용자/ }).click();
    await expect(page.getByRole('menuitem', { name: 'Admin' })).toHaveCount(0);
    await page.goto('/');
    await expect(page.getByRole('link', { name: 'NSA' })).toHaveCount(0);
    await expect(page.getByRole('link', { name: /AeroAI|AI/ })).toHaveCount(0);
    await page.goto('/nsa');
    await expect(page.getByText(/권한이 있는 계정|접근 권한/)).toBeVisible();
    await page.goto('/ai');
    await expect(page.getByText(/권한|로그인|접근/)).toBeVisible();

    await loginAs(page, 'qa-nsa', 'QA-nsa-v1130-strong!', '/nsa');
    await expect(page.getByRole('heading', { name: 'NSA' })).toBeVisible();
    await expect(page.getByText(/문서가 없습니다|찾을 수 없습니다|없습니다/)).toBeVisible();
  });

  test('admin overview, users, sessions, and modules controls render @matrix', async ({ page }) => {
    await login(page);
    await expect(page.getByText('운영 콘솔')).toBeVisible();
    for (const tab of ['사용자', '세션', '모듈']) {
      await page.getByRole('tab', { name: tab }).click();
      await expect(page.locator('[role="tabpanel"]')).toBeVisible();
    }
    await expect(page.getByRole('button', { name: /새로고침|정리|저장|추가|검색/ }).first()).toBeVisible();
  });

  test('live APIs reject unauthorized NSA and malformed activity safely @matrix', async ({ page }) => {
    const nsa = await page.request.get('/api/frontend/collections/nsa/list');
    expect([401, 403]).toContain(nsa.status());
    await loginAs(page, 'qa-normal', 'QA-normal-v1130-strong!', '/activity');
    const activity = await page.request.get('/api/frontend/auth/activity');
    expect(activity.status()).toBe(200);
    const malformed = await page.request.get('/api/frontend/auth/activity?unexpected=1');
    expect(malformed.status()).toBe(422);
    const payload = await malformed.json();
    expect(JSON.stringify(payload)).not.toMatch(/token|hash|prompt|body|user[- ]agent|ip/i);
  });
});
