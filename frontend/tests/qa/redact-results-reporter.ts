import fs from 'node:fs';

import type { Reporter } from '@playwright/test/reporter';

type Options = {
  file: string;
  roots: string[];
};

/**
 * Post-processes the Playwright JSON receipt so persisted evidence never leaks
 * operator-local absolute paths. The built-in JSON reporter writes during
 * onEnd; onExit runs after every reporter's onEnd, so the file is complete
 * when this reporter rewrites it. Redaction failure is fail-closed: the raw
 * receipt is deleted rather than left behind unredacted.
 */
class RedactResultsReporter implements Reporter {
  private readonly options: Options;

  constructor(options: Options) {
    if (!options || typeof options.file !== 'string' || !Array.isArray(options.roots)) {
      throw new Error('redact-results-reporter requires { file, roots }');
    }
    this.options = options;
  }

  printsToStdio(): boolean {
    return false;
  }

  async onExit(): Promise<void> {
    const { file, roots } = this.options;
    if (!fs.existsSync(file)) return;
    try {
      let text = fs.readFileSync(file, 'utf8');
      for (const root of roots) {
        if (!root) continue;
        const variants = new Set<string>([
          root,
          root.replaceAll('\\', '/'),
          JSON.stringify(root).slice(1, -1),
          JSON.stringify(root.replaceAll('\\', '/')).slice(1, -1),
        ]);
        for (const variant of variants) {
          text = text.split(variant).join('[REPO_ROOT]');
        }
      }
      text = text
        .replace(/[A-Z]:\\\\(?:Users|Documents and Settings)\\\\[^\\"\s]+/g, '[USER_PATH]')
        .replace(/[A-Z]:\/(?:Users|Documents and Settings)\/[^/"\s]+/g, '[USER_PATH]');
      fs.writeFileSync(file, text, 'utf8');
    } catch {
      fs.rmSync(file, { force: true });
      throw new Error('failed to redact Playwright receipt; raw receipt removed');
    }
  }
}

export default RedactResultsReporter;
