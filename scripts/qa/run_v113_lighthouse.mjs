#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import process from 'node:process';

const VERSION = 'v1.13.0';
const REPO_ROOT = path.resolve(import.meta.dirname, '../..');
const FRONTEND_REQUIRE = createRequire(path.join(REPO_ROOT, 'frontend', 'package.json'));
const ROUTES = ['/login', '/activity', '/admin'];
const AUTHENTICATED_ROUTES = new Set(['/activity', '/admin']);
const FORM_FACTORS = ['mobile', 'desktop'];
const RUNS = 3;
const THRESHOLDS = { performance: 100, accessibility: 100, 'best-practices': 100, seo: 100 };
const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const REQUIRED_SCHEMA_KEYS = ['schemaVersion', 'sha', 'backendUrl', 'frontendUrl', 'backendPid', 'frontendPid', 'tempRoot', 'artifactRoot'];
const QA_USERNAME = 'qa-admin';
const QA_PASSWORD = 'QA-admin-v1130-strong!';
const CHROME_FLAGS = ['--headless=new', '--no-first-run', '--no-default-browser-check', '--disable-background-networking', '--disable-component-update', '--disable-default-apps', '--disable-sync', '--disable-extensions', '--disable-features=Translate,MediaRouter,OptimizationHints'];
const SCREEN_EMULATION = {
  mobile: { mobile: true, width: 360, height: 640, deviceScaleFactor: 2.625, disabled: false },
  desktop: { mobile: false, width: 1350, height: 940, deviceScaleFactor: 1, disabled: false },
};

function fail(message) { throw new Error(message); }
function parseArgs(argv) {
  const out = { sha: null, runtime: null };
  for (let i = 2; i < argv.length; i += 1) {
    if (argv[i] === '--sha') out.sha = argv[++i];
    else if (argv[i] === '--runtime') out.runtime = argv[++i];
    else fail(`unknown argument: ${argv[i]}`);
  }
  if (!out.sha || !/^[a-f0-9]{40}$/.test(out.sha)) fail('missing or invalid --sha');
  const derived = path.resolve(REPO_ROOT, 'artifacts', 'qa', VERSION, out.sha, 'runtime', 'runtime.json');
  if (out.runtime && path.resolve(out.runtime) !== derived) fail('--runtime does not match --sha runtime path');
  return { ...out, runtime: out.runtime ?? derived };
}
function isLoopbackUrl(value) {
  try { const u = new URL(value); return u.protocol === 'http:' && (u.hostname === '127.0.0.1' || u.hostname === 'localhost') && u.username === '' && u.password === '' && !u.pathname.includes('..'); } catch { return false; }
}
function validateRuntime(runtimeFile, expectedSha) {
  const runtimePath = path.resolve(runtimeFile); const root = path.dirname(path.dirname(runtimePath));
  const value = JSON.parse(fs.readFileSync(runtimePath, 'utf8'));
  if (!value || typeof value !== 'object' || Object.keys(value).sort().join(',') !== REQUIRED_SCHEMA_KEYS.slice().sort().join(',')) fail('runtime schema keys mismatch');
  if (value.schemaVersion !== 1 || !/^[a-f0-9]{40}$/.test(value.sha) || value.sha !== expectedSha || value.sha !== path.basename(root)) fail('runtime schema or SHA mismatch');
  if (!isLoopbackUrl(value.backendUrl) || !isLoopbackUrl(value.frontendUrl)) fail('runtime URL is not loopback-only');
  for (const key of ['backendPid', 'frontendPid']) if (!Number.isInteger(value[key]) || value[key] <= 0) fail(`invalid ${key}`);
  if (!path.isAbsolute(value.tempRoot) || !path.isAbsolute(value.artifactRoot)) fail('runtime roots must be absolute');
  const artifactRoot = path.resolve(value.artifactRoot); if (artifactRoot !== path.resolve(root, 'browser')) fail('artifactRoot escapes owned SHA root');
  fs.mkdirSync(artifactRoot, { recursive: true }); return { ...value, runtimePath, artifactRoot, frontendBase: new URL(value.frontendUrl).origin };
}
function redact(value) {
  if (typeof value === 'string') return value.replaceAll(QA_PASSWORD, '[REDACTED]').replace(/(authorization|cookie|token|secret|password|api[-_]?key)\s*[:=]\s*[^,\s]+/gi, '$1=[REDACTED]').replace(/[A-Za-z0-9+/_=-]{32,}/g, '[REDACTED]');
  if (Array.isArray(value)) return value.map(redact);
  if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).map(([k, v]) => [k, /secret|token|password|cookie|authorization|credential|header/i.test(k) ? '[REDACTED]' : redact(v)]));
  return value;
}
function median(values) { const sorted = values.slice().sort((a, b) => a - b); return sorted[Math.floor(sorted.length / 2)]; }
async function authenticate(frontendBase) {
  const response = await fetch(`${frontendBase}/api/frontend/auth/login`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ username: QA_USERNAME, password: QA_PASSWORD }), redirect: 'manual' });
  if (!response.ok) fail('synthetic admin authentication failed');
  const setCookies = typeof response.headers.getSetCookie === 'function' ? response.headers.getSetCookie() : (response.headers.get('set-cookie') ? [response.headers.get('set-cookie')] : []);
  const pairs = setCookies.map((cookie) => cookie.split(';', 1)[0]).filter((pair) => /^[^=;]+=[^=;]*$/.test(pair));
  if (pairs.length < 2) fail('synthetic admin authentication did not return the session cookie pair');
  return pairs.slice(0, 2).join('; ');
}
function assertRequestedPath(output, requestedUrl, route) {
  const finalUrl = output?.lhr?.finalDisplayedUrl ?? output?.lhr?.finalUrl;
  if (typeof finalUrl !== 'string' || new URL(finalUrl).origin !== new URL(requestedUrl).origin || new URL(finalUrl).pathname !== route) fail(`audit redirected away from requested route ${route}`);
}

