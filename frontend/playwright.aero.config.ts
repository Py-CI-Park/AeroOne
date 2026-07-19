import { defineConfig, devices } from '@playwright/test';
import path from 'node:path';

// Aero Work E2E (G007) — 이미 가동 중인 라이브 서버(프런트 :29501, 백엔드 :18437)를 그대로 쓴다.
// v113 QA 인프라(playwright.qa.config.ts)와 달리 SHA 고정 runtime.json 게이트, webServer 재기동을
// 요구하지 않는다 — 이 스위트는 살아있는 개발 서버를 대상으로 한 시나리오 검증 전용이다.
const repoRoot = path.resolve(process.cwd(), '..');
const artifactRoot = path.join(repoRoot, 'artifacts', 'qa', 'ultragoal', 'G007');

export default defineConfig({
  testDir: './tests/qa',
  testMatch: /aero-work\.e2e\.ts/,
  outputDir: path.join(artifactRoot, 'playwright-output'),
  timeout: 600_000,
  expect: { timeout: 20_000 },
  fullyParallel: false,
  forbidOnly: true,
  retries: 0,
  workers: 1,
  reporter: [
    ['line'],
    ['json', { outputFile: path.join(artifactRoot, 'results.json') }],
  ],
  use: {
    ...devices['Desktop Chrome'],
    browserName: 'chromium',
    headless: true,
    trace: 'retain-on-failure',
    screenshot: 'off',
    video: 'off',
    baseURL: 'http://localhost:29501',
    acceptDownloads: true,
  },
});
