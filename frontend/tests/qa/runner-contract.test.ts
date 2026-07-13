import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';
// The executable QA runner is JavaScript by design; its exported seams are runtime-tested here.
// @ts-expect-error TS7016: no implicit-any MJS import; the seam is validated by behavioral tests below.
import { assertCleanSha, browserRequestGuard, prepareReceiptRun, redact, verifyInstallation } from '../../../scripts/qa/run_v113_react_diagnostics.mjs';
// @ts-expect-error TS7016: shared JavaScript QA seams are runtime-tested below.
import { redactString } from '../../../scripts/qa/redact_v113.mjs';

const root = path.resolve(__dirname, '../../..');
const lighthouse = fs.readFileSync(path.join(root, 'scripts/qa/run_v113_lighthouse.mjs'), 'utf8');
const diagnostics = fs.readFileSync(path.join(root, 'scripts/qa/run_v113_react_diagnostics.mjs'), 'utf8');

describe('v1.13 browser QA runner contract', () => {
  it('fixes the required route, matrix, run, and score constants', () => {
    expect(lighthouse).toContain("const ROUTES = ['/login', '/activity', '/admin'];");
    expect(lighthouse).toContain("const FORM_FACTORS = ['mobile', 'desktop'];");
    expect(lighthouse).toContain('const RUNS = 3;');
    expect(lighthouse).toContain("performance: 100, accessibility: 100, 'best-practices': 100, seo: 100");
    expect(lighthouse).toContain('C:\\\\Program Files\\\\Google\\\\Chrome\\\\Application\\\\chrome.exe');
    expect(lighthouse).toContain("if (argv[i] === '--sha')");
    expect(lighthouse).toContain("chrome.port");
    expect(lighthouse).toContain("await chrome.kill()");
    expect(lighthouse).toContain("await importFrontendPackage('chrome-launcher')");
    expect(lighthouse).not.toContain('port: 0');
    expect(lighthouse).toContain("createRequire(path.join(REPO_ROOT, 'frontend', 'package.json'))");
    expect(lighthouse).toContain("await importFrontendPackage('lighthouse')");
    expect(lighthouse).toContain("const AUTHENTICATED_ROUTES = new Set(['/activity', '/admin']);");
    expect(lighthouse).toContain("const QA_USERNAME = 'qa-admin';");
    expect(lighthouse).toContain("const QA_PASSWORD = 'QA-admin-v1130-strong!';");
    expect(lighthouse).toContain('/api/frontend/auth/login');
    expect(lighthouse).toContain('extraHeaders');
    expect(lighthouse).toContain('sessionCookie');
    expect(lighthouse).toContain('finalDisplayedUrl');
    expect(lighthouse).toContain('--disable-background-networking');
    expect(lighthouse).toContain('--disable-default-apps');
    expect(lighthouse).toContain('sessionCookie = undefined');
    expect(diagnostics).toContain("if (argv[i] === '--sha')");
    expect(diagnostics).toContain('bin/react-doctor.js');
  });

  it('requires the exact runtime schema and loopback/SHA/root validation', () => {
    for (const source of [lighthouse, diagnostics]) {
      expect(source).toContain("schemaVersion', 'sha', 'backendUrl', 'frontendUrl', 'backendPid', 'frontendPid', 'tempRoot', 'artifactRoot");
      expect(source).toContain('runtime schema keys mismatch');
      expect(source).toContain('loopback-only');
      expect(source).toContain('SHA mismatch');
      expect(source).toContain("artifactRoot");
      expect(source).toMatch(/path\.resolve\([^)]*, 'browser'\)/);
    }
  });

  it('uses local locked tools and forbids latest/download/CDN fallbacks', () => {
    expect(diagnostics).toContain("'react-doctor': '0.7.3'");
    expect(diagnostics).toContain("'react-scan': '0.5.7'");
    expect(diagnostics).toContain('bin/react-doctor.js');
    for (const source of [lighthouse, diagnostics]) {
      expect(source).not.toMatch(/npx\s+[^\n]*@latest|chromium\.download|https?:\/\/(?!127\.0\.0\.1|localhost)/i);
      expect(source).toContain('process.exitCode = 1');
      expect(source).toContain('[REDACTED]');
      expect(source).toContain('artifactRoot');
    }
  });

  it('runs locked browser react-scan analysis and requires executable evidence', () => {
    expect(diagnostics).toContain("'react-grab': '0.1.48'");
    expect(diagnostics).toContain("kind: 'analysis'");
    expect(diagnostics).toContain('runReactScan');
    expect(diagnostics).toContain("dist', 'auto.global.js");
    expect(diagnostics).toContain('addInitScript');
    expect(diagnostics).toContain('render/commit evidence');
    expect(diagnostics).toContain('unnecessary renders');
    expect(diagnostics).toContain('locked local browser asset missing');
    expect(diagnostics).toContain("'--json', '--no-supply-chain', '--no-score', '--no-telemetry', '--no-color', '--yes', '--blocking', 'error'");
    expect(diagnostics).toContain('JSON.parse(result.stdout)');
    expect(diagnostics).toContain('timeout: 120000');
    expect(diagnostics).toContain("HTTP_PROXY: 'http://127.0.0.1:9'");
    expect(diagnostics).toContain('react-scan reported unnecessary renders');
    expect(diagnostics).not.toContain("kind: 'installation-contract'");
    expect(diagnostics).not.toContain("name === 'react-scan' ? ['--project', '.']");
    expect(diagnostics).toMatch(/result\.status !== 0/);
  });
  it('fails closed on wrong SHA, dirty trees, and adversarial redaction', () => {
    const clean = (args: string[]) => ({ error: null, status: 0, stdout: args[0] === 'rev-parse' ? `${'a'.repeat(40)}\n` : '' });
    expect(() => assertCleanSha('b'.repeat(40), clean)).toThrow(/SHA/);
    const dirty = (args: string[]) => ({ error: null, status: 0, stdout: args[0] === 'rev-parse' ? `${'a'.repeat(40)}\n` : ' M frontend/next.config.ts\n' });
    expect(() => assertCleanSha('a'.repeat(40), dirty)).toThrow(/dirty/);
    const sensitive = redact({
      Authorization: 'Bearer secret value,with commas',
      nested: 'token: "quoted value with spaces, and commas"',
      path: 'C:\\Users\\qa-user\\Documents\\secret.txt',
    });
    expect(JSON.stringify(sensitive)).not.toMatch(/secret value|quoted value|C:\\\\Users/);
  });

  it('behaviorally rejects installed package drift and non-loopback browser egress', async () => {
    const fixtureRoot = fs.mkdtempSync(path.join(process.env.TEMP ?? process.cwd(), 'aeroone-react-tool-'));
    try {
      const packageRoot = path.join(fixtureRoot, 'node_modules', 'react-scan');
      fs.mkdirSync(path.join(packageRoot, 'bin'), { recursive: true });
      fs.mkdirSync(path.join(packageRoot, 'dist'), { recursive: true });
      fs.writeFileSync(
        path.join(fixtureRoot, 'package-lock.json'),
        JSON.stringify({
          packages: {
            'node_modules/react-scan': { version: '0.5.7' },
          },
        }),
      );
      fs.writeFileSync(path.join(packageRoot, 'package.json'), JSON.stringify({ version: '0.5.6' }));
      fs.writeFileSync(path.join(packageRoot, 'bin', 'cli.js'), '');
      fs.writeFileSync(path.join(packageRoot, 'dist', 'auto.global.js'), '');
      expect(() => verifyInstallation('react-scan', fixtureRoot)).toThrow(/installed version mismatch/);

      fs.writeFileSync(path.join(packageRoot, 'package.json'), JSON.stringify({ version: '0.5.7' }));
      expect(verifyInstallation('react-scan', fixtureRoot).version).toBe('0.5.7');
    } finally {
      fs.rmSync(fixtureRoot, { recursive: true, force: true });
    }

    let routeHandler: ((route: {
      request: () => { url: () => string };
      abort: (reason: string) => unknown;
      continue: () => unknown;
    }) => unknown) | undefined;
    let webSocketHandler: ((socket: {
      url: () => string;
      close: () => unknown;
      connectToServer: () => unknown;
    }) => unknown) | undefined;
    const context = {
      route: vi.fn(async (_pattern: string, handler: typeof routeHandler) => {
        routeHandler = handler;
      }),
      routeWebSocket: vi.fn(async (_pattern: string, handler: typeof webSocketHandler) => {
        webSocketHandler = handler;
      }),
    };
    const violations: string[] = [];
    await browserRequestGuard(context, violations);

    const abort = vi.fn();
    const continueRequest = vi.fn();
    await routeHandler?.({
      request: () => ({ url: () => 'https://example.invalid/tracker.js' }),
      abort,
      continue: continueRequest,
    });
    expect(abort).toHaveBeenCalledWith('blockedbyclient');
    expect(continueRequest).not.toHaveBeenCalled();
    expect(violations).toEqual(['https://example.invalid/tracker.js']);

    await routeHandler?.({
      request: () => ({ url: () => 'http://127.0.0.1:3000/app.js' }),
      abort,
      continue: continueRequest,
    });
    expect(continueRequest).toHaveBeenCalledTimes(1);

    const closeSocket = vi.fn();
    const connectToServer = vi.fn();
    await webSocketHandler?.({
      url: () => 'wss://example.invalid/socket',
      close: closeSocket,
      connectToServer,
    });
    expect(closeSocket).toHaveBeenCalledTimes(1);
    expect(connectToServer).not.toHaveBeenCalled();
    expect(violations).toContain('wss://example.invalid/socket');

    await webSocketHandler?.({
      url: () => 'ws://127.0.0.1:3000/socket',
      close: closeSocket,
      connectToServer,
    });
    expect(connectToServer).toHaveBeenCalledTimes(1);
  });


  it('behaviorally invalidates stale receipts and redacts delimited free text', () => {
    const artifactRoot = fs.mkdtempSync(path.join(process.env.TEMP ?? process.cwd(), 'aeroone-receipt-'));
    const canonical = path.join(artifactRoot, 'react-diagnostics.json');
    const temporary = path.join(artifactRoot, 'react-diagnostics.123.456.tmp');
    fs.writeFileSync(canonical, '{"status":"passed"}');
    fs.writeFileSync(temporary, '{"status":"passed"}');

    try {
      expect(() => prepareReceiptRun(artifactRoot, 'b'.repeat(40), () => ({
        error: null,
        status: 0,
        stdout: `${'a'.repeat(40)}\n`,
      }))).toThrow(/SHA/);
      expect(fs.existsSync(canonical)).toBe(false);
      expect(fs.existsSync(temporary)).toBe(false);
    } finally {
      fs.rmSync(artifactRoot, { recursive: true, force: true });
    }

    const redacted = redactString([
      'authorization: Bearer alpha,beta; suffix',
      'password=alpha beta; cookie=gamma,delta',
      'safe line',
      'token: "quoted value, with spaces"',
    ].join('\n'));
    expect(redacted).toContain('safe line');
    expect(redacted).not.toMatch(/alpha|beta|gamma|delta|quoted value|suffix/);
  });
  it('keeps source-level fail-closed wiring as a secondary contract', () => {
    expect(diagnostics).toContain('prepareReceiptRun(expectedArtifactRoot, args.sha)');
    expect(diagnostics).toContain('fs.renameSync(tempPath, finalPath)');
    expect(diagnostics).toContain('react-scan produced no render/commit evidence');
    expect(diagnostics).toContain('blockedbyclient');
    expect(diagnostics).toContain("serviceWorkers: 'block'");
    expect(diagnostics).toContain('계정 접속');
    expect(diagnostics).toContain('내 활동');
    expect(diagnostics).toContain('관리자 콘솔');
  });
});
