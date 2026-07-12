#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { spawnSync } from 'node:child_process';

const VERSION = '1.13.0';
const REQUIRED = { 'react-doctor': '0.7.3', 'react-scan': '0.5.7', 'react-grab': '0.1.48' };
const REQUIRED_SCHEMA_KEYS = ['schemaVersion', 'sha', 'backendUrl', 'frontendUrl', 'backendPid', 'frontendPid', 'tempRoot', 'artifactRoot'];
const ASSETS = { 'react-doctor': ['bin/react-doctor.js'], 'react-scan': ['bin/cli.js', 'dist/index.mjs', 'dist/auto.global.js'], 'react-grab': ['bin/cli.js', 'dist/index.js', 'dist/index.global.js'] };
function fail(message) { throw new Error(message); }
function parseArgs(argv) { const out = { sha: null, runtime: null }; for (let i = 2; i < argv.length; i += 1) { if (argv[i] === '--sha') out.sha = argv[++i]; else if (argv[i] === '--runtime') out.runtime = argv[++i]; else fail(`unknown argument: ${argv[i]}`); } if (!out.sha || !/^[a-f0-9]{40}$/.test(out.sha)) fail('missing or invalid --sha'); const derived = path.resolve(process.cwd(), 'artifacts', 'qa', VERSION, out.sha, 'runtime', 'runtime.json'); if (out.runtime && path.resolve(out.runtime) !== derived) fail('--runtime does not match --sha runtime path'); return { ...out, runtime: out.runtime ?? derived }; }
function loopback(value) { try { const u = new URL(value); return u.protocol === 'http:' && (u.hostname === '127.0.0.1' || u.hostname === 'localhost') && !u.username && !u.password; } catch { return false; } }
function validateRuntime(runtimeFile, expectedSha) { const runtimePath = path.resolve(runtimeFile); const shaRoot = path.dirname(path.dirname(runtimePath)); const value = JSON.parse(fs.readFileSync(runtimePath, 'utf8')); if (!value || typeof value !== 'object' || Object.keys(value).sort().join(',') !== REQUIRED_SCHEMA_KEYS.slice().sort().join(',')) fail('runtime schema keys mismatch'); if (value.schemaVersion !== 1 || !/^[a-f0-9]{40}$/.test(value.sha) || value.sha !== expectedSha || value.sha !== path.basename(shaRoot)) fail('runtime SHA mismatch'); if (!loopback(value.backendUrl) || !loopback(value.frontendUrl)) fail('runtime URL is not loopback-only'); for (const key of ['backendPid', 'frontendPid']) if (!Number.isInteger(value[key]) || value[key] <= 0) fail(`invalid ${key}`); if (!path.isAbsolute(value.tempRoot) || path.resolve(value.artifactRoot) !== path.resolve(shaRoot, 'browser')) fail('unsafe runtime roots'); fs.mkdirSync(value.artifactRoot, { recursive: true }); return { ...value, runtimePath, artifactRoot: path.resolve(value.artifactRoot) }; }
function redact(value) {
  if (typeof value === 'string') {
    return value
      .replace(/(authorization|cookie|token|secret|password|api[-_]?key)\s*[:=]\s*[^\s,]+/gi, '$1=[REDACTED]')
      .replace(/[A-Za-z0-9+/_=-]{32,}/g, '[REDACTED]')
      .replace(/[A-Z]:\\(?:Users|Documents and Settings)\\[^\\\s]+/gi, '[USER_PATH]');
  }
  if (Array.isArray(value)) return value.map(redact);
  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value).map(([key, child]) => [
        key,
        /secret|token|password|cookie|authorization|credential|header/i.test(key)
          ? '[REDACTED]'
          : redact(child),
      ]),
    );
  }
  return value;
}
function packageRoot(name, frontendRoot) { return path.join(frontendRoot, 'node_modules', name); }
function packageVersion(name, frontendRoot) { const lock = JSON.parse(fs.readFileSync(path.join(frontendRoot, 'package-lock.json'), 'utf8')); return lock.packages?.[`node_modules/${name}`]?.version; }
function verifyInstallation(name, frontendRoot) { const root = packageRoot(name, frontendRoot); const version = packageVersion(name, frontendRoot); if (version !== REQUIRED[name]) fail(`${name} pin mismatch`); const packageJsonPath = path.join(root, 'package.json'); if (!fs.existsSync(packageJsonPath)) fail(`${name} package entry missing`); const manifest = JSON.parse(fs.readFileSync(packageJsonPath, 'utf8')); if (manifest.version !== REQUIRED[name]) fail(`${name} installed version mismatch`); for (const asset of ASSETS[name]) if (!fs.existsSync(path.join(root, asset))) fail(`${name} installed asset missing`); return { name, version, kind: 'installation-contract', invoked: false, assets: ASSETS[name] }; }
function runDoctor(frontendRoot) { const name = 'react-doctor'; if (packageVersion(name, frontendRoot) !== REQUIRED[name]) fail('react-doctor pin mismatch'); const bin = path.join(frontendRoot, 'node_modules', '.bin', process.platform === 'win32' ? 'react-doctor.cmd' : 'react-doctor'); if (!fs.existsSync(bin)) fail('locked local react-doctor missing'); const env = { PATH: process.env.PATH ?? '', SystemRoot: process.env.SystemRoot ?? process.env.SYSTEMROOT ?? '', TEMP: process.env.TEMP ?? '', TMP: process.env.TMP ?? '', NODE_ENV: 'test', HTTP_PROXY: '', HTTPS_PROXY: '', ALL_PROXY: '', NO_PROXY: '*' }; const result = spawnSync(bin, ['.', '--json', '--no-supply-chain', '--no-score', '--no-telemetry', '--no-color', '--yes', '--blocking', 'error'], { cwd: frontendRoot, encoding: 'utf8', shell: false, timeout: 120000, env }); if (result.error) fail(result.error.code === 'ETIMEDOUT' ? 'react-doctor timed out' : 'react-doctor invocation failed'); let report; try { report = JSON.parse(result.stdout); } catch { fail('react-doctor did not emit valid JSON'); } const blocking = []; const visit = (value, key = '') => { if (Array.isArray(value)) return value.forEach((item) => visit(item, key)); if (!value || typeof value !== 'object') return; const severity = String(value.severity ?? value.level ?? '').toLowerCase(); if (severity === 'error' || severity === 'critical' || severity === 'high' || value.blocking === true) blocking.push({ key, severity }); for (const [childKey, child] of Object.entries(value)) visit(child, childKey); }; visit(report); if (result.status !== 0 || blocking.length) fail('react-doctor reported blocking findings'); return { name, version: REQUIRED[name], kind: 'analysis', invoked: true, status: result.status, blockingFindings: blocking, report: redact(report) }; }
async function run() { const args = parseArgs(process.argv); const runtime = validateRuntime(args.runtime, args.sha); const frontendRoot = path.resolve(path.dirname(runtime.runtimePath), '..', '..', '..', '..', '..', 'frontend'); if (!fs.existsSync(path.join(frontendRoot, 'package-lock.json'))) fail(`frontend root not found: ${frontendRoot}`); const tools = [runDoctor(frontendRoot), verifyInstallation('react-scan', frontendRoot), verifyInstallation('react-grab', frontendRoot)]; fs.writeFileSync(path.join(runtime.artifactRoot, 'react-diagnostics.json'), `${JSON.stringify({ schemaVersion: 1, sha: runtime.sha, tools }, null, 2)}\n`); }
run().catch((error) => { console.error(`react diagnostics failed: ${redact(error.message)}`); process.exitCode = 1; });
export { parseArgs, validateRuntime, redact, runDoctor, verifyInstallation, REQUIRED, ASSETS };
