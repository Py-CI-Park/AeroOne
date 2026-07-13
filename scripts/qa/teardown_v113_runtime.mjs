import { readdir, readFile, rm, writeFile } from 'node:fs/promises';
import { redact } from './redact_v113.mjs';
import { resolve, join, relative } from 'node:path';
import { tmpdir } from 'node:os';
import { spawn } from 'node:child_process';

const repo = resolve(import.meta.dirname, '../..');
const sha = (process.argv[process.argv.indexOf('--sha') + 1] || '').trim();
if (!/^[a-f0-9]{40}$/.test(sha)) throw new Error('sha must be 40 lowercase hex');
const runtimePath = join(repo, 'artifacts/qa/v1.13.0', sha, 'runtime', 'runtime.json');
const artifactRoot = join(repo, 'artifacts/qa/v1.13.0', sha, 'browser');
const runtimeKeys = ['schemaVersion', 'sha', 'backendUrl', 'frontendUrl', 'backendPid', 'frontendPid', 'tempRoot', 'artifactRoot'];

const runCommand = (command, args) => new Promise(resolveCommand => {
  const child = spawn(command, args, { shell: false, windowsHide: true });
  let stdout = '';
  child.stdout.on('data', chunk => { stdout += chunk; });
  child.once('close', code => resolveCommand({ code: code ?? 1, stdout }));
  child.once('error', () => resolveCommand({ code: 1, stdout }));
});
const processInfo = pid => runCommand('wmic.exe', ['process', 'where', `ProcessId=${pid}`, 'get', 'CommandLine', '/value']);
const commandLine = async pid => (await processInfo(pid)).stdout;
const isAlive = async pid => (await commandLine(pid)).includes('CommandLine=');
const hasListener = async port => (
  await runCommand('netstat.exe', ['-ano', '-p', 'TCP'])
).stdout.split(/\r?\n/).some(line => line.includes(`127.0.0.1:${port}`) && /LISTENING/i.test(line));
const sleep = milliseconds => new Promise(resolveDelay => setTimeout(resolveDelay, milliseconds));

function validateRuntime(runtime) {
  if (
    !runtime
    || typeof runtime !== 'object'
    || Object.keys(runtime).sort().join() !== runtimeKeys.slice().sort().join()
    || runtime.schemaVersion !== 1
    || runtime.sha !== sha
    || ![runtime.backendPid, runtime.frontendPid].every(Number.isInteger)
    || runtime.backendPid <= 0
    || runtime.frontendPid <= 0
  ) throw new Error('invalid runtime schema');
  const loopback = value => /^http:\/\/127\.0\.0\.1:\d+$/.test(value);
  if (!loopback(runtime.backendUrl) || !loopback(runtime.frontendUrl)) throw new Error('non-loopback URL');
  const expectedArtifactRoot = resolve(repo, 'artifacts/qa/v1.13.0', sha, 'browser');
  if (resolve(runtime.artifactRoot) !== expectedArtifactRoot) throw new Error('artifactRoot not owned');
  const tempRoot = resolve(runtime.tempRoot);
  const tempRelative = relative(resolve(tmpdir()), tempRoot);
  const tempPattern = new RegExp(`^aeroone-v113-${sha}-[A-Za-z0-9]{6}$`);
  if (!tempPattern.test(tempRelative) || /[\\/]/.test(tempRelative)) throw new Error('tempRoot not owned');
  return { ...runtime, tempRoot };
}

function ownsBackend(command, port) {
  return command.includes('uvicorn')
    && command.includes('app.main:app')
    && command.includes(`--port ${port}`);
}
function ownsFrontend(command, port) {
  return command.toLowerCase().includes('next')
    && command.includes('start')
    && command.includes(`-p ${port}`);
}

async function removeOwnedTemp(tempRoot) {
  let lastError;
  for (let attempt = 1; attempt <= 5; attempt += 1) {
    try {
      await rm(tempRoot, { recursive: true, force: false });
      return;
    } catch (error) {
      lastError = error;
      if (attempt < 5) await sleep(attempt * 250);
    }
  }
  throw lastError;
}

function redactText(text, runtime) {
  return redact(text, { replacements: [[repo, '[REPO_ROOT]'], [runtime.tempRoot, '[TEMP_ROOT]'], ['QA-admin-v1130-strong!', '[REDACTED]']] });
}

async function redactRuntimeLogs(runtime) {
  for (const name of ['backend.log', 'frontend.log']) {
    const logPath = join(runtime.artifactRoot, name);
    let source;
    try {
      source = await readFile(logPath, 'utf8');
    } catch (error) {
      if (error.code === 'ENOENT') continue;
      throw error;
    }
    const redacted = redactText(source, runtime);
    if (
      redacted.includes(repo)
      || redacted.includes(repo.replaceAll('\\', '/'))
      || redacted.includes(runtime.tempRoot)
      || redacted.includes(runtime.tempRoot.replaceAll('\\', '/'))
    ) throw new Error(`${name} redaction failed`);
    await writeFile(logPath, redacted, 'utf8');
  }
}

let failed = false;
try {
  let runtime;
  try {
    runtime = validateRuntime(JSON.parse(await readFile(runtimePath, 'utf8')));
  } catch (error) {
    if (error.code !== 'ENOENT') throw error;
    const ownedTempExists = (await readdir(tmpdir(), { withFileTypes: true }))
      .some(entry => entry.isDirectory() && entry.name.startsWith(`aeroone-v113-${sha}-`));
    if (ownedTempExists) throw new Error('runtime missing but owned temp exists');
    process.stdout.write('nothing to teardown\n');
    process.exit(0);
  }

  const backendPort = Number(new URL(runtime.backendUrl).port);
  const frontendPort = Number(new URL(runtime.frontendUrl).port);
  const backendCommand = await commandLine(runtime.backendPid);
  const frontendCommand = await commandLine(runtime.frontendPid);
  const backendAlive = backendCommand.includes('CommandLine=');
  const frontendAlive = frontendCommand.includes('CommandLine=');
  if (backendAlive && !ownsBackend(backendCommand, backendPort)) throw new Error('backend PID command ownership failed');
  if (frontendAlive && !ownsFrontend(frontendCommand, frontendPort)) throw new Error('frontend PID command ownership failed');

  const unexpectedExit = !backendAlive || !frontendAlive;
  for (const pid of [runtime.frontendPid, runtime.backendPid]) {
    if (!(await isAlive(pid))) continue;
    const result = await runCommand('taskkill.exe', ['/PID', String(pid), '/T', '/F']);
    if (result.code !== 0 && await isAlive(pid)) throw new Error(`taskkill failed for ${pid}`);
  }

  const deadline = Date.now() + 15_000;
  while (
    Date.now() < deadline
    && (await isAlive(runtime.backendPid) || await isAlive(runtime.frontendPid))
  ) await sleep(250);
  if (
    await isAlive(runtime.backendPid)
    || await isAlive(runtime.frontendPid)
    || await hasListener(backendPort)
    || await hasListener(frontendPort)
  ) throw new Error('owned process/listener remains');

  await redactRuntimeLogs(runtime);
  await removeOwnedTemp(runtime.tempRoot);
  await rm(runtimePath, { force: false });
  if (unexpectedExit) throw new Error('owned process exited before teardown');
} catch (error) {
  failed = true;
  process.stderr.write(`teardown failed: ${error.message}\n`);
}
process.exitCode = failed ? 1 : 0;
