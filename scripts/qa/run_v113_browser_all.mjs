import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { dirname, resolve, join } from 'node:path';
const repo = resolve(import.meta.dirname, '../..');
const frontend = join(repo, 'frontend');
const sha = (process.argv[process.argv.indexOf('--sha') + 1] || process.env.QA_SHA || '').trim();
if (!/^[a-f0-9]{40}$/.test(sha)) throw new Error('sha must be 40 lowercase hex');
const npmCandidates = [
  process.env.npm_execpath,
  join(dirname(process.execPath), 'node_modules', 'npm', 'bin', 'npm-cli.js'),
].filter(Boolean);
const npmCli = npmCandidates.find(candidate =>
  existsSync(candidate)
  && resolve(candidate).replaceAll('\\', '/').endsWith('/node_modules/npm/bin/npm-cli.js')
);
if (!npmCli) throw new Error('local npm CLI is unavailable');
const allowedEnv = ['PATH', 'Path', 'SYSTEMROOT', 'SystemRoot', 'WINDIR', 'TEMP', 'TMP', 'COMSPEC', 'PATHEXT', 'NUMBER_OF_PROCESSORS'];
const qaEnv = Object.fromEntries(allowedEnv.filter(key => process.env[key] !== undefined).map(key => [key, process.env[key]]));
qaEnv.QA_SHA = sha;
const run = (script, passSha = false) => new Promise((resolveRun, reject) => {
  const args = ['run', script];
  if (passSha) args.push('--', '--sha', sha);
  const p = spawn(process.execPath, [npmCli, ...args], { cwd: frontend, env: qaEnv, shell: false, windowsHide: true, stdio: 'inherit' });
  p.once('error', reject); p.once('close', code => resolveRun(code ?? 1));
});
let runnerCode = 0; let teardownCode = 1;
try {
  for (const script of ['qa:browser:setup', 'qa:browser:smoke', 'qa:browser:matrix', 'qa:browser:axe', 'qa:browser:lighthouse', 'qa:browser:react']) {
    runnerCode = await run(script, script === 'qa:browser:lighthouse' || script === 'qa:browser:react');
    if (runnerCode !== 0) break;
  }
} catch { runnerCode = 1; }
finally {
  try { teardownCode = await run('qa:browser:teardown', true); } catch { teardownCode = 1; }
}
if (runnerCode !== 0) process.exitCode = runnerCode;
else if (teardownCode !== 0) process.exitCode = teardownCode;
