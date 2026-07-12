#!/usr/bin/env node
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';

const VERSION = 'v1.13.0';
const REPO_ROOT = path.resolve(import.meta.dirname, '../..');
const PYTHON = path.join(REPO_ROOT, 'backend', '.venv', 'Scripts', 'python.exe');
const BACKEND_CWD = path.join(REPO_ROOT, 'backend');
const GATES = {
  backend: { args: ['-m', 'pytest', 'tests', '-q'], timeoutMs: 3 * 60 * 60 * 1000 },
  package: {
    args: [
      '-m', 'pytest',
      'tests/unit/test_package_policy_verifier.py',
      'tests/unit/test_offline_package_builder.py',
      'tests/unit/test_internal_data_bundle.py',
      '-q',
    ],
    timeoutMs: 30 * 60 * 1000,
  },
  'migration-heads': { args: ['-m', 'alembic', 'heads'], timeoutMs: 5 * 60 * 1000 },
  migration: {
    args: [
      '-m', 'pytest',
      'tests/integration/test_credential_rotation_migration.py',
      'tests/unit/test_ensure_db_state.py',
      '-q',
    ],
    timeoutMs: 30 * 60 * 1000,
  },
};

function fail(message) {
  process.stderr.write(`backend gates failed: ${message}\n`);
  process.exit(1);
}

function git(...args) {
  const result = spawnSync('git.exe', args, { cwd: REPO_ROOT, encoding: 'utf8', shell: false });
  if (result.status !== 0) fail(`git ${args.join(' ')} exited ${result.status}`);
  return result.stdout.trim();
}

function redact(text) {
  let out = String(text);
  for (const variant of [REPO_ROOT, REPO_ROOT.replaceAll('\\', '/')]) {
    out = out.split(variant).join('[REPO_ROOT]');
  }
  return out
    .replace(/[A-Z]:\\(?:Users|Documents and Settings)\\[^\\\s"']+/gi, '[USER_PATH]')
    .replace(/[A-Z]:\/(?:Users|Documents and Settings)\/[^/\s"']+/gi, '[USER_PATH]');
}

const shaIndex = process.argv.indexOf('--sha');
const sha = (shaIndex >= 0 ? process.argv[shaIndex + 1] : process.env.QA_SHA || '').trim();
if (!/^[a-f0-9]{40}$/.test(sha)) fail('--sha must be the exact 40-character lowercase revision');

const suiteIndex = process.argv.indexOf('--suite');
const suite = suiteIndex >= 0 ? process.argv[suiteIndex + 1] : 'all';
const selected = suite === 'all'
  ? ['backend', 'package', 'migration-heads', 'migration']
  : suite.split(',').map((name) => name.trim()).filter(Boolean);
for (const name of selected) if (!GATES[name]) fail(`unknown gate: ${name}`);

if (!fs.existsSync(PYTHON)) fail(`backend interpreter missing: ${PYTHON}`);
const head = git('rev-parse', 'HEAD');
if (head !== sha) fail(`working tree HEAD ${head} does not match --sha ${sha}`);
const dirty = git('status', '--porcelain');
if (dirty !== '') fail('working tree must be clean so the receipt binds to the exact revision');

const gatesRoot = path.join(REPO_ROOT, 'artifacts', 'qa', VERSION, sha, 'gates');
fs.mkdirSync(gatesRoot, { recursive: true });

let anyFailed = false;
for (const name of selected) {
  const gate = GATES[name];
  const startedAt = new Date().toISOString();
  const result = spawnSync(PYTHON, gate.args, {
    cwd: BACKEND_CWD,
    encoding: 'utf8',
    shell: false,
    timeout: gate.timeoutMs,
    maxBuffer: 64 * 1024 * 1024,
  });
  const finishedAt = new Date().toISOString();
  const exitCode = result.error ? 1 : (result.status ?? 1);
  const receipt = {
    schemaVersion: 1,
    sha,
    gate: name,
    command: `[REPO_ROOT]/backend/.venv/Scripts/python.exe ${gate.args.join(' ')}`,
    cwd: '[REPO_ROOT]/backend',
    startedAt,
    finishedAt,
    exitCode,
    timedOut: result.error?.code === 'ETIMEDOUT' || false,
    generator: 'scripts/qa/run_v113_backend_gates.mjs',
  };
  fs.writeFileSync(path.join(gatesRoot, `${name}.stdout.log`), redact(result.stdout ?? ''), 'utf8');
  fs.writeFileSync(path.join(gatesRoot, `${name}.stderr.log`), redact(result.stderr ?? ''), 'utf8');
  fs.writeFileSync(path.join(gatesRoot, `${name}.receipt.json`), `${JSON.stringify(receipt, null, 2)}\n`, 'utf8');
  process.stdout.write(`${name}: exit ${exitCode}\n`);
  if (exitCode !== 0) anyFailed = true;
}

process.exitCode = anyFailed ? 1 : 0;
