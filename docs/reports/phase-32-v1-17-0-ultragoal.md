# 단계 32 — 1.16.3 개선 계획 완주 (단일 1.17.0 릴리스, ultragoal 9목표)

## 1. 배경

1.16.3 전수 검사([`v1-16-3-full-audit-2026-07-16.md`](v1-16-3-full-audit-2026-07-16.md))와 개선
계획([`v1-17-0-improvement-plan-2026-07-16.md`](v1-17-0-improvement-plan-2026-07-16.md))이 확정한
P0~P2 항목을 durable multi-goal(ultragoal) 9개 목표로 분해해 완주했다. **이 작업 전체는 1.16.3
다음의 단일 릴리스 `1.17.0` 으로 게시한다** — `1.17.0-dev` 브랜치 한 곳에 누적된 결과물이며,
개발 중 목표별로 1.17.0/1.17.1/1.18.0 표기를 오갔으나 어느 것도 별도 게시된 적이 없어 실제
릴리스는 1.17.0 하나로 통합했다(1.16.3 → 1.17.0, minor). 각 목표는
architect CLEAR/APPROVE + executor QA red-team + 전체 게이트를 통과한 뒤에만 완료 체크포인트를
남겼다(품질 게이트 산출물: `artifacts/qa/ultragoal/G00{1..9}/`).

## 2. 목표별 성과

|목표|범위|대표 커밋|
|---|---|---|
|G001|개발 환경 드리프트 방지 — frontend 의존성 복원을 `npm ci` 로 일원화|`8d5dadb`|
|G002|Office Studio 대화형 차트 컴포저(CSV 붙여넣기·첨부·후속명령 refine)|(phase-31)|
|G003|AeroAI SSE 스트리밍 + 파일 첨부 질문, 스트리밍 마크다운 무한 루프 근절|`7191d3d`|
|G004|런처 상태 배지 + 최근 열람 스트립|`7641516`·`0c6daab`|
|G005|문서 수정일 메타·폴더 트리 상태 보존·뉴스레터 이슈 내비|`bd06d60`·`33def5c`|
|G006|경고 부채 4종 제거(pydantic Config·asyncio 스코프·repr 필드·act 경고)|`891ee46`·`8c13ca1`|
|G007|Civil Aircraft 대시보드 v1.8 — 실루엣 상호작용·내보내기·프리셋·측면 후퇴각·지연 로딩|`1303ce1`·`8b4846c`|
|G008|관리자 콘솔 6그룹 IA + 그룹 진입 lazy fetch(개요 진입 17→1) + 43.9KB 분해|`6821e53`·`b42b7c5`|
|G009|릴리스 성능 예산 게이트 승격 + Leantime 단일 워커 한계 명시 + 1.17.0 릴리스 준비|본 단계|

## 3. 릴리스 성능 예산 게이트 (G009)

v1.13 Lighthouse 러너를 릴리스 게이트로 승격했다. 사용자 체감 3경로에 예산을 명문화하고
실측을 산출물로 남긴다.

- 게이트: `scripts/qa/release_budget_gate.mjs`(라우트 First Load JS 상한 강제, `next build` 파싱).
- 예산·실측(1.17.0): 대시보드 `/` 132/160 kB · 뉴스레터 `/newsletters` 138/170 kB · Civil `/reports/civil-aircraft` 130/160 kB — 3/3 pass. 산출물 `artifacts/qa/release-budget/1.17.0.json`.
- 성능 점수·FCP 예산은 같은 매니페스트에 정의, Chrome 딥패스(`run_v113_lighthouse.mjs`)로 측정.
- 문서: [`AGENTS.md`](../../AGENTS.md) §9.3, [`docs/runbook/release-performance-budget.md`](../runbook/release-performance-budget.md).
- Leantime PHP 내장 서버(`php -S`) 단일 워커 한계를 [`docs/runbook/leantime-codeploy.md`](../runbook/leantime-codeploy.md) 에 명시(다중 사용자 상시 운영은 IIS FastCGI/PHP-FPM 승격).

## 4. 최종 게이트 실측 (2026-07-17, 1.17.0)

- backend `pytest tests` 전체: **1,283 passed / 0 failed** (unit 917 + integration 366), 경고 0(1.16.3 대비 pydantic/asyncio/repr 경고 전량 제거).
- frontend Vitest 전체: **625 passed / 97 files**, `tsc --noEmit` 통과, "not wrapped in act" 경고 0.
- `next build` 통과(전 라우트 컴파일, First Load JS 공유 103 kB), 성능 예산 게이트 3/3 pass.
- 각 목표: 2-pass architect(최종 CLEAR/APPROVE) + executor QA red-team + 라이브 브라우저/실측 — 증거 `artifacts/qa/ultragoal/G00{1..9}/`.

## 5. 후속

- 게시(main 병합·tag·GitHub Release·ZIP asset)와 폐쇄망 실 PC 재검증은 운영자 승인 액션.
- 1.16.4 hotfix(Leantime 스택 3중 결함 수정 + 새 스택 ZIP)는 코드 완료, 게시만 운영자 액션.
