import { defineConfig, devices } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const chromePath = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const sha = process.env.QA_SHA ?? process.env.GIT_SHA ?? process.env.GIT_COMMIT_SHA;
if (!sha || !/^[0-9a-f]{40}$/.test(sha)) {
  throw new Error('QA_SHA (or GIT_SHA/GIT_COMMIT_SHA) must be the exact 40-character lowercase revision');
}

const repoRoot = path.resolve(process.cwd(), '..');
const runtimePath = path.join(repoRoot, 'artifacts', 'qa', 'v1.13.0', sha, 'runtime', 'runtime.json');
const runtime = JSON.parse(fs.readFileSync(runtimePath, 'utf8')) as {
  schemaVersion: number;
  sha: string;
  backendUrl: string;
  frontendUrl: string;
  backendPid: number;
  frontendPid: number;
  tempRoot: string;
  artifactRoot: string;
};
const runtimeFields = ['schemaVersion', 'sha', 'backendUrl', 'frontendUrl', 'backendPid', 'frontendPid', 'tempRoot', 'artifactRoot'];
if (!runtime || typeof runtime !== 'object' || Object.keys(runtime).sort().join(',') !== runtimeFields.sort().join(',')) {
  throw new Error('QA runtime metadata fields do not match schema');
}
if (runtime.schemaVersion !== 1 || runtime.sha !== sha) throw new Error('Unsupported QA runtime metadata');
for (const key of ['backendUrl', 'frontendUrl'] as const) {
  const url = new URL(runtime[key]);
  if (!['http:', 'https:'].includes(url.protocol) || !['localhost', '127.0.0.1', '::1'].includes(url.hostname)) {
    throw new Error('QA traffic must remain loopback-only');
  }
}
if (!Number.isInteger(runtime.backendPid) || runtime.backendPid <= 0 || !Number.isInteger(runtime.frontendPid) || runtime.frontendPid <= 0) {
  throw new Error('Invalid QA runtime process metadata');
}
if (!path.isAbsolute(runtime.tempRoot) || !path.isAbsolute(runtime.artifactRoot)) {
  throw new Error('QA runtime roots must be absolute paths');
}
const artifactRoot = path.resolve(runtime.artifactRoot);
const expectedArtifactRoot = path.join(repoRoot, 'artifacts', 'qa', 'v1.13.0', sha, 'browser');
if (artifactRoot !== expectedArtifactRoot) throw new Error('QA artifacts must remain under the redacted revision root');

export default defineConfig({
  testDir: './tests/qa',
  outputDir: path.join(artifactRoot, 'playwright'),
  timeout: 30_000,
  fullyParallel: false,
  forbidOnly: true,
  retries: 0,
  workers: 1,
  reporter: [['line'], ['json', { outputFile: path.join(artifactRoot, 'playwright', 'results.json') }]],
  use: {
    ...devices['Desktop Chrome'],
    browserName: 'chromium',
    launchOptions: { executablePath: chromePath },
    headless: true,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    baseURL: runtime.frontendUrl,
  },
  projects: [
    { name: 'smoke', testMatch: /v113-browser\.e2e\.ts/, grep: /@smoke/ },
    { name: 'matrix', testMatch: /v113-browser\.e2e\.ts/, grep: /@matrix/ },
    { name: 'axe', testMatch: /v113-browser\.e2e\.ts/, grep: /@axe/ },
  ],
});
