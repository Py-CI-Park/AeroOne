import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { describe, expect, it } from 'vitest';
import { deterministicBuildId } from '../../next.config';

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
const teardown = fs.readFileSync(path.join(frontendRoot, '../scripts/qa/teardown_v113_runtime.mjs'), 'utf8');

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
    expect(setup).toContain('frontend BUILD_ID does not match --sha');
    expect(fs.readFileSync(path.join(frontendRoot, 'next.config.ts'), 'utf8')).toContain('generateBuildId');
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
    expect(setup).toContain("gitCheck(['rev-parse', 'HEAD']");
    expect(setup).toContain("gitCheck(['status', '--porcelain']");
    expect(setup).toContain('git HEAD does not match --sha');
    expect(setup).toContain('git worktree is dirty');
    expect(setup).toContain('shell: false');
    expect(fs.readFileSync(path.join(frontendRoot, '../scripts/build_offline_package.ps1'), 'utf8')).toContain('AEROONE_BUILD_ID');
    expect(teardown).toContain('redactRuntimeLogs(runtime)');
    expect(teardown).toContain("'[REPO_ROOT]'");
    expect(teardown).toContain("'[TEMP_ROOT]'");
    expect(teardown).toContain("['backend.log', 'frontend.log']");
  });

  it('rejects a wrong SHA and invalidates a stale runtime receipt before failing', () => {
    const wrongSha = '0'.repeat(40);
    const staleRoot = path.join(frontendRoot, '..', 'artifacts', 'qa', 'v1.13.0', wrongSha);
    const staleRuntime = path.join(staleRoot, 'runtime', 'runtime.json');
    fs.mkdirSync(path.dirname(staleRuntime), { recursive: true });
    fs.writeFileSync(staleRuntime, '{"stale":true}\n');

    try {
      const result = spawnSync(
        process.execPath,
        [path.join(frontendRoot, '..', 'scripts', 'qa', 'prepare_v113_runtime.mjs'), '--sha', wrongSha],
        {
          cwd: path.join(frontendRoot, '..'),
          encoding: 'utf8',
          shell: false,
          windowsHide: true,
        },
      );
      expect(result.status).not.toBe(0);
      expect(`${result.stdout}${result.stderr}`).toContain('git HEAD does not match --sha');
      expect(fs.existsSync(staleRuntime)).toBe(false);
    } finally {
      fs.rmSync(staleRoot, { recursive: true, force: true });
    }
  });
});
describe('deterministic build provenance', () => {
  it('rejects a dirty worktree even when HEAD is the requested SHA', () => {
    const sha = 'a'.repeat(40);
    const calls: string[][] = [];
    const buildId = () => deterministicBuildId((args) => {
      calls.push(args);
      if (args[0] === 'rev-parse' && args[1] === '--is-inside-work-tree') return 'true\n';
      if (args[0] === 'rev-parse') return `${sha}\n`;
      return ' M frontend/next.config.ts\n';
    });

    expect(buildId).toThrow('git worktree is dirty');
    expect(calls).toContainEqual(['status', '--porcelain']);
  });

  it('uses a clean exact SHA from Git', () => {
    const sha = 'b'.repeat(40);
    const buildId = deterministicBuildId((args) => {
      if (args[0] === 'rev-parse' && args[1] === '--is-inside-work-tree') return 'true\n';
      if (args[0] === 'rev-parse') return `${sha}\n`;
      return '';
    });

    expect(buildId).toBe(sha);
  });

  it('uses the offline fallback when Git metadata is unavailable', () => {
    const previous = process.env.AEROONE_BUILD_ID;
    process.env.AEROONE_BUILD_ID = 'c'.repeat(40);
    try {
      expect(deterministicBuildId(() => { throw new Error('not a worktree'); })).toBe('c'.repeat(40));
    } finally {
      if (previous === undefined) delete process.env.AEROONE_BUILD_ID;
      else process.env.AEROONE_BUILD_ID = previous;
    }
  });
});
