# 릴리스 성능 예산 게이트 (Release Performance Budget)

1.17.0 에서 v1.13 Lighthouse 러너를 **릴리스 게이트**로 승격했습니다. 사용자 체감 3경로에
성능 예산을 명문화하고, 릴리스 직전 실측 기록을 산출물로 남깁니다.

## 1. 대상 경로와 예산

`scripts/qa/release_budget_gate.mjs` 의 `ROUTE_BUDGETS` 가 단일 원천입니다.

|경로|라벨|First Load JS 상한|성능 점수 하한|FCP 상한|
|---|---|---|---|---|
|`/`|대시보드|160 kB|90|2000 ms|
|`/newsletters`|뉴스레터|170 kB|90|2200 ms|
|`/reports/civil-aircraft`|Civil|160 kB|85|2500 ms|

First Load JS 상한은 현재 실측(대시보드 132 · 뉴스레터 138 · Civil 130 kB, 1.17.0 기준)에
회귀 여유를 둔 값입니다. 상한을 낮추거나 예산을 바꿀 때는 이 표와 스크립트, 그리고
`frontend/tests/qa/release-budget-gate.test.ts` 를 함께 갱신합니다.

## 2. First Load JS 게이트 (항상 강제 · Chrome 불필요)

라우트 First Load JS 는 결정적이라 CI/폐쇄망에서 항상 강제합니다.

```cmd
cd frontend
npx next build > ..\build.log 2>&1
cd ..
node scripts/qa/release_budget_gate.mjs --build-log build.log --version 1.17.0
```

- 산출물: `artifacts/qa/release-budget/1.17.0.json` (경로별 측정값·예산·pass/fail).
- 예산 초과 또는 경로 누락(fail-closed) 시 종료 코드 1 로 병합을 차단합니다.
- `next build` 출력의 라우트 표에서 각 경로의 First Load JS 컬럼을 파싱하며, `/` 가
  `/newsletters` 같은 하위 경로 행을 잘못 읽지 않도록 경로 뒤 2칸 공백을 요구합니다.

## 3. 성능 점수 · FCP 딥패스 (Chrome 필요 · 본 PC)

성능 점수와 FCP 는 실제 렌더가 필요하므로 Chrome 이 설치된 본 PC 에서 Lighthouse
딥패스(`scripts/qa/run_v113_lighthouse.mjs`)로 측정합니다. 두 게이트의 예산은 동일
매니페스트(`ROUTE_BUDGETS`)에 함께 정의돼 있어 표기 드리프트가 없습니다.

## 4. 릴리스 절차 편입 (AGENTS §9.3)

병합 직전 검증 게이트에 편입되어 있습니다 — [`AGENTS.md`](../../AGENTS.md) §9.3 참고.
backend `pytest tests` 전건 그린 + frontend Vitest 전건 그린 + `tsc` + `next build` +
본 성능 예산 게이트(실측 산출물) 를 모두 남긴 뒤에만 릴리스 태그를 붙입니다.
