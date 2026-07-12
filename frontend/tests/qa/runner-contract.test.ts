import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

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
    expect(lighthouse).toContain("await import('chrome-launcher')");
    expect(lighthouse).not.toContain('port: 0');
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
    expect(diagnostics).toContain("bin', 'react-doctor.js");
  });

  it('requires the exact runtime schema and loopback/SHA/root validation', () => {
    for (const source of [lighthouse, diagnostics]) {
      expect(source).toContain("schemaVersion', 'sha', 'backendUrl', 'frontendUrl', 'backendPid', 'frontendPid', 'tempRoot', 'artifactRoot");
      expect(source).toContain('runtime schema keys mismatch');
      expect(source).toContain('loopback-only');
      expect(source).toContain('SHA mismatch');
      expect(source).toContain("artifactRoot");
      expect(source).toMatch(/path\.resolve\([^)]*, 'browser'\)/);
      expect(source).toMatch(/path\.resolve\([^)]*, 'browser'\)/);
    }
  });

  it('uses local locked tools and forbids latest/download/CDN fallbacks', () => {
    expect(diagnostics).toContain("'react-doctor': '0.7.3'");
    expect(diagnostics).toContain("'react-scan': '0.5.7'");
    expect(diagnostics).toContain("bin', 'react-doctor.js");
    for (const source of [lighthouse, diagnostics]) {
      expect(source).not.toMatch(/npx\s+[^\n]*@latest|chromium\.download|https?:\/\/(?!127\.0\.0\.1|localhost)/i);
      expect(source).toContain('process.exitCode = 1');
      expect(source).toContain('[REDACTED]');
      expect(source).toContain('artifactRoot');
    }
  });

  it('runs only structured doctor analysis and installation contracts for scan/grab', () => {
    expect(diagnostics).toContain("'react-grab': '0.1.48'");
    expect(diagnostics).toContain("kind: 'analysis'");
    expect(diagnostics).toContain("kind: 'installation-contract'");
    expect(diagnostics).toContain("'--json', '--no-supply-chain', '--no-score', '--no-telemetry', '--no-color', '--yes', '--blocking', 'error'");
    expect(diagnostics).toContain('JSON.parse(result.stdout)');
    expect(diagnostics).toContain('timeout: 120000');
    expect(diagnostics).toContain("HTTP_PROXY: ''");
    expect(diagnostics).not.toContain("name === 'react-scan' ? ['--project', '.']");
    expect(diagnostics).not.toContain('react-scan reported unnecessary renders');
    expect(diagnostics).toMatch(/result\.status !== 0/);
  });
});
