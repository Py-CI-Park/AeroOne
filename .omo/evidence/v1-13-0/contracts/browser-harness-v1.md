# Browser QA Harness v1 Contract

## Producers

- `scripts/qa/run_v113_lighthouse.mjs` — Lighthouse route and score gate.
- `scripts/qa/run_v113_react_diagnostics.mjs` — locked React diagnostics gate.
- `frontend/tests/qa/runner-contract.test.ts` — static contract regression checks.

## Tool versions and host

- Node `22.14.0` only.
- `@playwright/test@1.61.1`, `@axe-core/playwright@4.12.1`, `lighthouse@12.8.2`, `playwright-lighthouse@4.0.0`, `react-grab@0.1.48`, `react-scan@0.5.7`, `react-doctor@0.7.3`.
- Stable Chrome: `C:\Program Files\Google\Chrome\Application\chrome.exe`.
- No bundled browser download, `npx`, `@latest`, CDN, or external network.

## Runtime contract

The runner receives `--runtime artifacts/qa/v1.13.0/<sha>/runtime/runtime.json`. The JSON object has exactly these keys:

```json
{
  "schemaVersion": 1,
  "sha": "<40 lowercase hex characters>",
  "backendUrl": "http://127.0.0.1:<port>",
  "frontendUrl": "http://127.0.0.1:<port>",
  "backendPid": 123,
  "frontendPid": 456,
  "tempRoot": "<absolute owned temporary root>",
  "artifactRoot": "<absolute .../<sha>/browser path>"
}
```

Missing/extra keys, SHA mismatch, nonpositive PIDs, non-loopback URLs, relative roots, and roots outside the SHA-owned artifact root are rejected. Runtime and browser traffic are loopback-only.

## Commands and coverage

```text
node scripts/qa/run_v113_lighthouse.mjs --sha <40hex>
node scripts/qa/run_v113_react_diagnostics.mjs --sha <40hex>
```

Lighthouse keeps `/login` anonymous, authenticates synthetic `qa-admin` through loopback `/api/frontend/auth/login` using the fixture password in memory, and passes only the two session-cookie pairs to `/activity` and `/admin`. It asserts each final audited path equals the requested path, so redirects fail closed. Chrome is launched through local `chrome-launcher` with background networking/default services disabled, and only the owned launcher is killed during cleanup. Coverage is mobile and desktop, three times each; every median of performance, accessibility, best-practices, and SEO must be exactly 100. React diagnostics runs only non-mutating structured `react-doctor@0.7.3` analysis with `. --json --no-supply-chain --no-score --no-telemetry --no-color --yes --blocking error`, with a bounded timeout and minimal offline environment. `react-scan@0.5.7` and `react-grab@0.1.48` are never invoked: their exact lock/package versions and required local entrypoint/bundle assets are recorded as `installation-contract` checks only. No scan/grab runtime findings are claimed.

## Artifacts and redaction

Machine-readable outputs are written only below `artifacts/qa/v1.13.0/<sha>/browser/`:

- `lighthouse.json`
- `react-diagnostics.json`

Outputs contain the SHA, route/matrix metadata, scores, tool statuses, and redacted diagnostics. Secrets, cookies, authorization, credentials, tokens, passwords, API keys, raw PII, and raw request headers must never be emitted.

## Failure and cleanup obligations

Any contract, URL, SHA, tool-version, score, blocking-finding, render-budget, invocation, redaction, or artifact-path failure exits nonzero. The harness owner must terminate spawned processes, close browser sessions, remove temporary resources, and leave no listener, secret environment variable, or external-network request. Product packaging must exclude these development-only tools and artifacts.

## Consumer acknowledgement

- Consumer: ____________________
- Revision/SHA reviewed: ____________________
- Acknowledged: ____________________
