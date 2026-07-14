#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import { redact, assertCleanSha, prepareReceiptRun, verifyInstallation, browserRequestGuard, packageRoot, REQUIRED, ASSETS, ENTRYPOINTS, QA_PASSWORD } from './run_v113_react_contract.mjs';
const VERSION = 'v1.13.0';
const REPO_ROOT = path.resolve(import.meta.dirname, '../..');
const require = createRequire(import.meta.url);
const { chromium } = require(path.join(REPO_ROOT, 'frontend', 'node_modules', 'playwright-core'));
const QA_USERNAME = 'qa-admin';
const REQUIRED_SCHEMA_KEYS = ['schemaVersion', 'sha', 'backendUrl', 'frontendUrl', 'backendPid', 'frontendPid', 'tempRoot', 'artifactRoot'];
function fail(message) { throw new Error(message); }
function parseArgs(argv) { const out = { sha: null, runtime: null }; for (let i = 2; i < argv.length; i += 1) { if (argv[i] === '--sha') out.sha = argv[++i]; else if (argv[i] === '--runtime') out.runtime = argv[++i]; else fail(`unknown argument: ${argv[i]}`); } if (!out.sha || !/^[a-f0-9]{40}$/.test(out.sha)) fail('missing or invalid --sha'); const derived = path.resolve(REPO_ROOT, 'artifacts', 'qa', VERSION, out.sha, 'runtime', 'runtime.json'); if (out.runtime && path.resolve(out.runtime) !== derived) fail('--runtime does not match --sha runtime path'); return { ...out, runtime: out.runtime ?? derived }; }
function loopback(value) { try { const u = new URL(value); return u.protocol === 'http:' && ['127.0.0.1', 'localhost', '[::1]', '::1'].includes(u.hostname) && !u.username && !u.password; } catch { return false; } }
function validateRuntime(runtimeFile, expectedSha) { const runtimePath = path.resolve(runtimeFile); const shaRoot = path.dirname(path.dirname(runtimePath)); const value = JSON.parse(fs.readFileSync(runtimePath, 'utf8')); if (!value || typeof value !== 'object' || Object.keys(value).sort().join(',') !== REQUIRED_SCHEMA_KEYS.slice().sort().join(',')) fail('runtime schema keys mismatch'); if (value.schemaVersion !== 1 || value.sha !== expectedSha || value.sha !== path.basename(shaRoot)) fail('runtime SHA mismatch'); if (!loopback(value.backendUrl) || !loopback(value.frontendUrl)) fail('runtime URL is not loopback-only'); for (const key of ['backendPid', 'frontendPid']) if (!Number.isInteger(value[key]) || value[key] <= 0) fail(`invalid ${key}`); if (!path.isAbsolute(value.tempRoot) || path.resolve(value.artifactRoot) !== path.resolve(shaRoot, 'browser')) fail('unsafe runtime roots'); fs.mkdirSync(value.artifactRoot, { recursive: true }); return { ...value, runtimePath, artifactRoot: path.resolve(value.artifactRoot) }; }
function runDoctor(frontendRoot, verified) {
  const entryPoint = path.join(packageRoot('react-doctor', frontendRoot), ENTRYPOINTS['react-doctor']);
  const allowedEnv = ['PATH', 'Path', 'SYSTEMROOT', 'SystemRoot', 'WINDIR', 'TEMP', 'TMP', 'COMSPEC', 'PATHEXT', 'NUMBER_OF_PROCESSORS'];
  const env = Object.fromEntries(allowedEnv.filter(key => process.env[key] !== undefined).map(key => [key, process.env[key]]));
  Object.assign(env, { NODE_ENV: 'test', CI: '1', HTTP_PROXY: 'http://127.0.0.1:9', HTTPS_PROXY: 'http://127.0.0.1:9', ALL_PROXY: 'http://127.0.0.1:9', NO_PROXY: '', npm_config_offline: 'true', REACT_DOCTOR_TELEMETRY: '0' });
  const result = spawnSync(process.execPath, [entryPoint, '.', '--json', '--no-supply-chain', '--no-score', '--no-telemetry', '--no-color', '--yes', '--blocking', 'error'], { cwd: frontendRoot, encoding: 'utf8', shell: false, timeout: 120000, env });
  if (result.error) fail('react-doctor invocation failed'); let report; try { report = JSON.parse(result.stdout); } catch { fail('react-doctor did not emit valid JSON'); }
  const blocking = []; const visit = (v, key = '') => { if (Array.isArray(v)) return v.forEach(x => visit(x, key)); if (!v || typeof v !== 'object') return; const s = String(v.severity ?? v.level ?? '').toLowerCase(); if (['error', 'critical', 'high'].includes(s) || v.blocking === true) blocking.push({ key, severity: s }); Object.entries(v).forEach(([k, x]) => visit(x, k)); }; visit(report); if (result.status !== 0 || blocking.length) fail('react-doctor reported blocking findings'); return { name: 'react-doctor', version: verified.version, kind: 'analysis', invoked: true, status: result.status, blockingFindings: blocking, report: redact(report) };
}
async function runReactScan(frontendRoot, frontendUrl, verified) {
  const bundle = fs.readFileSync(path.join(packageRoot('react-scan', frontendRoot), 'dist', 'auto.global.js'), 'utf8');
  const marker = '}({});';
  const markerIndex = bundle.lastIndexOf(marker);
  if (markerIndex < 0) fail('react-scan locked browser asset export contract changed');
  const exposedBundle = [
    "Object.defineProperty(Navigator.prototype, 'onLine', { configurable: true, get: () => false });",
    bundle.slice(0, markerIndex),
    '}(globalThis.__AEROONE_REACT_SCAN__ = {});',
    bundle.slice(markerIndex + marker.length),
    `globalThis.__AEROONE_REACT_SCAN_EVIDENCE__ = { commits: 0, renders: 0, unnecessaryRenders: 0 };
globalThis.__AEROONE_REACT_SCAN__.scan({
  enabled: true,
  dangerouslyForceRunInProduction: true,
  showToolbar: false,
  log: false,
  trackUnnecessaryRenders: true,
  onCommitStart() {
    globalThis.__AEROONE_REACT_SCAN_EVIDENCE__.commits += 1;
  },
  onRender(_fiber, renders) {
    const rows = Array.isArray(renders) ? renders : [];
    globalThis.__AEROONE_REACT_SCAN_EVIDENCE__.renders += rows.length;
    globalThis.__AEROONE_REACT_SCAN_EVIDENCE__.unnecessaryRenders += rows.filter(row => row?.unnecessary === true).length;
  },
});`,
  ].join('');

  const browser = await chromium.launch({
    executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    headless: true,
    args: ['--disable-background-networking', '--disable-component-update', '--disable-default-apps', '--disable-sync'],
  });
  const context = await browser.newContext({ serviceWorkers: 'block' });
  const page = await context.newPage();
  const egressViolations = [];
  await browserRequestGuard(context, egressViolations);
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
  await page.addInitScript({ content: exposedBundle });
  const routes = ['/login', '/activity', '/admin'];
  const evidence = [];

  try {
    for (const route of routes) {
      if (route === '/activity') {
        const login = await context.request.post(`${frontendUrl}/api/frontend/auth/login`, {
          data: { username: QA_USERNAME, password: QA_PASSWORD },
        });
        if (!login.ok()) fail('react-scan synthetic authentication failed');
      }
      const response = await page.goto(`${frontendUrl}${route}`, { waitUntil: 'networkidle', timeout: 120000 });
      if (!response?.ok() || new URL(page.url()).pathname !== route) fail(`react-scan route failed: ${route}`);
      const identity = await page.evaluate(() => ({
        heading: document.querySelector('h1,h2')?.textContent?.trim(),
        accountLabel: document.querySelector('[aria-label^="현재 로그인 사용자 "]')?.getAttribute('aria-label'),
      }));
      const expectedHeading = route === '/login' ? '계정 접속' : route === '/activity' ? '내 활동' : '관리자 콘솔';
      if (identity.heading !== expectedHeading) fail(`route identity mismatch: ${route}`);
      if (route === '/admin' && identity.accountLabel !== `현재 로그인 사용자 ${QA_USERNAME}`) fail('admin authorization identity missing');
      await page.waitForTimeout(250);
      const state = await page.evaluate(() => {
        const api = globalThis.__AEROONE_REACT_SCAN__;
        const callbackEvidence = globalThis.__AEROONE_REACT_SCAN_EVIDENCE__;
        const report = api?.getReport?.();
        const reports = report instanceof Map
          ? Array.from(report.values()).map(item => {
            const renders = Array.isArray(item?.renders) ? item.renders : [];
            return {
              displayName: item?.displayName ?? null,
              renderCount: renders.length,
              commitCount: renders.filter(render => render?.didCommit === true).length,
              unnecessaryCount: renders.filter(render => render?.unnecessary === true).length,
            };
          })
          : [];
        return {
          active: Boolean(api?.ReactScanInternals?.instrumentation),
          callbackEvidence: {
            commits: callbackEvidence?.commits ?? 0,
            renders: callbackEvidence?.renders ?? 0,
            unnecessaryRenders: callbackEvidence?.unnecessaryRenders ?? 0,
          },
          reports,
          url: location.pathname,
        };
      });
      if (!state.active) fail('react-scan instrumentation did not initialize');
      if (!state.callbackEvidence.renders || !state.callbackEvidence.commits) fail(`react-scan produced no render/commit evidence: ${route}`);
      evidence.push(state);
    }
  } finally {
    await context.close();
    await browser.close();
  }

  if (egressViolations.length) fail(`react-scan blocked non-loopback egress (${egressViolations.length})`);
  if (errors.length) fail('react-scan instrumentation error');
  const commits = evidence.reduce((sum, item) => sum + item.callbackEvidence.commits, 0);
  const renders = evidence.reduce((sum, item) => sum + item.callbackEvidence.renders, 0);
  const unnecessaryRenders = evidence.reduce((sum, item) => sum + item.callbackEvidence.unnecessaryRenders, 0);
  if (!commits || !renders) fail('react-scan produced no render/commit evidence');
  if (unnecessaryRenders) fail('react-scan reported unnecessary renders');
  return {
    name: 'react-scan',
    version: verified.version,
    kind: 'analysis',
    invoked: true,
    mode: 'local-browser-auto-global',
    routes,
    commits,
    renders,
    unnecessaryRenders,
    evidence: redact(evidence),
  };
}
async function run() {
  const args = parseArgs(process.argv);
  const expectedArtifactRoot = path.resolve(REPO_ROOT, 'artifacts', 'qa', VERSION, args.sha, 'browser');
  prepareReceiptRun(expectedArtifactRoot, args.sha);
  const finalPath = path.join(expectedArtifactRoot, 'react-diagnostics.json');
  const runtime = validateRuntime(args.runtime, args.sha);
  const frontendRoot = path.resolve(REPO_ROOT, 'frontend');
  const verified = Object.fromEntries(Object.keys(REQUIRED).map(name => [name, verifyInstallation(name, frontendRoot)]));
  const tools = [
    runDoctor(frontendRoot, verified['react-doctor']),
    await runReactScan(frontendRoot, runtime.frontendUrl, verified['react-scan']),
    verified['react-grab'],
  ];
  const tempPath = path.join(runtime.artifactRoot, `react-diagnostics.${process.pid}.${Date.now()}.tmp`);
  try {
    fs.writeFileSync(tempPath, `${JSON.stringify({ schemaVersion: 1, sha: runtime.sha, tools }, null, 2)}\n`, { mode: 0o600 });
    assertCleanSha(args.sha);
    fs.renameSync(tempPath, finalPath);
  } catch (error) {
    fs.rmSync(tempPath, { force: true });
    throw error;
  }
}
const invokedPath = process.argv[1] ? pathToFileURL(path.resolve(process.argv[1])).href : null;
if (invokedPath && import.meta.url === invokedPath) run().catch(error => { console.error(`react diagnostics failed: ${redact(error.message)}`); process.exitCode = 1; });
export { parseArgs, validateRuntime, redact, verifyInstallation, runDoctor, runReactScan, assertCleanSha, prepareReceiptRun, browserRequestGuard, run, REQUIRED, ASSETS };
