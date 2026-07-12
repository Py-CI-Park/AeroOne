import { test, expect, type Page, type TestInfo } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const LOOPBACK = new Set(['localhost', '127.0.0.1', '::1']);
const QA_USERNAME = 'qa-admin';
const QA_PASSWORD = 'QA-admin-v1130-strong!';
const ROUTES = ['/login', '/activity', '/admin'];
const VIEWPORTS = [{ width: 375, height: 812 }, { width: 768, height: 1024 }, { width: 1280, height: 800 }];

function installGuards(page: Page, testInfo: TestInfo) {
  const failures: string[] = [];
  const fail = (message: string) => failures.push(message);
  page.on('console', message => { if (message.type() === 'error') fail(`console error: ${message.text()}`); });
  page.on('pageerror', error => fail(`page error: ${error.message}`));
  page.on('requestfailed', request => {
    const url = new URL(request.url());
    const errorText = request.failure()?.errorText ?? 'unknown';
    const expectedRscCancellation =
      errorText.includes('net::ERR_ABORTED')
      && url.searchParams.has('_rsc')
      && LOOPBACK.has(url.hostname);
    if (!expectedRscCancellation) fail(`request failed (${errorText}): ${request.url()}`);
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

async function visit(page: Page, route: string) {
  const response = await page.goto(route, { waitUntil: 'domcontentloaded' });
  expect(response?.status(), `${route} response`).toBeGreaterThanOrEqual(200);
  expect(response?.status(), `${route} response`).toBeLessThan(400);
  await expect(page.locator('body')).not.toHaveText('');
}

async function login(page: Page) {
  await visit(page, '/login');
  await page.locator('input[autocomplete="username"]').fill(QA_USERNAME);
  await page.locator('input[autocomplete="current-password"]').fill(QA_PASSWORD);
  await page.getByRole('button', { name: '로그인' }).click();
  await page.waitForURL(/\/admin(?:$|\?)/);
}

async function assertPageQuality(page: Page, route: string, zoom = false) {
  const response = await page.goto(route, { waitUntil: 'networkidle' });
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
}

test.describe('smoke @smoke', () => {
  test.beforeEach(async ({ page }, testInfo) => { const done = installGuards(page, testInfo); testInfo.attach('guard-finalizer', { body: 'installed', contentType: 'text/plain' }); (page as Page & { __qaDone?: () => void }).__qaDone = done; });
  test.afterEach(async ({ page }) => (page as Page & { __qaDone?: () => void }).__qaDone?.());
  test('root and login respond with nonempty DOM @smoke', async ({ page }) => {
    await visit(page, '/');
    await visit(page, '/login');
  });
});

test.describe('route and viewport matrix @matrix', () => {
  test.beforeEach(async ({ page }, testInfo) => { const done = installGuards(page, testInfo); (page as Page & { __qaDone?: () => void }).__qaDone = done; });
  test.afterEach(async ({ page }) => (page as Page & { __qaDone?: () => void }).__qaDone?.());
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
  test.beforeEach(async ({ page }, testInfo) => { const done = installGuards(page, testInfo); (page as Page & { __qaDone?: () => void }).__qaDone = done; });
  test.afterEach(async ({ page }) => (page as Page & { __qaDone?: () => void }).__qaDone?.());
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
