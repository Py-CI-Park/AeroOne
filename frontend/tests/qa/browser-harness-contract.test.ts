import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

type Manifest = {
  scripts: Record<string, string>;
  dependencies: Record<string, string>;
  devDependencies: Record<string, string>;
};

const frontendRoot = path.resolve(__dirname, '../..');
const manifest = JSON.parse(fs.readFileSync(path.join(frontendRoot, 'package.json'), 'utf8')) as Manifest;
const lock = JSON.parse(fs.readFileSync(path.join(frontendRoot, 'package-lock.json'), 'utf8')) as {
  packages: Record<string, { version?: string; devDependencies?: Record<string, string> }>;
};
const config = fs.readFileSync(path.join(frontendRoot, 'playwright.qa.config.ts'), 'utf8');
const spec = fs.readFileSync(path.join(frontendRoot, 'tests/qa/v113-browser.e2e.ts'), 'utf8');
const setup = fs.readFileSync(path.join(frontendRoot, '../scripts/qa/prepare_v113_runtime.mjs'), 'utf8');

const qaDependencies = {
  '@playwright/test': '1.61.1',
  '@axe-core/playwright': '4.12.1',
  lighthouse: '12.8.2',
  'playwright-lighthouse': '4.0.0',
  'react-grab': '0.1.48',
  'react-scan': '0.5.7',
  'react-doctor': '0.7.3',
};

const qaScripts = {
  'qa:browser:setup': 'node ../scripts/qa/prepare_v113_runtime.mjs',
  'qa:browser:smoke': 'npx --no-install playwright test --config=playwright.qa.config.ts --project=smoke',
  'qa:browser:matrix': 'npx --no-install playwright test --config=playwright.qa.config.ts --project=matrix',
  'qa:browser:axe': 'npx --no-install playwright test --config=playwright.qa.config.ts --project=axe',
  'qa:browser:lighthouse': 'node ../scripts/qa/run_v113_lighthouse.mjs',
  'qa:browser:react': 'node ../scripts/qa/run_v113_react_diagnostics.mjs',
  'qa:browser:teardown': 'node ../scripts/qa/teardown_v113_runtime.mjs',
  'qa:browser:all': 'node ../scripts/qa/run_v113_browser_all.mjs',
};

describe('browser harness contract', () => {
  it('pins QA dependencies and scripts exactly', () => {
    expect(manifest.dependencies.next).toBe('15.2.9');
    expect(manifest.devDependencies).toMatchObject(qaDependencies);
    expect(manifest.scripts).toMatchObject(qaScripts);
    expect(lock.packages[''].devDependencies).toMatchObject(qaDependencies);
    for (const [name, version] of Object.entries(qaDependencies)) {
      expect(lock.packages[`node_modules/${name}`]?.version).toBe(version);
    }
  });

  it('keeps browser execution on installed Chrome and redacted loopback artifacts', () => {
    expect(config).toContain("C:\\\\Program Files\\\\Google\\\\Chrome\\\\Application\\\\chrome.exe");
    expect(config).toContain("'..'");
    expect(config).toContain("'artifacts'");
    expect(config).toContain("'qa'");
    expect(config).toContain("'v1.13.0'");
    expect(config).toContain("expectedArtifactRoot");
    expect(config).toContain("Object.keys(runtime)");
    expect(config).toContain("runtime.backendPid <= 0");
    expect(config).toContain("path.isAbsolute(runtime.tempRoot)");
    expect(config).toContain("outputDir: path.join(artifactRoot, 'playwright', projectLabel)");
    expect(config).toContain("results-${projectLabel}.json");
    expect(config).toContain("'./tests/qa/redact-results-reporter.ts'");
    expect(fs.existsSync(path.join(frontendRoot, 'tests/qa/redact-results-reporter.ts'))).toBe(true);
    expect(config).toContain("screenshot: 'on'");
    expect(config).toContain("runtime.frontendUrl");
    expect(config).toContain("['localhost', '127.0.0.1', '::1']");
    expect(config).toMatch(/name: 'smoke'/);
    expect(config).toMatch(/name: 'matrix'/);
    expect(config).toMatch(/name: 'axe'/);
    expect(config).not.toMatch(/playwright\s+install/);
    expect(config).not.toMatch(/https?:\/\/(?!localhost)/);
    expect(config).toMatch(/testMatch:\s*\/v113-browser\\\.e2e\\\.ts\//);
    expect(config).toMatch(/grep:\s*\/@smoke\//);
    expect(config).toMatch(/grep:\s*\/@matrix\//);
    expect(config).toMatch(/grep:\s*\/@axe\//);
    expect(spec).toMatch(/requestfailed/);
    expect(spec).toContain("QA-admin-v1130-strong!");
    expect(spec).toMatch(/hostname/);
    expect(spec).toMatch(/localhost.*127\.0\.0\.1.*::1/);
    expect(fs.existsSync(path.join(frontendRoot, 'tests/qa/v113-browser.e2e.ts'))).toBe(true);
    expect(setup).toContain('const reservePort');
    expect(setup).toContain("const isolatedBackend = join(tempRoot, 'backend')");
    expect(setup).toContain("hold_maintenance_gate.ps1");
    expect(setup).toContain("APP_ENV:'closed_network'");
    expect(setup).toContain('env.PYTHONPATH = isolatedBackend');
    expect(setup).toContain("childFailure('backend', backendProcess)");
  });
});