async function importFrontendPackage(name) {
  const resolved = FRONTEND_REQUIRE.resolve(name);
  return import(pathToFileURL(resolved).href);
}
async function run() {
  const args = parseArgs(process.argv); const runtime = validateRuntime(args.runtime, args.sha);
  if (!fs.existsSync(CHROME_PATH)) fail(`stable Chrome not found: ${CHROME_PATH}`);
  const { default: lighthouse } = await importFrontendPackage('lighthouse'); const { launch } = await importFrontendPackage('chrome-launcher');
  let chrome; let sessionCookie;
  const results = [];
  try {
    sessionCookie = await authenticate(runtime.frontendBase);
    chrome = await launch({ chromePath: CHROME_PATH, chromeFlags: CHROME_FLAGS });
    if (!Number.isInteger(chrome.port) || chrome.port <= 0) fail('chrome-launcher returned invalid debugging port');
    for (const route of ROUTES) for (const formFactor of FORM_FACTORS) {
      const scores = [];
      for (let iteration = 1; iteration <= RUNS; iteration += 1) {
        const url = `${runtime.frontendBase}${route}`; if (!isLoopbackUrl(url)) fail('constructed URL is not loopback-only');
        const output = await lighthouse(url, { port: chrome.port, formFactor, screenEmulation: SCREEN_EMULATION[formFactor], throttlingMethod: 'provided', extraHeaders: AUTHENTICATED_ROUTES.has(route) ? { Cookie: sessionCookie } : {}, onlyCategories: Object.keys(THRESHOLDS), output: 'json', logLevel: 'error', maxWaitForFcp: 30000, maxWaitForLoad: 60000 });
        assertRequestedPath(output, url, route);
        const categories = output?.lhr?.categories ?? {};
        const scoresForRun = Object.fromEntries(Object.keys(THRESHOLDS).map((key) => [key, Math.round((categories[key]?.score ?? -1) * 100)]));
        const failedAudits = Object.entries(categories).flatMap(([category, value]) =>
          (value?.auditRefs ?? [])
            .filter((ref) => ref.weight > 0 && (output?.lhr?.audits?.[ref.id]?.score ?? 1) < 1)
            .map((ref) => ({ category, id: ref.id, score: output.lhr.audits[ref.id].score })),
        );
        scores.push(scoresForRun);
        results.push({ route, formFactor, iteration, scores: scoresForRun, failedAudits });
      }
      const medians = Object.fromEntries(Object.keys(THRESHOLDS).map((key) => [key, median(scores.map((s) => s[key]))]));
      if (Object.values(medians).some((score) => score !== 100)) {
        const failedAudits = results.slice(-RUNS).flatMap((result) => result.failedAudits);
        fail(`${route} ${formFactor} median threshold failure: ${JSON.stringify({ medians, failedAudits })}`);
      }
    }
    fs.writeFileSync(path.join(runtime.artifactRoot, 'lighthouse.json'), `${JSON.stringify(redact({ schemaVersion: 1, sha: runtime.sha, routes: ROUTES, formFactors: FORM_FACTORS, runs: RUNS, thresholds: THRESHOLDS, results }), null, 2)}\n`, 'utf8');
  } finally { sessionCookie = undefined; if (chrome) await chrome.kill(); }
}
run().catch((error) => { console.error(`lighthouse QA failed: ${redact(error.message)}`); process.exitCode = 1; });
export { parseArgs, validateRuntime, redact, authenticate, assertRequestedPath, ROUTES, FORM_FACTORS, RUNS, THRESHOLDS };
