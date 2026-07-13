import { access, cp, mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { closeSync, openSync } from 'node:fs';
import { createServer } from 'node:net';
import { join, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { spawn } from 'node:child_process';
import { randomBytes } from 'node:crypto';
const repo = resolve(import.meta.dirname, '../..'); const sha = (process.argv[process.argv.indexOf('--sha') + 1] || process.env.QA_SHA || '').trim();
if (!/^[a-f0-9]{40}$/.test(sha)) throw new Error('sha must be 40 lowercase hex');
const artifactRoot = resolve(repo, 'artifacts/qa/v1.13.0', sha, 'browser'); const runtimeDir = resolve(repo, 'artifacts/qa/v1.13.0', sha, 'runtime'); const runtimePath = join(runtimeDir, 'runtime.json');
const backendCwd = join(repo, 'backend'); const frontendCwd = join(repo, 'frontend'); const py = join(backendCwd, '.venv', 'Scripts', 'python.exe'); const next = join(frontendCwd, 'node_modules', 'next', 'dist', 'bin', 'next');
const reservePort = () => new Promise((ok, bad) => {
 const server = createServer();
 server.once('error', bad);
 server.listen(0, '127.0.0.1', () => {
  const address = server.address();
  if (!address || typeof address === 'string') {
   server.close();
   bad(new Error('failed to reserve loopback port'));
   return;
  }
  let released = false;
  ok({
   port: address.port,
   release: () => new Promise((releaseOk, releaseBad) => {
    if (released) { releaseOk(); return; }
    released = true;
    server.close(error => error ? releaseBad(error) : releaseOk());
   }),
  });
 });
});
const run = (cmd, args, cwd, env) => new Promise((ok, bad) => { const p = spawn(cmd, args, { cwd, env, shell: false, windowsHide: true }); let out = ''; p.stdout.on('data', d => { out += d; }); p.stderr.on('data', d => { out += d; }); p.once('error', bad); p.once('close', c => c === 0 ? ok(out) : bad(new Error(`${cmd} failed (${c}): ${out.slice(-1000)}`))); });
const killTree = pid => new Promise(ok => { if (!pid) return ok(); const p = spawn('taskkill.exe', ['/PID', String(pid), '/T', '/F'], { shell: false, windowsHide: true }); p.once('close', () => ok()); p.once('error', () => ok()); });
let tempRoot; let backendPid; let frontendPid; let backendProcess; let frontendProcess; let backendReservation; let frontendReservation; const fds = [];
try {
 for (const [p, label] of [[py, 'backend Python'], [next, 'frontend Next'], [join(frontendCwd, '.next', 'BUILD_ID'), 'frontend production build']]) await access(p).catch(() => { throw new Error(`missing ${label}: ${p}`); });
 await mkdir(artifactRoot, { recursive: true }); await mkdir(runtimeDir, { recursive: true }); await rm(runtimePath, { force: true }); tempRoot = await mkdtemp(join(tmpdir(), `aeroone-v113-${sha}-`));
 const isolatedBackend = join(tempRoot, 'backend');
 await cp(join(backendCwd, 'app'), join(isolatedBackend, 'app'), { recursive: true });
 await mkdir(join(tempRoot, 'scripts', 'windows'), { recursive: true });
 await cp(join(repo, 'scripts', 'windows', 'hold_maintenance_gate.ps1'), join(tempRoot, 'scripts', 'windows', 'hold_maintenance_gate.ps1'));
 await cp(join(repo, 'scripts', 'credential_rotation'), join(tempRoot, 'scripts', 'credential_rotation'), { recursive: true });
 const dbPath = join(tempRoot, 'data', 'aeroone.db'); const roots = { storage: join(tempRoot, 'storage'), import: join(tempRoot, 'newsletter'), document: join(tempRoot, 'document'), civil: join(tempRoot, 'civil'), nsa: join(tempRoot, 'nsa') }; for (const p of [join(tempRoot, 'data'), ...Object.values(roots)]) await mkdir(p, { recursive: true });
 const fixture = join(tempRoot, 'fixtures.py'); await writeFile(fixture, `from app.core.config import Settings\nfrom app.core.security import hash_password\nfrom app.db.session import Database\nfrom app.modules.auth.repositories import UserRepository\nfrom app.modules.admin.models import UserPermission\ns=Settings(); d=Database(s.database_url)\nwith d.session() as x:\n r=UserRepository(x)\n for u,p,role in [('qa-normal','QA-normal-v1130-strong!','user'),('qa-nsa','QA-nsa-v1130-strong!','user'),('qa-admin','QA-admin-v1130-strong!','admin'),('qa-pending','QA-pending-v1130-strong!','pending')]:\n  z=r.get_by_username(u) or r.create(username=u,password_hash=hash_password(p),role=role); z.role=role\n  if u=='qa-nsa' and not x.get(UserPermission,(z.id,'collections.nsa.read')): x.add(UserPermission(user_id=z.id,permission_key='collections.nsa.read'))\n`, 'utf8');
 const backendPort = backendReservation = await reservePort(); const frontendPort = frontendReservation = await reservePort(); const bp = backendPort.port; const fp = frontendPort.port; const allow = ['PATH','Path','SYSTEMROOT','SystemRoot','WINDIR','TEMP','TMP','COMSPEC','PATHEXT','NUMBER_OF_PROCESSORS']; const env = Object.fromEntries(allow.filter(k => process.env[k] !== undefined).map(k => [k, process.env[k]])); Object.assign(env, { APP_ENV:'closed_network', APP_VERSION:'1.13.0', BACKEND_PORT:String(bp), FRONTEND_PORT:String(fp), DATABASE_URL:`sqlite:///${dbPath.replaceAll('\\','/')}`, JWT_SECRET_KEY:randomBytes(48).toString('base64url'), ADMIN_USERNAME:'qa-admin', ADMIN_PASSWORD:'QA-admin-v1130-strong!', CORS_ORIGINS:`http://127.0.0.1:${fp}`, NEXT_PUBLIC_API_BASE_URL:`http://127.0.0.1:${bp}`, SERVER_API_BASE_URL:`http://127.0.0.1:${bp}`, STORAGE_ROOT:roots.storage, NEWSLETTER_IMPORT_ROOT_CONTAINER:roots.import, DOCUMENT_ROOT:roots.document, CIVIL_AIRCRAFT_ROOT:roots.civil, NSA_ROOT:roots.nsa, PYTHONPATH:backendCwd, ACCESS_TOKEN_TTL_MINUTES:'30', SESSION_ACTIVITY_DEBOUNCE_SECONDS:'60', CONNECTED_USER_RETENTION_DAYS:'30', ADMIN_SESSION_COOKIE_NAME:'admin_session', CSRF_COOKIE_NAME:'csrf_token', AI_FEATURES_ENABLED:'false', AI_PERSISTENCE_ENABLED:'false', OLLAMA_BASE_URL:'http://127.0.0.1:1', OLLAMA_DEFAULT_MODEL:'synthetic', OLLAMA_CONNECT_TIMEOUT_SECONDS:'1', OLLAMA_READ_TIMEOUT_SECONDS:'1', AI_MAX_CONTEXT_CHARS:'12000' });
 env.PYTHONPATH = isolatedBackend;
 const alembic = join(tempRoot, 'alembic.ini');
 const baseAlembic = await readFile(join(backendCwd, 'alembic.ini'), 'utf8');
 const isolatedAlembic = baseAlembic
   .replace(/^script_location\s*=.*$/m, `script_location = ${join(backendCwd, 'alembic').replaceAll('\\', '/')}`)
   .replace(/^sqlalchemy\.url\s*=.*$/m, `sqlalchemy.url = ${env.DATABASE_URL}`);
 if (isolatedAlembic === baseAlembic) throw new Error('failed to isolate Alembic configuration');
 await writeFile(alembic, isolatedAlembic, 'utf8');
 await run(py, ['-m', 'alembic', '-c', alembic, 'upgrade', 'head'], tempRoot, env);
 await run(py, [join(backendCwd, 'scripts', 'seed.py')], tempRoot, env);
 await run(py, [fixture], tempRoot, env);
 await Promise.all([backendPort.release(), frontendPort.release()]); backendReservation = undefined; frontendReservation = undefined;
 const start = (cmd,args,cwd,log) => { const fd=openSync(log,'a'); fds.push(fd); const p=spawn(cmd,args,{cwd,env,shell:false,windowsHide:true,detached:true,stdio:['ignore',fd,fd]}); p.unref(); return p; };
 const childFailure = (label, child) => new Promise((_, rejectChild) => {
  child.once('error', error => rejectChild(new Error(`${label} spawn failed: ${error.message}`)));
  child.once('exit', (code, signal) => rejectChild(new Error(`${label} exited before readiness (code=${code}, signal=${signal ?? 'none'})`)));
 });
 backendProcess=start(py,['-m','uvicorn','app.main:app','--host','127.0.0.1','--port',String(bp)],tempRoot,join(artifactRoot,'backend.log')); backendPid=backendProcess.pid;
 frontendProcess=start(process.execPath,[next,'start','-H','127.0.0.1','-p',String(fp)],frontendCwd,join(artifactRoot,'frontend.log')); frontendPid=frontendProcess.pid;
 await writeFile(runtimePath,JSON.stringify({schemaVersion:1,sha,backendUrl:`http://127.0.0.1:${bp}`,frontendUrl:`http://127.0.0.1:${fp}`,backendPid,frontendPid,tempRoot,artifactRoot},null,2)+'\n',{mode:0o600});
 const readyEnv=Object.fromEntries(allow.filter(k => process.env[k] !== undefined).map(k => [k, process.env[k]]));
 await Promise.race([
  run(process.execPath,[join(import.meta.dirname,'wait_v113_ready.mjs'),'--sha',sha],repo,readyEnv),
  childFailure('backend', backendProcess),
  childFailure('frontend', frontendProcess),
 ]);
 process.stdout.write('runtime ready\n');
} catch (error) {
 const cleanupErrors = [];
 try { await backendReservation?.release(); } catch (cleanupError) { cleanupErrors.push(cleanupError.message); }
 try { await frontendReservation?.release(); } catch (cleanupError) { cleanupErrors.push(cleanupError.message); }
 await killTree(frontendPid);
 await killTree(backendPid);
 for (const fd of fds) {
   try { closeSync(fd); } catch (closeError) { cleanupErrors.push(closeError.message); }
 }
 if (tempRoot) {
   for (let attempt = 1; attempt <= 5; attempt += 1) {
     try {
       await rm(tempRoot, { recursive: true, force: true });
       break;
     } catch (cleanupError) {
       if (attempt === 5) cleanupErrors.push(cleanupError.message);
       else await new Promise(resolveDelay => setTimeout(resolveDelay, attempt * 250));
     }
   }
 }
 try { await rm(runtimePath, { force: true }); } catch (cleanupError) { cleanupErrors.push(cleanupError.message); }
 const cleanupSuffix = cleanupErrors.length ? `; cleanup: ${cleanupErrors.join('; ')}` : '';
 process.stderr.write(`prepare failed: ${error.message}${cleanupSuffix}\n`);
 process.exitCode = 1;
}
