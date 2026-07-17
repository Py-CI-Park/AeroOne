import { describe, expect, test } from 'vitest';

// 릴리스 성능 예산 게이트의 순수 파싱/판정 로직 회귀. next build 출력 텍스트에서
// 3경로 First Load JS 를 정확히 뽑고, 예산 초과를 fail 로 판정하는지 고정한다.
import {
  ROUTE_BUDGETS,
  buildBudgetRecord,
  evaluateJsBudgets,
  parseFirstLoadKb,
  // @ts-expect-error — 저장소 루트의 node 게이트 스크립트(.mjs) 를 직접 import 한다.
} from '../../../scripts/qa/release_budget_gate.mjs';

const SAMPLE_BUILD = [
  'Route (app)                                      Size  First Load JS',
  '┌ ƒ /                                         2.28 kB         131 kB',
  '├ ƒ /admin/newsletters                        2.22 kB         131 kB',
  '├ ƒ /newsletters                                136 B         138 kB',
  '├ ƒ /newsletters/[slug]                         136 B         138 kB',
  '├ ƒ /reports/civil-aircraft                     198 B         129 kB',
  '└ ƒ /viewer                                   2.51 kB         132 kB',
  '+ First Load JS shared by all                  103 kB',
].join('\n');

describe('release budget gate parsing', () => {
  test('parses the exact First Load JS for the 3 user-facing routes', () => {
    expect(parseFirstLoadKb(SAMPLE_BUILD, '/')).toBe(131);
    expect(parseFirstLoadKb(SAMPLE_BUILD, '/newsletters')).toBe(138);
    expect(parseFirstLoadKb(SAMPLE_BUILD, '/reports/civil-aircraft')).toBe(129);
  });

  test("root '/' does not accidentally match a nested route like /newsletters", () => {
    // '/' 행만 매치해야 한다 — 하위 경로(/newsletters 등)의 First Load JS 를 잘못 읽으면 131 이 아니게 된다.
    expect(parseFirstLoadKb(SAMPLE_BUILD, '/')).toBe(131);
  });

  test('returns null when a route is absent from the build output', () => {
    expect(parseFirstLoadKb(SAMPLE_BUILD, '/does-not-exist')).toBeNull();
  });

  test('normalizes B and MB units to kB', () => {
    expect(parseFirstLoadKb('┌ ƒ /x                                         10 B         2048 B', '/x')).toBeCloseTo(2, 5);
    expect(parseFirstLoadKb('┌ ƒ /y                                         10 B         2 MB', '/y')).toBe(2048);
  });
});

describe('release budget gate evaluation', () => {
  test('all 3 routes are within their budgets in the sample build', () => {
    const results = evaluateJsBudgets(SAMPLE_BUILD);
    expect(results.map((r: { status: string }) => r.status)).toEqual(['pass', 'pass', 'pass']);
    expect(results.find((r: { route: string; measuredFirstLoadKb: number | null }) => r.route === '/')?.measuredFirstLoadKb).toBe(131);
  });

  test('a route that exceeds its budget is failed', () => {
    const overBudget = SAMPLE_BUILD.replace('131 kB', '999 kB');
    const results = evaluateJsBudgets(overBudget);
    expect(results.find((r: { route: string; status: string }) => r.route === '/')?.status).toBe('fail');
  });

  test('a route missing from the build is flagged missing (fail-closed)', () => {
    const withoutCivil = SAMPLE_BUILD.replace('├ ƒ /reports/civil-aircraft                     198 B         129 kB\n', '');
    const results = evaluateJsBudgets(withoutCivil);
    expect(results.find((r: { route: string; status: string }) => r.route === '/reports/civil-aircraft')?.status).toBe('missing');
  });

  test('the budget manifest covers exactly the 3 user-facing routes with all budget fields', () => {
    expect(ROUTE_BUDGETS.map((b: { route: string }) => b.route)).toEqual(['/', '/newsletters', '/reports/civil-aircraft']);
    for (const b of ROUTE_BUDGETS as Array<{ maxFirstLoadKb: number; minPerformance: number; maxFcpMs: number }>) {
      expect(b.maxFirstLoadKb).toBeGreaterThan(0);
      expect(b.minPerformance).toBeGreaterThan(0);
      expect(b.maxFcpMs).toBeGreaterThan(0);
    }
  });
});

describe('release budget gate record schema', () => {
  test('buildBudgetRecord produces the stable artifact shape with ok reflecting pass/fail', () => {
    const results = evaluateJsBudgets(SAMPLE_BUILD);
    const record = buildBudgetRecord(results, '9.9.9', new Date('2026-07-17T00:00:00Z'));
    expect(record.schemaVersion).toBe(1);
    expect(record.kind).toBe('release-performance-budget');
    expect(record.version).toBe('9.9.9');
    expect(record.generatedAt).toBe('2026-07-17T00:00:00.000Z');
    expect(typeof record.note).toBe('string');
    expect(record.results).toBe(results);
    expect(record.ok).toBe(true);
  });

  test('ok is false when any route is not pass', () => {
    const overBudget = SAMPLE_BUILD.replace('131 kB', '999 kB');
    const record = buildBudgetRecord(evaluateJsBudgets(overBudget), '9.9.9');
    expect(record.ok).toBe(false);
  });
});
