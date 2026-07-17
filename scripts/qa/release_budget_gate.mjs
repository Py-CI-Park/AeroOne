#!/usr/bin/env node
// AeroOne 릴리스 성능 예산 게이트 (v1.18.0 승격).
//
// v1.13 Lighthouse 러너(run_v113_lighthouse.mjs)를 릴리스 게이트로 승격하는 축의 하나로,
// 사용자 체감 3경로(대시보드 / · 뉴스레터 /newsletters · Civil /reports/civil-aircraft)에
// 성능 예산을 명문화하고 실측 기록을 산출물로 남긴다.
//
// 이 스크립트가 CI/폐쇄망에서 항상 강제하는 부분은 라우트 First Load JS 크기다 —
// `next build` 출력(결정적·Chrome 불필요)에서 각 경로의 First Load JS 를 파싱해 예산과
// 비교하고, 초과 시 비영점 종료한다. 성능 점수·FCP 예산은 Lighthouse 딥패스
// (run_v113_lighthouse.mjs, Chrome 필요)가 측정하며 본 매니페스트에 함께 정의해 둔다.
//
// 산출물: artifacts/qa/release-budget/<version>.json (측정값·예산·pass/fail).
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');

// 사용자 체감 3경로의 성능 예산. maxFirstLoadKb 는 이 게이트가 강제하고,
// minPerformance/maxFcpMs 는 Lighthouse 딥패스가 측정하는 계약값이다.
// 예산은 현재 실측(대시보드 131 / 뉴스레터 138 / Civil 129 kB)에 회귀 여유를 둔 상한이다.
export const ROUTE_BUDGETS = [
  { route: '/', label: '대시보드', maxFirstLoadKb: 160, minPerformance: 90, maxFcpMs: 2000 },
  { route: '/newsletters', label: '뉴스레터', maxFirstLoadKb: 170, minPerformance: 90, maxFcpMs: 2200 },
  { route: '/reports/civil-aircraft', label: 'Civil', maxFirstLoadKb: 160, minPerformance: 85, maxFcpMs: 2500 },
];

// `next build` 라우트 표의 한 행에서 해당 경로의 First Load JS(kB)를 파싱한다.
// 행 예: "├ ƒ /newsletters                                136 B         138 kB"
// 마지막 크기 토큰(First Load JS)만 취하고 kB 로 정규화한다(B/MB 단위도 처리).
export function parseFirstLoadKb(buildText, route) {
  const lines = buildText.split(/\r?\n/);
  // 경로 정확 일치: 트리 글리프/파일타입 마커 뒤에 경로가 오고, 그 뒤 공백으로 구분된 토큰들.
  const escaped = route.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const re = new RegExp(`^[\\s│├└┌●○ƒλ\\-]*${escaped}\\s{2,}(.+)$`);
  for (const line of lines) {
    const m = line.match(re);
    if (!m) continue;
    // 행 뒤쪽에서 "<num> <unit>" 크기 토큰을 모두 뽑아 마지막(First Load JS)을 쓴다.
    const sizes = [...m[1].matchAll(/([\d.]+)\s*(kB|MB|B)\b/g)];
    if (!sizes.length) continue;
    const [, num, unit] = sizes[sizes.length - 1];
    const value = Number(num);
    if (!Number.isFinite(value)) continue;
    return unit === 'MB' ? value * 1024 : unit === 'B' ? value / 1024 : value;
  }
  return null;
}

// 빌드 출력과 예산으로 라우트별 JS 크기 판정을 만든다.
export function evaluateJsBudgets(buildText, budgets = ROUTE_BUDGETS) {
  return budgets.map((budget) => {
    const measuredKb = parseFirstLoadKb(buildText, budget.route);
    const found = measuredKb !== null;
    const pass = found && measuredKb <= budget.maxFirstLoadKb;
    return {
      route: budget.route,
      label: budget.label,
      measuredFirstLoadKb: found ? Number(measuredKb.toFixed(2)) : null,
      maxFirstLoadKb: budget.maxFirstLoadKb,
      minPerformance: budget.minPerformance,
      maxFcpMs: budget.maxFcpMs,
      status: !found ? 'missing' : pass ? 'pass' : 'fail',
    };
  });
}

function parseArgs(argv) {
  const args = { version: '1.18.0', buildLog: null, out: null };
  for (let i = 2; i < argv.length; i += 1) {
    const [key, value] = argv[i].includes('=') ? argv[i].split(/=(.*)/s) : [argv[i], argv[i + 1]];
    if (key === '--version') args.version = value;
    else if (key === '--build-log') args.buildLog = value;
    else if (key === '--out') args.out = value;
    if (!argv[i].includes('=') && ['--version', '--build-log', '--out'].includes(key)) i += 1;
  }
  return args;
}

function main() {
  const args = parseArgs(process.argv);
  if (!args.buildLog) {
    console.error('release budget gate: --build-log <path to next build stdout capture> is required');
    process.exitCode = 2;
    return;
  }
  const buildText = fs.readFileSync(path.resolve(REPO_ROOT, args.buildLog), 'utf8');
  const results = evaluateJsBudgets(buildText);
  const failed = results.filter((r) => r.status !== 'pass');
  const record = {
    schemaVersion: 1,
    kind: 'release-performance-budget',
    version: args.version,
    generatedAt: new Date().toISOString(),
    note: 'First Load JS is enforced from next build output. performance score / FCP budgets are measured by the Lighthouse deep pass (scripts/qa/run_v113_lighthouse.mjs, Chrome required).',
    results,
    ok: failed.length === 0,
  };
  const outPath = path.resolve(REPO_ROOT, args.out ?? `artifacts/qa/release-budget/${args.version}.json`);
  fs.mkdirSync(path.dirname(outPath), { recursive: true });
  fs.writeFileSync(outPath, `${JSON.stringify(record, null, 2)}\n`, 'utf8');
  for (const r of results) {
    console.log(`${r.status.toUpperCase().padEnd(7)} ${r.route} (${r.label}) First Load JS ${r.measuredFirstLoadKb ?? '?'} / ${r.maxFirstLoadKb} kB`);
  }
  console.log(`release budget artifact: ${outPath}`);
  if (failed.length) {
    console.error(`release budget gate FAILED: ${failed.map((r) => `${r.route}(${r.status})`).join(', ')}`);
    process.exitCode = 1;
  }
}

const invokedPath = process.argv[1] ? pathToFileURL(path.resolve(process.argv[1])).href : null;
if (invokedPath && import.meta.url === invokedPath) main();
