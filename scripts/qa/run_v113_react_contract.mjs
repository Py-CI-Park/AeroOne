import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { redact as redactValue, invalidateReceiptFiles } from './redact_v113.mjs';

const REPO_ROOT = path.resolve(import.meta.dirname, '../..');
const QA_PASSWORD = 'QA-admin-v1130-strong!';
const REQUIRED = { 'react-doctor': '0.7.3', 'react-scan': '0.5.7', 'react-grab': '0.1.48' };
const ASSETS = { 'react-doctor': ['bin/react-doctor.js'], 'react-scan': ['bin/cli.js', 'dist/auto.global.js'], 'react-grab': ['bin/cli.js'] };
const ENTRYPOINTS = { 'react-doctor': 'bin/react-doctor.js', 'react-scan': 'bin/cli.js', 'react-grab': 'bin/cli.js' };

function fail(message) { throw new Error(message); }
function git(args) { return spawnSync('git', args, { cwd: REPO_ROOT, encoding: 'utf8', shell: false, windowsHide: true }); }
function redact(value) { return redactValue(value, { replacements: [[REPO_ROOT, '[REPO_ROOT]'], [QA_PASSWORD, '[REDACTED]']] }); }
function assertCleanSha(sha, gitRunner = git) {
  const head = gitRunner(['rev-parse', 'HEAD']);
  if (head.error || head.status !== 0 || head.stdout.trim() !== sha) fail('git HEAD does not match requested SHA');
  const status = gitRunner(['status', '--porcelain']);
  if (status.error || status.status !== 0 || status.stdout.trim()) fail('git worktree is dirty');
}
function prepareReceiptRun(artifactRoot, sha, gitRunner = git, invalidate = invalidateReceiptFiles) {
  fs.mkdirSync(artifactRoot, { recursive: true });
  invalidate(artifactRoot);
  assertCleanSha(sha, gitRunner);
}
function packageRoot(name, frontendRoot) { return path.join(frontendRoot, 'node_modules', name); }
function verifyInstallation(name, frontendRoot) {
  const lock = JSON.parse(fs.readFileSync(path.join(frontendRoot, 'package-lock.json'), 'utf8'));
  const lockEntry = lock.packages?.[`node_modules/${name}`];
  const root = packageRoot(name, frontendRoot);
  const manifestPath = path.join(root, 'package.json');
  if (!lockEntry?.version || lockEntry.version !== REQUIRED[name]) fail(`${name} lock version mismatch`);
  if (!fs.existsSync(manifestPath)) fail(`${name} installed manifest missing`);
  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
  if (manifest.version !== lockEntry.version || manifest.version !== REQUIRED[name]) fail(`${name} installed version mismatch`);
  for (const asset of ASSETS[name]) if (!fs.existsSync(path.join(root, asset))) fail(`${name} locked local browser asset missing: ${asset}`);
  return { name, version: manifest.version, kind: 'not-applicable', invoked: false, applicable: false, versionScope: `${name}@${manifest.version}`, executableEvidence: ENTRYPOINTS[name], reason: 'No documented non-mutating deterministic analysis mode is provided by the locked local entrypoint.' };
}
function loopbackEgress(value) { try { const u = new URL(value); return ['http:', 'https:', 'ws:', 'wss:'].includes(u.protocol) && ['127.0.0.1', 'localhost', '[::1]', '::1'].includes(u.hostname) && !u.username && !u.password; } catch { return false; } }
async function browserRequestGuard(context, violations = []) {
  await context.route('**/*', route => {
    const u = new URL(route.request().url());
    if (/^https?:$/.test(u.protocol) && !loopbackEgress(u.href)) { violations.push(u.href); return route.abort('blockedbyclient'); }
    return route.continue();
  });
  if (typeof context.routeWebSocket === 'function') await context.routeWebSocket('**/*', socket => {
    const url = socket.url();
    if (!loopbackEgress(url)) { violations.push(url); return socket.close(); }
    return socket.connectToServer();
  });
}

export { redact, assertCleanSha, prepareReceiptRun, verifyInstallation, browserRequestGuard, packageRoot, REQUIRED, ASSETS, ENTRYPOINTS, QA_PASSWORD };
