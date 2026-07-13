---
slug: v1-13-0-operator-experience-plan
status: in-progress
risk: high
branch: 1.13.0-dev
baseline-head: 034bd03
target: v1.13.0 PR-ready, PR not opened
updated: 2026-07-11
handoff: docs/runbook/ai-agent-handoff-2026-07-11.md
status-report: docs/reports/v1-13-0-development-status-2026-07-11.md
---

# AeroOne v1.13.0 운영 경험·패키지 안전성 개발 계획

## TL;DR

> **2026-07-11 checkpoint:** Task 1~2는 완료됐다. Task 3 Round 4 구현은 `.worktrees/1.12.3-hotfix`의 미커밋 변경으로 존재하며 focused 85개는 PASS했으나 backend full 최종 재실행이 worker 사용량 한도로 중단되어 Task 3은 미완료다. 다음 에이전트는 [최신 핸드오프](../../docs/runbook/ai-agent-handoff-2026-07-11.md)와 [상태 보고서](../../docs/reports/v1-13-0-development-status-2026-07-11.md)를 읽고 Task 3 backend full부터 재개한다. Task 4 실행은 금지한다.

> **Summary**: proven-unsafe 1.12.2를 즉시 봉쇄하고 승인된 historical 자산·자격증명·패키저를 정리해 1.12.3을 배포한 뒤, 그 계보 위에서 v1.13.0 운영 경험을 구현해 PR 생성 직전까지 검증한다.
> **Deliverables**:
> - 1.12.2/승인된 historical containment, DB-aware rotation, safe 1.12.3 release
> - public allow-list package와 별도 CMS 승인 internal bundle 도구
> - session-aware nav/account/activity와 admin Overview/users/sessions/modules
> - reproducible browser/package QA, v1.13.0 docs/version, Korean PR body
> **Effort**: XL
> **Parallel**: YES — 6 implementation waves + final verification
> **Critical Path**: Task 1 → 2(owner approval) → 3-9 → 10 → 11-15 → 16-24 → 25-27 → F1-F6

## Context

### Original Request

- 최신 원격을 반영해 `1.13.0-dev`에서 v1.13.0을 개발한다.
- 앞서 제안한 다섯 권고안을 모두 실행한다.
- 기존 v1.13.0 계획을 현재 환경에 맞게 재검토·수정하고, 제품을 v1.13.0 PR 직전까지 완성한다.
- 사용자가 명시한 `$ulw-plan` 흐름에 따라 실행 전에 결정 완료형 계획을 만든다.

### Confirmed Repository and Release State

- 현재 브랜치/HEAD: `1.13.0-dev@034bd03`, upstream `origin/1.13.0-dev`.
- 계획 시점 divergence: upstream과 `0 0`, `origin/main...HEAD`는 main 쪽 0/dev 쪽 2.
- open PR: `1.13.0-dev`에서 열린 PR 없음.
- 제품 파일은 깨끗하며 기존 dirty 항목은 계획 초안뿐이다. 브랜치를 재생성·reset·rebase하지 않는다.
- 공개됐던 1.12.2 ZIP과 로컬 ZIP digest가 일치하며, Task 2의 sparse 중앙-directory-only 감사에서 env, DB/backend data, storage, agent/VCS state, cache/dev artifact가 확인되었다. 일반 dependency 파일명에서 발생한 legacy `backup` 오탐은 경로 문맥 규칙으로 제거했다. 내용과 비밀값은 열지 않았다.
- GitHub의 `downloadCount=0`은 미접근 증거로 사용하지 않는다.
- Task 2에서 paginated 46-release를 재열거하고 원격 잔존 ZIP 14개와 Task 1의 local matching receipt 1개를 같은 고정 정책으로 중앙-directory-only 재감사했다. 15개 모두 unsafe, parser/audit error 0, contract mismatch 0이었다. ZIP entry stream/content는 열지 않았으며 나머지 exact asset 삭제는 별도 owner 승인 전 실행하지 않는다.

  | Tag | ZIP asset ID | SHA asset ID | Verdict |
  | --- | --- | --- | --- |
  | 1.12.2 | 469662394 | 469662393 | env/database/storage/agent-state/dev-artifact |
  | 1.12.1 | 468959744 | 468959745 | env/database/storage/agent-state/dev-artifact |
  | 1.12.0 | 467598771 | 467598772 | env/database/storage/agent-state/dev-artifact |
  | 1.11.0 | 467141283 | 467141282 | env/database/storage/agent-state/dev-artifact |
  | 1.10.0 | 466204038 | 466204039 | env/database/storage/agent-state/dev-artifact |
  | 1.8.0 | 465087963 | 465087964 | env/database/storage/agent-state/dev-artifact |
  | 1.7.1 | 463971385 | 463971384 | env/database/storage/agent-state/dev-artifact |
  | 1.7.0 bundle/offline | 460314227 / 460314230 | 460314229 / 460314228 | storage/agent-state/dev-artifact 또는 storage/dev-artifact |
  | 1.6.2 | 451005119 | 451005118 | storage/dev-artifact |
  | 1.6.1 | 449183210 | 449183209 | env/database/storage/agent-state/dev-artifact |
  | 1.6.0 | 448898337 | 448898338 | env/database/storage/agent-state/dev-artifact |
  | 1.5.0 bundle/offline | 448050524 / 448050213 | 448050525 / 448050212 | storage/agent-state/dev-artifact 또는 env/database/storage/agent-state/dev-artifact |
  | 1.4.4 | 445483030 | 445483029 | storage/dev-artifact |

- `offline_package.bat`의 deny-list 복사 방식은 새 로컬 상태를 자동 포함할 수 있고 최종 ZIP verifier가 없다.
- `next@15.2.0`은 취약하며, 동일 minor의 정확 고정 버전 `15.2.9`를 보안 핫픽스 기준으로 채택한다.
- 2026-07-11 재검증 결과 host는 Windows 11 Pro build 26200이고 현재 process는 비관리자다. BIOS virtualization/Hypervisor 요건은 충족하지만 `WindowsSandbox.exe`가 absent하고 feature 조회·활성화는 elevation이 필요하다. Task 6 구현과 synthetic QA는 계속 진행하되 실제 기능 활성화는 관리자 PowerShell에서 수행하고, 반환된 `RestartNeeded`가 true일 때만 Boulder+ledger checkpoint 후 자동 reboot 없이 재부팅 승인을 받아 같은 계획을 재개한다.

### Interview Summary

1. 공개 1.12.2 위험 자산을 즉시 봉쇄하고 안전 자산으로 교체한다.
2. 잠재 노출된 JWT·계정·외부 provider 자격증명을 회전하고 세션을 무효화한다.
3. 공개 packager를 fail-closed allow-list + manifest + pre/post verifier로 바꾼다.
4. 공개 GitHub ZIP은 코드·런타임과 저장소 추적 비민감 seed만 포함한다.
5. 실제 `_database`는 별도 승인된 내부 번들로만 전달하고 NSA는 공개 기본값에서 영구 제외한다.
- 내부 번들 기본 구현은 새 crypto runtime 대신 현재 검증된 Windows PowerShell 5.1 SignedCms/EnvelopedCms와 외부 조직 인증서를 사용한다. 실제 trust/certificate provisioning과 real bundle은 PR 범위 밖이며 absent trust는 fail closed다.
- QA host Node 22.14.0과 호환되는 Lighthouse 12.8.2를 사용하고 offline product Node 20.18.0과 분리한다.
- historical ZIP/SHA asset ID 삭제는 운영자 승인 후 Task 2에서 완료됐다. Windows Sandbox host reboot만 실제 feature 활성화 결과가 `RestartNeeded=true`일 때 별도 운영자 승인이 필요한 유일한 환경 gate로 남는다.

### Metis Review (gaps addressed)

- 기존 계획은 현재 브랜치를 다시 만들고 1.12.2 사고·1.12.3 핫픽스를 누락해 전면 교체가 필요하다는 판정을 반영했다.
- 제품 수정은 1.12.3 공개 검증 완료 전까지 금지한다.
- containment 실패, 자격증명 회전 불완전, verifier 실패, 부분 릴리스 자산은 모두 후속 작업을 차단한다.
- 인증·활동·관리자 집계·모듈 정책·QA·문서·버전·push를 각각 독립 작업과 증거로 분리한다.
- 직접 확인한 canonical 정책과 충돌한 두 제안은 교정했다: `search.nsa.read` legacy 권한은 `can_read_collection` 호환 계약에 따라 유지하고, 활동 세션은 실제 모델 필드 `created_at/last_seen_at/expires_at/is_current`를 사용한다.

## Work Objectives

### Core Objective

노출 가능성이 있는 공개 오프라인 패키지 경로를 먼저 안전하게 폐쇄한 뒤, 인증·권한·운영자 UX를 확장하고, 현재 Windows 폐쇄망 환경에서 재현 가능한 검증을 거쳐 `1.13.0-dev`를 PR 생성 직전 상태로 만든다.

### Deliverables

- redacted incident record와 1.12.2 및 동일 취약 packager 계열의 과거 공개 자산 containment 영수증.
- DB-aware 전 계정 비밀번호 회전·`session_version` 증가·활성 세션 제거 도구와 값 없는 검증 영수증.
- 공개 패키지 policy/builder/verifier, ZIP·SHA256·manifest 3종 산출물, 별도 내부 데이터 bundle builder·승인 schema.
- Next.js 15.2.9 기반 검증된 1.12.3 보안 릴리스와 dev ancestry merge.
- root `DESIGN.md`, `.omo/frontend-design/state.md`, dev-only QA 도구와 격리 browser harness.
- 공유 client session, 계정 메뉴, 공개 Document·권한 인식 NSA, 안전 로그인 redirect, 자기 활동 API/UI.
- 관리자 backend overview·실세션 집계·모듈 정책과 frontend Overview·사용자·세션·모듈 화면.
- phase-26 보고서, 최신 handoff, 운영·보안·설치 문서, 최종 v1.13.0 버전 메타데이터.
- 전체 자동/브라우저/시각/보안/문서 검증 증거와 한국어 PR 본문 초안.

### Definition of Done (verifiable conditions with commands)

- 1.12.2와 이름-only 감사에서 위험 판정된 과거 Release 객체/tag는 보존되고 해당 ZIP/SHA URL은 404이며, 경고 아래 기존 release notes가 그대로 보존된다.
- 현재 작업공간 `D:\Chanil_Park\Project\Programming\AeroOne`의 root/backend env와 한 번만 처리되는 canonical `backend/data/aeroone.db`에서 JWT·모든 계정 비밀번호가 회전되고 기존 토큰/비밀번호가 거부된다.
- 1.12.3 공개 ZIP에 금지 경로·실데이터·로컬 상태가 0개이고 로컬/sidecar/manifest/GitHub/download digest가 모두 일치한다.
- 1.12.3 source commit가 `origin/main`과 `1.12.3^{}`에 일치하고 그 commit과 기존 `034bd03` 모두 최종 dev HEAD의 ancestor다.
- v1.13.0 제품 계약과 QA 기준이 모두 통과하며 실패를 “기존 실패”로 면제하지 않는다.
- `1.13.0-dev`가 clean하고 원격 divergence `0 0`, open 1.13 PR/tag/release가 없으며 PR 본문 파일만 ignored artifact로 준비돼 있다.

### Must Have

- 모든 보안·개인정보 증거에는 값·hash·DB row·민감 entry name 대신 범주/개수/성공 여부만 기록한다.
- credential incident scope는 현재 작업공간의 `.env`, `backend/.env`, 동일 canonical SQLite DB로 고정한다. 회전 key는 `JWT_SECRET_KEY`, `ADMIN_PASSWORD`이며 frontend URL key는 회전 대상이 아니다. 예상 밖 provider key·다른 deployment root가 발견되면 자동 처리하지 않고 Task 4를 차단한다.
- 공개 package release mode는 HEAD와 정확히 일치하는 annotated tag가 없으면 실패한다.
- QA mode는 `artifacts/qa/`에 `1.13.0-pr-<shortsha>`로만 만들며 publishable `dist/`에 쓰지 않는다.
- Document는 anonymous/authenticated 모두에게 공개 상태를 유지한다.
- NSA는 module이 enabled/non-hidden이고, 인증 사용자가 admin·`collections.nsa.read`·legacy `search.nsa.read`·정확한 `collection/nsa/collections.nsa.read` grant 중 하나를 만족할 때만 노출한다.
- 활동 API는 자기 데이터만 bounded query로 반환하며 콘텐츠·식별자·hash·IP·UA를 반환하지 않는다.
- 관리자 수치는 backend의 일관된 24시간 current/previous window에서 계산하고 frontend가 누락 값을 0으로 위조하지 않는다.
- 서비스 모듈 access tuple은 PATCH merged state를 server가 검증한다.
- 모든 커밋은 한국어 제목/본문과 7개 Lore trailer를 갖는다.

### Must NOT Have (guardrails, scope boundaries)

- 구 ZIP·구 credential 복원, 1.12.2 tag 이동/재작성, release 객체 삭제.
- 공개 packager의 `--include-data`/NSA 우회 옵션, 실제 내부 bundle의 GitHub/`dist/` 출력.
- `.env*`, DB, backup, storage, `_database`, NSA, `.git`, `.claude`, `.omo`, `.codegraph`, `.gjc`, `.omc`, `.omx`, `.worktrees`, cache, dev QA 도구의 공개 ZIP 포함.
- auth JWT hash와 AI session hash join, `AiConversation` title/message/prompt/answer/citation/snippet의 활동 API 포함.
- frontend-only 권한 보장, module-disabled/session-error 상태의 NSA fail-open.
- 새 chart/icon/animation runtime dependency, CDN, floating `latest`/`npx` QA 도구.
- giant admin 파일에 기능을 계속 누적하거나 fake donut/sparkline/가짜 0 수치를 표시하는 구현.
- `git reset`, rebase, force-push, squash, dev 브랜치 삭제.
- `gh pr create`, `gh pr create --dry-run`, main v1.13 merge/tag/release.

## Verification Strategy

> ZERO HUMAN INTERVENTION - OS feature/reboot prerequisite가 완료된 뒤 모든 검증은 agent가 실행한다.
> Test decision: security/auth/package/backend는 TDD, behavior-preserving UI refactor는 characterization-first tests-after.
> QA policy: every task has agent-executed happy and failure scenarios.
> Evidence: `.omo/evidence/v1-13-0/task-{N}.md` + ignored binary artifacts.

### Test Policy

- 보안·권한·활동·패키지·redirect·module validator는 RED 테스트를 먼저 추가한 뒤 최소 구현으로 GREEN을 만든다.
- 대형 admin 추출은 기존 계약 테스트를 먼저 잠그고 behavior-preserving refactor 후 기능을 추가한다.
- UI 변경은 unit/component만으로 끝내지 않고 production `next start` + stable Chrome에서 검증한다.
- 모든 테스트는 현재 revision에서 새로 실행하며 과거 `.omo/evidence`를 현재 PASS로 재사용하지 않는다.

### Exact Local Tooling

- Backend: repository의 `.venv` Python + `pytest`.
- Frontend: lockfile 기반 npm, Vitest, TypeScript, Next production build.
- Browser/dev QA exact dev dependencies: `@playwright/test@1.61.1`, `@axe-core/playwright@4.12.1`, `lighthouse@12.8.2`, `playwright-lighthouse@4.0.0`, `react-grab@0.1.48`, `react-scan@0.5.7`, `react-doctor@0.7.3`. Host Node `22.14.0`과 모두 호환되며 offline product installer Node `20.18.0`과 분리한다.
- Browser: installed stable Chrome `C:\Program Files\Google\Chrome\Application\chrome.exe`; Playwright bundled Chromium download 금지.

### Browser Matrix

| Route | Identities / states | Required checks |
| --- | --- | --- |
| `/login` | anonymous, invalid credential, normal/admin success, safe/unsafe `next` | label/autofill/loading/error, hard navigation, redirect sanitizer |
| `/` | anonymous, normal, NSA permission, NSA resource grant, legacy permission, admin, session unavailable, NSA module disabled | Document always, NSA exact matrix, account menu |
| `/activity` | normal self data, empty, 401, 5xx retry | cross-user absence, bounded rows, no sensitive content |
| `/admin` Overview | admin full/degraded/empty | backend values, partial state, charts/text, shortcut `0` |
| `/admin` Users | admin mixed roles/statuses, page 1/2 | search/sort/reset, created/last login, 10/page |
| `/admin` Sessions | admin active/stale/events, purge | 15s scoped refresh, actual counts, filters/paging |
| `/admin` Modules | admin Document/NSA/invalid tuples | create/edit presets, server rejection, no mutation/audit on failure |
| `/documents` | anonymous/authenticated, loaded/empty/error | public access, iframe/parent scroll |
| `/nsa` | normal denied, all four valid authority paths allowed, module disabled | UI fail-closed plus direct API 401/403 |
| `/newsletters` + seeded detail | anonymous/authenticated | existing release/read-beacon regression |

각 상태는 375×812, 768×1024, 1280×800에서 실행하고 대표 화면은 200% zoom도 검사한다. CJK/U+FFFD, focus/keyboard, root overflow, unexpected console/page/request/4xx/5xx, browser external network/CDN/`:11434`, Axe moderate/serious/critical 위반을 0으로 만든다. `/login`, `/activity`, `/admin`은 mobile/desktop 각 3회 Lighthouse 중앙값 100/100/100/100을 요구한다.

### Evidence Policy

- 커밋되는 요약: `.omo/evidence/v1-13-0/task-<N>.md`; secret 값과 원시 DB/ZIP 목록 금지.
- 대용량 로그·스크린샷·trace·PR 본문: ignored `artifacts/qa/v1.13.0/<commit>/`.
- incident credential bundle: `%USERPROFILE%\AeroOne-secure\1.12.3-credentials.dpapi`, 현재 Windows SID 전용 DPAPI + ACL; stdout/로그/Git 금지.
- `.omo/start-work/ledger.jsonl`은 append-only, 기존 evidence는 superseded 표시만 하고 삭제·재사용하지 않는다.

## Execution Strategy

### Parallel Execution Waves

> Target: shared foundations first, then 5-8 parallel-safe tasks per product wave; P0과 release/metadata gates는 의도적으로 직렬화한다.

| Wave | Purpose | Tasks |
| --- | --- | --- |
| 0 | P0 containment·자격증명 | 1-4 |
| 1 | 1.12.3 패키지·보안 릴리스 | 5-10 |
| 2 | v1.13 UI·QA·코드 구조 기반 | 11-15 |
| 3 | 사용자 인증·활동 흐름 | 16-19 |
| 4 | 관리자 backend/frontend | 20-24 |
| 5 | 문서·통합 QA·버전 최종화 | 25-27 |
| Final | 독립 검토·fresh gate·push | F1-F6 |

### Dependency Matrix (full, all tasks)

| Task | Depends on | Blocks | Parallel-safe with |
| --- | --- | --- | --- |
| 1 | none | 2 | none |
| 2 | 1 | 3-9 | none |
| 3 | 2 | 4-9 | none |
| 4 | 3 | 9 | 5-8 after tool contract lands |
| 5 | 3 | 6-9 | 4 |
| 6 | 5 | 8-9 | 7 |
| 7 | 5 | 8-9 | 6 |
| 8 | 4,6,7 | 9 | none |
| 9 | 4-8 | 10 | none |
| 10 | 9 | 11-27 | none |
| 11 | 10 | 14,16,17,19,22-24 | 12,13 |
| 12 | 10 | 16-27 | 11,13,14,15 |
| 13 | 10 | 18,20,21 | 11,12,14,15 |
| 14 | 11 | 22-24 | 12,13,15 |
| 15 | 10 | 16,18,19 | 11-14 |
| 16 | 11,12,15 | 19,25-27 | 17,18 |
| 17 | 11,12 | 19,25-27 | 16,18 |
| 18 | 12,13,15 | 19,25-27 | 16,17 |
| 19 | 11,12,15-18 | 25-27 | 20,21 |
| 20 | 12,13 | 22,23,25-27 | 21 |
| 21 | 12,13 | 24-27 | 20 |
| 22 | 11,12,14,20 | 25-27 | 23,24 after shared types settle |
| 23 | 11,12,14,20 | 25-27 | 22,24 |
| 24 | 11,12,14,21 | 25-27 | 22,23 |
| 25 | 16-24 | 26-27 | none |
| 26 | 12,19,22-25 | 27 | none |
| 27 | 26 | F1-F6 | none |

## TODOs

> Implementation + Test = ONE task. Never separate.
> EVERY task has exhaustive references, agent-executable acceptance criteria, happy/failure QA, and a commit decision.

- [x] 1. 다른 감사보다 먼저 proven-unsafe 1.12.2 asset pair를 즉시 봉쇄한다

  **What to do**: product Git reconciliation이나 historical download를 기다리지 않는다. 실행기 시작에 `.omo/boulder.json`을 현재 root/plan/branch/Task 1로 교체하고 ledger에 start event를 append한다. `gh auth status`와 repo/release를 확인한 뒤 exact release ID `350620445`, ZIP ID `469662394`, SHA ID `469662393`, 알려진 digests가 Task 1 재조회와 일치하는지 확인한다. 기존 1.12.2 body hash를 보존하고 맨 위에 사용·재배포 금지/1.12.3 교체 예정 경고를 prepend한 다음 두 asset만 ID로 삭제한다. release/tag/다른 asset은 보존하고 두 old URL 404와 body suffix hash를 즉시 확인한다.

  **Must NOT do**: Git pull/audit 완료를 기다림, release/tag 삭제·이동, asset name glob, ZIP download/extract/open, body 원문 수정, `downloadCount=0`을 미접근 증거로 표현, 다른 historical asset 변경.

  **Parallelization**: Can Parallel: NO | Wave 0 | Blocks: 2 | Blocked By: none

  **References** (executor has NO interview context - be exhaustive): GitHub release `1.12.2` exact IDs above; `.omo/boulder.json`; `.omo/start-work/ledger.jsonl`; planned incident report; Task 1 planning audit receipt.

  **Acceptance Criteria** (agent-executable only):
  - [ ] boulder current root/plan/task; 1.12.2 release/tag 존재; warning 아래 원문 body hash 동일; asset IDs 469662394/469662393만 absent; old URLs 404; other asset set 동일; evidence에 값/entry name 0.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path
    Tool: gh api + curl
    Steps: exact IDs/digests/body hash를 확인해 warning+두 delete를 수행하고 release/tag/원문/404를 재검증한다.
    Expected: Exit 0 and every named assertion is true.
    Evidence: .omo/evidence/v1-13-0/task-1.md

  Scenario: Failure/edge case
    Tool: gh api + curl
    Steps: ID/digest/body mismatch 또는 warning/delete/404 실패면 가능한 경고를 유지하고 모든 후속 작업을 즉시 중단한다.
    Expected: The task blocks or exits nonzero exactly as stated, with no forbidden side effect.
    Evidence: .omo/evidence/v1-13-0/task-1-error.md
  ```

  **Commit**: NO | Message: n/a | Files: evidence or external receipts only (current OMO state와 승인된 1.12.2 외부 containment receipt만 생성.).

- [x] 2. Git 상태를 fast-forward로 맞추고 46개 release의 historical ZIP을 중앙-directory-only로 재감사한다

  **What to do**: `git fetch --prune origin`, `git pull --ff-only`, status/HEAD/upstream/main divergence/worktree를 기록한다. `gh api --paginate 'repos/Py-CI-Park/AeroOne/releases?per_page=100'`로 46개 전부를 열거한다. audit policy는 env(exact `.env.example` 제외), `_database`, backend/data·DB, storage, backup, agent/VCS/worktree state, cache/dev artifact를 unsafe로 고정한다. 각 ZIP은 HTTP byte-range로 EOCD/ZIP64 EOCD와 central directory만 memory에 읽고 filename category count만 계산하며 entry stream/content와 full archive는 읽지 않는다. 원격 잔존 unsafe ZIP 14개와 Task 1에서 봉쇄한 1.12.2 receipt를 합쳐 planning table의 15 ZIP/paired SHA ID·digest/verdict를 재검증한다. 1.12.2 외 exact IDs에 대한 owner approval receipt가 확인되면 각 affected release body hash를 보존하고 warning을 prepend한 뒤 ZIP/SHA pair만 ID로 삭제해 URL 404/body suffix hash/다른 asset 보존을 검증한다. approval이 없으면 Task 3과 1.12.3을 차단한다.

  **Must NOT do**: branch recreate/reset/rebase/force, full ZIP download/extract/entry open, category 밖 내용 추론, audit 실패 무시, 1.12.2 외 asset의 묵시적 경고/삭제, `034bd03` 강제 복귀.

  **Parallelization**: Can Parallel: NO | Wave 0 | Blocks: 3-9 | Blocked By: 1

  **References** (executor has NO interview context - be exhaustive): Context historical asset table; `AGENTS.md`; `.omo/boulder.json`; `.omo/start-work/ledger.jsonl`; `.omo/evidence/v1-13-0/task-2.md`; `.omo/evidence/v1-13-0/task-2-central-directory-audit.ps1`; `.omo/evidence/v1-13-0/task-2-contain-historical-assets.sh`; `docs/INDEX.md` 비공개 경계; planned public package policy.

  **Acceptance Criteria** (agent-executable only):
  - [x] branch upstream `0 0`; unexpected product dirty 0; paginated release count 46; 원격 잔존 matching unsafe ZIP 14 + Task 1 contained receipt 1 = planning table 15, audit error 0; table의 IDs/digests/category verdict 일치; temp/full ZIP bytes 0; evidence에 raw entry names/values 0; containment dry-run은 12 releases/14 pairs/28 assets/mutation 0을 통과; owner-approved historical pair는 warning/원문 hash/404/other-assets-preserved를 모두 통과하고 미승인 상태에서는 Task 3 blocked.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path
    Tool: Git Bash + gh api + PowerShell ZIP parser
    Steps: paginated API와 ZIP32/ZIP64 parser가 15 assets를 동일 분류하고 approval의 exact historical IDs에만 warning/delete를 적용해 모두 404로 만든다.
    Expected: Exit 0 and every named assertion is true.
    Evidence: .omo/evidence/v1-13-0/task-2.md

  Scenario: Failure/edge case
    Tool: Git Bash + gh api + PowerShell ZIP parser
    Steps: page/asset/pair/range/parser/digest mismatch 또는 approval 부재면 1.12.3 worktree 생성 전 차단하며 미승인 historical asset은 변경하지 않는다.
    Expected: The task blocks or exits nonzero exactly as stated, with no forbidden side effect.
    Evidence: .omo/evidence/v1-13-0/task-2-error.md
  ```

  **Commit**: NO | Message: n/a | Files: evidence or external receipts only (read-only Git/release audit와 owner approval receipt만 생성.).

- [ ] 3. clean main worktree에서 DB-aware 자격증명 회전 도구를 TDD로 구현한다

  **What to do**: clean sibling main worktree를 만들고 DB transaction tool과 PowerShell incident orchestrator를 추가한다. Python은 all-user CSPRNG hashes/password_changed_at/session_version/session rows를 한 transaction으로 바꾸고 before/after count만 반환한다. PowerShell은 exact workspace/key/DB validation, current-user DPAPI database recovery·rotation journal·credential bundle, pending env creation, atomic promotion, postcommit forward-resume, secure quarantine move/manifest를 구현한다. failpoint는 `before_db_commit`, `after_db_commit`, `after_root_env_promote`, `before_credentials_promote` exact 값만 test mode에서 허용한다. 다른 provider/key/root 기능은 없다.

  **Must NOT do**: plaintext/hash/secret를 stdout·argv·shell transcript·Git·`.omo/evidence`에 출력, 사용자 일부만 회전, env만 바꾸고 DB를 생략, 기존 credential로 rollback, dev dirty plan을 hotfix worktree에 복사.

  **Parallelization**: Can Parallel: NO | Wave 0 | Blocks: 4-9 | Blocked By: 2

  **References** (executor has NO interview context - be exhaustive): `backend/app/modules/auth/models.py:11-23`; `backend/app/modules/admin/models.py:94-109`; `backend/app/modules/auth/api.py:143-144`; `backend/app/modules/admin/api.py:517-533`; `backend/app/core/security.py:36-47`; `backend/tests/integration/test_admin_rbac_matrix.py`.

  **Acceptance Criteria** (agent-executable only):
  - [ ] RED→GREEN; synthetic DB row=hash-inequality count; version +1/timestamps/session 0/role-active invariant; precommit rollback, each postcommit failpoint idempotent forward-resume; env/admin/DB synchronization; DPAPI same-SID only; exact ACL/retention/quarantine manifest; stdout/evidence secret/hash 0.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path
    Tool: pytest + PowerShell
    Steps: 임시 SQLite와 exact-key synthetic env에서 dry-run → execute → old token/password 401 → DPAPI의 새 admin credential login 200을 검증한다.
    Expected: Exit 0 and every named assertion is true.
    Evidence: .omo/evidence/v1-13-0/task-3.md

  Scenario: Failure/edge case
    Tool: pytest + PowerShell
    Steps: read-only DB, row-count mismatch, insecure output ACL, unknown key/root 입력 중 하나면 transaction/output promotion을 실패시키고 old credential 복구 없이 서비스를 중지 상태로 유지한다.
    Expected: The task blocks or exits nonzero exactly as stated, with no forbidden side effect.
    Evidence: .omo/evidence/v1-13-0/task-3-error.md
  ```

  **Commit**: YES | Message: `노출 가능 자격증명을 데이터베이스 기준으로 일괄 회전한다`; focused tests와 7개 Lore trailer 포함. | Files: implementation, tests, and evidence paths listed above.

- [ ] 4. 현재 작업공간의 정확한 env·canonical DB 자격증명과 세션을 회전한다

  **What to do**: exact scope와 canonical DB를 확인하고 workspace AeroOne process를 중지한다. secure root는 `%USERPROFILE%\AeroOne-secure\incident-20260710`으로 고정하고 owner=current SID, inheritance disabled, current SID+SYSTEM FullControl 외 ACE 0으로 만든다. 버전에 종속되지 않는 final 이름 `credentials.dpapi`, versioned `recovery/aeroone-db-before-rotation.<rotation-id>.dpapi`, `rotation-state.json.dpapi`, pending credential/env files를 current-user DPAPI로 저장하고 retention을 `2027-07-10T00:00:00+09:00`으로 기록한다. promotion protocol은 (1) exclusive DB lock+DPAPI recovery, (2) new values를 memory/pending DPAPI에 생성, (3) DB transaction으로 모든 hashes/session versions/session rows 변경, (4) commit, (5) old root/backend env를 quarantine으로 move, (6) pending env를 atomic rename, (7) credentials bundle을 final rename, (8) verify다. DB commit 뒤 env promotion 실패는 old DB/credential로 rollback하지 않고 state journal로 forward-resume한다. local `dist/*.zip`을 Task 2 category parser로 audit해 unsafe ZIP과 paired SHA 및 해당 staging dirs, exact env/DB backup paths를 `quarantine/<category>/`로 move하고 secure `quarantine-manifest.json`에 source relative path/size/SHA/moved_at/retention만 기록한다. 이번 실행에서 quarantine 삭제는 하지 않는다.

  **Must NOT do**: workspace 밖 discovery/rotation/delete, quarantine/backup 파괴, broad recursive delete, live DB 삭제·중복 처리, role/active 변경, frontend URL 회전, unknown provider 절차 발명, secret 출력, setup-only 완료 처리, DB commit 뒤 old credential rollback.

  **Parallelization**: Can Parallel: YES | Wave 0 | Blocks: 9 | Blocked By: 3

  **References** (executor has NO interview context - be exhaustive): `setup_offline.bat:119-155`; `backend/scripts/seed.py:35-38`; `backend/app/modules/auth/services.py:23-28`; `README.md` 기존 재실행 안내; Task 3 rotation scripts.

  **Acceptance Criteria** (agent-executable only):
  - [ ] env key set exact; canonical DB 하나/transaction 1회; secure root ACL exact; recovery/journal/credential DPAPI files 존재; user row 수=pre/post hash inequality 수; session_version 전부 +1; session rows 0; role/is_active 불변; root/backend JWT·ADMIN_PASSWORD와 DB 지정 admin 동기화; securely known old admin password/JWT만 401; 새 active user credential 200, inactive user credential 403; local unsafe ZIP/SHA/staging와 plaintext backup source count 0, quarantine hash/source manifest count 일치; retention exact; public evidence secret/hash/raw path 0.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path
    Tool: PowerShell + pytest + curl
    Steps: stopped workspace에서 protocol을 한 번 수행해 hash/session/role counts, known-old rejection, new active/inactive behavior, quarantine source-absent/destination-hash를 확인한다.
    Expected: Exit 0 and every named assertion is true.
    Evidence: .omo/evidence/v1-13-0/task-4.md

  Scenario: Failure/edge case
    Tool: PowerShell + pytest + curl
    Steps: synthetic failpoint를 DB precommit/env rename/final credential rename마다 주입해 precommit은 transaction rollback, postcommit은 journal forward-resume로 새 상태를 완성하며 service는 검증 전까지 중지 상태다.
    Expected: The task blocks or exits nonzero exactly as stated, with no forbidden side effect.
    Evidence: .omo/evidence/v1-13-0/task-4-error.md
  ```

  **Commit**: NO | Message: n/a | Files: evidence or external receipts only (Task 3의 reviewed 도구를 운영 실행하며 값 없는 receipt만 남긴다.).

- [ ] 5. 공개 package policy와 pre/post ZIP verifier를 RED-GREEN으로 구현한다

  **What to do**: public policy/verifier와 `packaging/installer-policy.json`을 추가한다. release/QA profile의 required installers는 (1) `python-3.12.7-amd64.exe`, SHA-256 `1206721601a62c925d4e4a0dcfc371e88f2ddbe8c0c07962ebb2be9b5bde4570`, Authenticode signer thumbprint `36168EE17C1A240517388540C903BB6717DD2563`, subject `Python Software Foundation`; (2) `node-v20.18.0-x64.msi`, SHA-256 `93d1d30341d7d38b7a8f3ab0fa3be1f9e6436b90338b2bd8b8af4e80d00bd036`, thumbprint `6153EB0186DD8FEBD9E3693F4F110DEFC007715D`, subject `OpenJS Foundation`이다. verifier는 path/duplicate/traversal/symlink, manifest one-to-one, entry hashes/origin/tag/commit/policy, required runtime와 두 installer exact filename/hash/Valid signature/thumbprint/subject를 pre-stage/post-stage에서 path 기반으로 검사한다. Windows PowerShell 5.1이 ZIP stream에 대해 Authenticode를 `NotSigned`로 판정하는 제약 때문에 post-ZIP은 archive를 extract하지 않고 entry SHA-256이 앞 단계에서 Valid 서명·thumbprint·subject까지 검증한 exact pinned digest와 같은지 증명해 동일 바이트의 서명 판정을 계승한다.

  **Must NOT do**: deny-list만으로 PASS, `.env.example` pattern으로 real `.env*` 허용, verifier 실패 산출물을 `dist/`에 남김, archive entry를 extract해 내용 검사, policy 밖 새 top-level 자동 허용.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 6-9 | Blocked By: 3

  **References** (executor has NO interview context - be exhaustive): `offline_package.bat:41-83`; `offline_installers/python-3.12.7-amd64.exe`; `offline_installers/node-v20.18.0-x64.msi`; planned `packaging/public-package-policy.json`, `packaging/installer-policy.json`, `scripts/verify_offline_package.ps1`, `backend/tests/unit/shared/test_offline_package_security.py`; existing batch tests.

  **Acceptance Criteria** (agent-executable only):
  - [ ] synthetic safe stage/ZIP PASS; 모든 forbidden/path/manifest/tag mismatch FAIL; installer missing/extra/rename/hash/status/thumbprint/subject mismatch 각각 FAIL; README.md는 installer root에 포함되지 않음; failure 후 publishable outputs 0; exact tracked `.env.example`만 허용.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path
    Tool: pytest + PowerShell verifier
    Steps: temp fixture의 policy+manifest+ZIP을 세 단계 모두 검증해 entry count와 digest one-to-one을 확인한다.
    Expected: Exit 0 and every named assertion is true.
    Evidence: .omo/evidence/v1-13-0/task-5.md

  Scenario: Failure/edge case
    Tool: pytest + PowerShell verifier
    Steps: safe fixture에 각 forbidden case를 하나씩 주입한 parameterized pytest가 non-zero와 redacted category code를 확인하고 파일명/secret를 evidence에 남기지 않는다.
    Expected: The task blocks or exits nonzero exactly as stated, with no forbidden side effect.
    Evidence: .omo/evidence/v1-13-0/task-5-error.md
  ```

  **Commit**: YES | Message: `공개 패키지 금지 정책을 검증 단계에서 강제한다`; RED/GREEN receipts와 Lore trailer 포함. | Files: implementation, tests, and evidence paths listed above.

- [ ] 6. `git archive` allow-list 기반 공개 package builder와 compatibility wrapper를 완성한다

  **What to do**: elevated host에서 `Enable-WindowsOptionalFeature -Online -FeatureName Containers-DisposableClientVM -All -NoRestart`를 실행하고 restart-needed면 current task/plan/hash를 Boulder+ledger에 checkpoint한 뒤 승인된 host reboot 후 feature Enabled/executable present 상태로 resume한다. `offline_package.bat`은 `scripts/build_offline_package.ps1` compatibility wrapper로 축소한다. builder는 verified ref의 explicit policy paths를 `git archive`하고 clean temp에서 npm ci/build/production prune, `backend/requirements.txt` wheelhouse, Task 5의 two exact installers만 generated roots에 추가한다. release mode는 exact annotated tag=HEAD=version과 `dist` ZIP/SHA/manifest, QA mode는 `artifacts/qa/.../1.13.0-pr-<sha>`+`publishable=false`를 강제한다. `setup_offline.bat:169`은 runtime requirements만 설치한다. networking-disabled WSB host/guest harness는 read-only package/writable receipt mapping과 20분 timeout을 사용한다. guest는 verifier 후 Python silent installer와 Node MSI silent installer를 exit 0으로 실행하고 PATH refresh, exact versions/npm, no-pause setup/start/health/frontend/login/empty-NSA/stop을 atomic receipt로 남긴다; 3010은 FAIL이다.

  **Must NOT do**: workspace robocopy, source workspace의 `node_modules/.next/wheelhouse` 재사용, `requirements-dev.txt` wheel/package/setup install, tag 없는 timestamp fallback, public data 옵션, dev QA dependencies의 production tree/ZIP 포함, network-enabled Sandbox, interactive pause.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 8-9 | Blocked By: 5

  **References** (executor has NO interview context - be exhaustive): `offline_package.bat`; `setup_offline.bat:169`; runtime/dev requirements; frontend package/lockfile; Task 5 policies; planned builder/verifier and `scripts/sandbox/run_offline_package_smoke.ps1`, `.wsb.template`, guest bootstrap; `docs/runbook/windows-offline.md`.

  **Acceptance Criteria** (agent-executable only):
  - [ ] feature enabled/resume; dirty source 미포함; forbidden 0; release mode exact tag/HEAD/version과 three `dist` outputs, QA mode ignored `1.13.0-pr-<sha>`/publishable=false; launchers/build/runtime wheels/exact two installers 존재; dev requirements/tools 0; setup runtime requirements; manifest entry hashes 일치; WSB network disabled; guest installer exit 0/exact versions/no-pause setup-start 증명.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path
    Tool: PowerShell + Windows Sandbox
    Steps: fresh Sandbox가 두 pinned installers를 silent exit 0으로 설치하고 exact versions 확인 후 package smoke를 완료한다.
    Expected: Exit 0 and every named assertion is true.
    Evidence: .omo/evidence/v1-13-0/task-6.md

  Scenario: Failure/edge case
    Tool: PowerShell + Windows Sandbox
    Steps: tampered installer, invalid signature, nonzero/3010 exit, PATH/version mismatch, network-enabled WSB, dev wheel/missing no-pause/dirty data 중 하나면 fail-closed이고 publishable artifact 0이다.
    Expected: The task blocks or exits nonzero exactly as stated, with no forbidden side effect.
    Evidence: .omo/evidence/v1-13-0/task-6-error.md
  ```

  **Commit**: YES | Message: `공개 오프라인 패키지를 추적 소스 allow-list로 재구성한다`; wrapper contract와 package E2E receipts 포함. | Files: implementation, tests, and evidence paths listed above.

- [ ] 7. 실제 데이터를 공개 경로와 분리하는 내부 bundle builder를 TDD로 구현한다

  **What to do**: 새 crypto dependency 대신 Windows PowerShell 5.1의 `.NET System.Security.Cryptography.Pkcs` `SignedCms`/`EnvelopedCms`를 고정 사용한다. approval JSON raw UTF-8 bytes는 exact fields `schema_version,request_id,ticket_id,purpose,issued_at,expires_at,target_environment_id,recipient_thumbprint,allowed_roots,source_inventory_sha256,include_nsa`와 additionalProperties=false/TTL≤24h schema를 따르며 duplicate key를 거부하는 strict parser로만 읽는다. normal bundle은 `{newsletter,civil_aircraft,document}`의 subset과 `include_nsa=false`, NSA bundle은 `{nsa}` only와 `include_nsa=true`로 고정하고 혼합 bundle은 금지한다. 서로 다른 역할 운영자가 별도 `Sign-AeroOneInternalApproval.ps1` 실행으로 동일 raw bytes에 detached SHA-256 SignedCms를 하나씩 만든다: normal=`data_owner+security_officer`, NSA=`nsa_data_owner+security_officer`; builder는 이미 생성된 두 `.p7s`만 검증하고 private signing key를 사용하지 않는다. signer cert는 `Cert:\CurrentUser\My`, Document Signing EKU `1.3.6.1.4.1.311.10.3.12`; recipient은 `Cert:\LocalMachine\My`, Email Protection EKU `1.3.6.1.5.5.7.3.4`, private key 필수다. 모든 인증서는 thumbprint/subject/EKU/validity뿐 아니라 `CheckSignature($true)`와 Windows 조직 trust 기반 X509Chain(`RevocationMode=NoCheck`, `NoFlag`)을 통과해야 한다. external trust policy `C:\ProgramData\AeroOne\trust\internal-data-trust.json`은 exact fields `schema_version,policy_id,expires_at,max_approval_ttl_hours,allowed_roots,signers[{role,thumbprint,subject,eku_oid}],recipients[{target_environment_id,thumbprint,subject,eku_oid}]`를 갖고 owner=Administrators, inheritance disabled, SYSTEM+Administrators+authorized current SID의 Read-only ACE exact 3개만 허용한다. policy SHA-256은 `HKLM:\SOFTWARE\AeroOne\InternalData\TrustPolicySha256`에 고정하며 mismatch/absent는 FAIL이다. inner ZIP은 approval, two `.p7s`, envelope 역할의 `inventory.json`, approved content만 포함하고 EnvelopedCms AES-256-CBC OID `2.16.840.1.101.3.4.1.42`로 recipient에게 암호화한다. `Install-AeroOneInternalTrust.ps1`은 이미 조직이 발급·설치한 thumbprint만 검증/등록하고 cert/key를 생성하지 않는다. `Import-AeroOneInternalDataBundle.ps1`은 decrypt→policy/signature/chain/EKU/validity/inventory/path 전체 사전 검증 뒤 Task 3 maintenance gate 아래 same-volume staging, durable journal, old-root backup/rollback/recovery를 사용해 approved target을 교체한다. 실제 trust provisioning과 real bundle은 이번 실행 범위 밖이며 production trust absent 상태의 fail-closed test가 기준이다.

  **Must NOT do**: public data flag, repo/dist/GitHub output, env/DB/storage/backup, approval/trust/cert/signature auto-generation, builder 안에서 서명, mixed normal+NSA bundle, self-signed/unpinned/untrusted-chain cert, same signer dual role, PowerShell `ConvertFrom-Json` 단독 경계 검증, trust registry/ACL/EKU/validity/digest/target mismatch 무시, maintenance gate 없는 multi-root import, production test override, actual trust provisioning/real bundle.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 8-9 | Blocked By: 5

  **References** (executor has NO interview context - be exhaustive): `_database/` layout; `docs/INDEX.md` 비공개 policy; `docs/runbook/open-notebook-airgap.md`; planned `packaging/internal-data-approval.schema.json`, `packaging/internal-data-trust.schema.json`, `packaging/internal-data-envelope.schema.json`, `scripts/build_internal_data_bundle.ps1`, `scripts/Install-AeroOneInternalTrust.ps1`, `scripts/New-AeroOneInternalApproval.ps1`, `scripts/Import-AeroOneInternalDataBundle.ps1`; .NET `System.Security.Cryptography.Pkcs` runtime verified on this host.

  **Acceptance Criteria** (agent-executable only):
  - [ ] approval/trust/envelope schemas exact; duplicate JSON key와 altered raw approval가 FAIL; distinct pinned signer roles/EKU/validity/chain, policy digest/read-only ACL, recipient target/private-key, TTL/inventory/root profile이 모두 맞을 때만 normal/NSA synthetic bundle PASS; builder private signing key 사용 0; inner/outer schema version과 AES OID exact; importer decrypt+hash+path+maintenance-gated journal import PASS; missing registry/trust/cert/private key, same signer, untrusted/self-signed chain, expired/future, wrong EKU/role/recipient/environment, mixed roots, broad ACL, changed inventory/ciphertext/path traversal 모두 FAIL; plaintext/partial 0.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path
    Tool: pytest invoking PowerShell CMS tools
    Steps: isolated test cert store/registry adapter의 distinct owner/security/recipient cert로 normal과 NSA `.p7m`을 build/import해 exact content hashes를 확인하고 store/temp를 cleanup한다.
    Expected: Exit 0 and every named assertion is true.
    Evidence: .omo/evidence/v1-13-0/task-7.md

  Scenario: Failure/edge case
    Tool: pytest invoking PowerShell CMS tools
    Steps: signature/ciphertext bit flip, same signer, trust digest/ACL mismatch, missing recipient private key, wrong EKU, NSA normal-owner, inventory/path mutation 각각 non-zero이고 target/plain partial 0이다.
    Expected: The task blocks or exits nonzero exactly as stated, with no forbidden side effect.
    Evidence: .omo/evidence/v1-13-0/task-7-error.md
  ```

  **Commit**: YES | Message: `내부 데이터 번들의 승인 경계를 공개 패키지와 분리한다`; synthetic tests와 Lore trailer 포함. | Files: implementation, tests, and evidence paths listed above.

- [ ] 8. Next.js 15.2.9 보안 패치와 1.12.3 사고·운영 문서를 반영한다

  **What to do**: `frontend/package.json`과 lockfile에서 `next`를 exact `15.2.9`로 고정하고 install/typecheck/test/build를 수행한다. `backend/app/core/config.py` app version, `frontend/lib/changelog.ts`, README badge/release line을 1.12.3에 정렬한다. redacted `docs/reports/incident-2026-07-10-offline-asset-containment.md`를 만들고 `docs/reports/INDEX.md`, `AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`, `README.md`, `docs/INDEX.md`, `docs/CLOSED_NETWORK_GUIDE.md`, `docs/runbook/windows-offline.md`, `docs/runbook/closed-network-install-manual.md`, `docs/runbook/admin-auth.md`, 최신 handoff의 공개/내부 package·rotation·release 절차를 갱신한다. 공개 문서의 실제 credential로 오인될 literal 두 곳을 값 재기재 없이 제거하고 “setup 재실행이 기존 DB admin password를 바꾼다”는 주장을 교정한다.

  **Must NOT do**: 다른 Next minor/major, caret/tilde, 새 runtime dependency, incident 문서에 secret·hash·DB row·구 ZIP 원시 entry name, 1.13.0 조기 표기, 과장된 “미접근/완전 무노출” 주장.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: 9 | Blocked By: 4,6,7

  **References** (executor has NO interview context - be exhaustive): `frontend/package.json`; `frontend/package-lock.json`; `backend/app/core/config.py:14`; `frontend/lib/changelog.ts`; official advisories `https://nextjs.org/blog/CVE-2025-66478`, `https://nextjs.org/blog/security-update-2025-12-11`; `docs/CLOSED_NETWORK_GUIDE.md`; `docs/reports/phase-22-operator-visibility-and-module-management.md`; `README.md` credential rotation guidance.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `npm ls next`가 오직 15.2.9; lockfile exact; frontend tests/typecheck/build exit 0; version tests 1.12.3; docs의 forbidden credential literal/old setup-only claim 0; incident report는 asset/category/count/timeline/action만 포함; docs links exist; public/internal profile과 3 asset release 절차가 일치.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path
    Tool: npm + pytest + markdown scanners
    Steps: clean npm install 후 full frontend gates와 docs link/secret-pattern scanner가 PASS한다.
    Expected: Exit 0 and every named assertion is true.
    Evidence: .omo/evidence/v1-13-0/task-8.md

  Scenario: Failure/edge case
    Tool: npm + pytest + markdown scanners
    Steps: dependency tree에 15.2.0/중복 Next/floating spec이 있거나 redacted scanner가 credential-like literal을 찾으면 commit/tag/package를 차단한다.
    Expected: The task blocks or exits nonzero exactly as stated, with no forbidden side effect.
    Evidence: .omo/evidence/v1-13-0/task-8-error.md
  ```

  **Commit**: YES | Message: `Next.js 보안 패치와 1.12.3 대응 문서를 반영한다`; advisory 근거·검증 출력·Lore trailer 포함. | Files: implementation, tests, and evidence paths listed above.

- [ ] 9. 1.12.3을 clean source에서 검증·태그·배포하고 원격 자산을 재검증한다

  **What to do**: tag 생성 전에 feature=`Enabled`, Sandbox executable, exact installer policy/files/signatures, host/guest harness self-test, remote 1.12.3 tag/release absent를 먼저 확인한다. full backend/frontend/package gates와 `git pull --ff-only origin main`을 통과한 다음 local annotated tag를 만들고 release package를 생성한다. networking-disabled Sandbox는 pinned installers exit 0+exact versions 후 no-pause setup/start/health/frontend/admin-login/empty-NSA/stop receipt를 20분 안에 반환한다. smoke 실패 시 아직 unpushed local tag `git tag -d 1.12.3`, ZIP/SHA/manifest/input/receipt를 제거하고 fix commit+full retry한다. smoke 성공 후에만 main/tag push와 draft release를 만든다. upload/digest/redownload 실패는 draft assets 세 개를 모두 삭제하고 draft를 유지해 retry하며, publish/latest 후 affected old warnings의 link를 확정한다.

  **Must NOT do**: prerequisite 전 tag, failed local tag 유지/이동, test 면제, workspace reuse, Sandbox fallback, pause batch, old asset 복원, draft 검증 전 publish, orphan/partial asset, 실제 data/credential.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: 10 | Blocked By: 4-8

  **References** (executor has NO interview context - be exhaustive): `AGENTS.md` §9; `CONTRIBUTING.md`; Tasks 3-8; `offline_package.bat`; `scripts/build_offline_package.ps1`; `scripts/verify_offline_package.ps1`.

  **Acceptance Criteria** (agent-executable only):
  - [ ] prerequisites before tag PASS; full gates 0; source commit=`origin/main`=`1.12.3^{}` after push; forbidden 0; all digests identical; fresh Sandbox installer/version/setup/start/health/frontend/login/NSA/stop PASS; cleanup leak 0; failed attempt local tag/draft orphan 0; 1.12.3 public/latest; owner-approved old assets absent/warnings linked.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path
    Tool: PowerShell + Windows Sandbox + gh
    Steps: prerequisite→local tag→release package→fresh Sandbox→push/draft/digest→publish 순서가 receipt timestamps로 증명된다.
    Expected: Exit 0 and every named assertion is true.
    Evidence: .omo/evidence/v1-13-0/task-9.md

  Scenario: Failure/edge case
    Tool: PowerShell + Windows Sandbox + gh
    Steps: installer/timeout/receipt 실패는 unpushed tag+local outputs 삭제, upload/digest 실패는 draft assets 3개 삭제를 증명하고 old asset/credential은 복원하지 않는다.
    Expected: The task blocks or exits nonzero exactly as stated, with no forbidden side effect.
    Evidence: .omo/evidence/v1-13-0/task-9-error.md
  ```

  **Commit**: NO | Message: n/a | Files: annotated tag, GitHub release assets, and external receipt only.

- [ ] 10. 1.12.3 hotfix 계보를 기존 `1.13.0-dev`에 일반 merge하고 OMO 상태를 현재 root로 맞춘다

  **What to do**: 원래 dev worktree로 돌아와 approved plan hash와 planning-only dirty set을 기록하고 plan replacement/current OMO state를 한국어/Lore commit으로 보존한다. `git fetch --prune origin` 후 verified `origin/main`을 `git merge --no-ff`로 병합한다. Task 1에서 이미 current root로 교체된 boulder의 current task/HEAD만 갱신하고 ledger에 hotfix-release/merge ancestry event를 append한다. 과거 evidence는 superseded로 유지한다.

  **Must NOT do**: planner draft를 실행 상태로 재생성, 브랜치 재생성, rebase/reset/cherry-pick/force, approved plan 내용 손실, conflict에서 사용자 변경 선택적 폐기, dev branch 삭제.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: 11-27 | Blocked By: 9

  **References** (executor has NO interview context - be exhaustive): `.omo/plans/v1-13-0-operator-experience-plan.md`; `.omo/boulder.json`; `.omo/start-work/ledger.jsonl`; `AGENTS.md` §9.2; Task 9 release receipt.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `034bd03`과 `1.12.3^{}`가 모두 dev HEAD ancestor; merge parent 2개/message 7 trailer; upstream은 기존 안전 지점; OMO root stale path 0/current HEAD·task exact; approved plan tracked; unexpected dirty 0. 이 gate 이후에만 제품 파일 수정 허용.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path
    Tool: git
    Steps: merge-base ancestor 두 명령 exit 0, `git show --format=%P`가 두 parent, log parser가 한국어 본문과 trailer를 검증한다.
    Expected: Exit 0 and every named assertion is true.
    Evidence: .omo/evidence/v1-13-0/task-10.md

  Scenario: Failure/edge case
    Tool: git
    Steps: remote dev가 non-fast-forward로 바뀌거나 conflict가 계획/사용자 파일과 겹치면 merge를 완료하지 않고 상태와 conflict만 기록해 재검토한다; reset으로 숨기지 않는다.
    Expected: The task blocks or exits nonzero exactly as stated, with no forbidden side effect.
    Evidence: .omo/evidence/v1-13-0/task-10-error.md
  ```

  **Commit**: YES | Message: plan/state commit 후 `1.12.3 보안 핫픽스를 개발 브랜치에 계보 그대로 반영한다` merge commit. | Files: implementation, tests, and evidence paths listed above.

- [ ] 11. 기존 AeroOne 시각 언어를 `DESIGN.md`와 frontend design state로 먼저 고정한다

  **What to do**: root `DESIGN.md`에 정확히 `Atmosphere & Identity`, `Color`, `Typography`, `Spacing & Layout`, `Components`, `Motion & Interaction`, `Depth & Surface`, `Accessibility Constraints & Accepted Debt` 8개 섹션을 작성한다. `globals.css`, Tailwind tokens, local SVG icons/primitives에서 운영 콘솔 언어를 추출하고 Account Menu/Login/Activity/Admin tabs/horizontal chart의 loading/empty/error/disabled/degraded/focus 상태를 구현 전 정의한다. `.omo/frontend-design/state.md`에 결정·부채·증거 ledger를 만들고, import되지 않는 `frontend/components/dev/ui-state-showcase.tsx`와 component test로 primitive/state 조합을 검증한다.

  **Must NOT do**: marketing hero/landing redesign, emoji icon, 새 font/icon/chart/animation runtime dependency, raw one-off palette 확산, 기존 login/admin raw styles와 `min-h-screen` 부채를 “해결됨”으로 허위 기록, accessibility blocker의 무기록 이월.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 14,16,17,19,22-24 | Blocked By: 10

  **References** (executor has NO interview context - be exhaustive): `frontend/app/globals.css:14-161`; `frontend/tailwind.config.ts:10-93`; `frontend/components/ui/icons.tsx`; `frontend/components/ui/primitives.tsx`; `frontend/components/auth/login-form.tsx`; `frontend/components/layout/app-shell.tsx`; `frontend/components/admin/admin-console-tabs.tsx`.

  **Acceptance Criteria** (agent-executable only):
  - [ ] 8개 exact heading 존재; 기존 token/icon/spacing/motion 매핑과 accepted debt 포함; 다섯 component family의 모든 상태 정의; showcase component는 production layout/import graph에 없음; showcase test에서 light/dark, focus, loading/empty/error/degraded state 렌더; DESIGN 이전 product UI commit 0.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path
    Tool: Vitest + rg
    Steps: heading/token reference scanner와 Vitest showcase snapshot/role test가 PASS하고 200% zoom 설계 제약이 문서화된다.
    Expected: Exit 0 and every named assertion is true.
    Evidence: .omo/evidence/v1-13-0/task-11.md

  Scenario: Failure/edge case
    Tool: Vitest + rg
    Steps: 구현자가 새 token/state를 요구하면 화면 구현을 중단하고 DESIGN/state ledger를 먼저 갱신·검증한다.
    Expected: The task blocks or exits nonzero exactly as stated, with no forbidden side effect.
    Evidence: .omo/evidence/v1-13-0/task-11-error.md
  ```

  **Commit**: YES | Message: `v1.13.0 운영 UI 기준을 구현보다 먼저 고정한다`; 문서/showcase/test/Lore 포함. | Files: implementation, tests, and evidence paths listed above.

- [ ] 12. exact-pinned dev QA 도구와 격리 production-browser harness를 구축한다

  **What to do**: host Node `22.14.0`에 맞춰 exact 7종(`lighthouse@12.8.2`, 나머지는 Verification Strategy 값)을 dev dependency/lockfile에 추가하고 `npm` engine preflight를 만든다. offline product Node 20.18.0은 QA CLI 실행에 사용하지 않는다. Playwright/Lighthouse/react scripts와 root harness, isolated browser seeder를 추가한다. harness는 새 SHA runtime root, closed_network+loopback+strong synthetic secrets+새 SQLite/storage, anonymous/normal/exact-NSA/admin, stable Chrome, health/finally teardown을 강제한다.

  **Must NOT do**: real env/DB/storage 재사용, Playwright Chromium download, `npx ...@latest`, CDN, dev tool product import, QA package의 production `.next`/public ZIP 포함, listener/process/temp/secret env 잔존.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 16-27 | Blocked By: 10

  **References** (executor has NO interview context - be exhaustive): `frontend/package.json`; `frontend/vitest.config.ts`; `backend/scripts/seed.py`; `scripts/_capture_screenshots.py`(참고용이며 gate로 재사용 금지); Task 6 production dependency boundary; `docs/CLOSED_NETWORK_GUIDE.md` loopback/port rules.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `node --version=v22.14.0`; each package exact and declared engines satisfied(`lighthouse 12.8.2 >=18.16`, react-doctor >=22.13); seed safety FAIL cases; clean production smoke; stable Chrome; external network/CDN/11434 0; teardown leak 0; production output/QA ZIP dev-tool token 0.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path
    Tool: npm + Playwright stable Chrome
    Steps: Node 22.14 QA host에서 exact tools와 four identities로 production smoke를 실행하고 완전 cleanup한다.
    Expected: Exit 0 and every named assertion is true.
    Evidence: .omo/evidence/v1-13-0/task-12.md

  Scenario: Failure/edge case
    Tool: npm + Playwright stable Chrome
    Steps: Lighthouse 13.x 또는 engines mismatch, product Node 20에서 QA CLI 실행, port/health/network/existing-DB/teardown leak 중 하나면 non-zero로 다음 product task를 차단한다.
    Expected: The task blocks or exits nonzero exactly as stated, with no forbidden side effect.
    Evidence: .omo/evidence/v1-13-0/task-12-error.md
  ```

  **Commit**: YES | Message: `재현 가능한 격리 브라우저 QA 기반을 고정한다`; exact lockfile·harness self-tests·Lore 포함. | Files: implementation, tests, and evidence paths listed above.

- [ ] 13. backend admin seam을 추출하고 NSA module 상태를 모든 delivery surface에서 강제한다

  **What to do**: 기존 route contract를 characterization test로 고정하고 admin module/session/user query·mutation seam을 service files로 추출한다. 이어 `backend/app/modules/collections/service_policy.py`에 recursion-free `can_access_collection_service(db,user,collection)`을 만든다. document/civil은 기존 public `can_read_collection` 결과를 그대로 반환한다. NSA는 `ServiceModule.key='nsa'` row가 존재하고 `is_enabled=true`, `status!='hidden'`인 경우에만 canonical admin/`collections.nsa.read`/legacy `search.nsa.read`/exact resource authority를 평가하며 missing row는 false다. collection list/content/download/search, admin unified search, AI requested scope/selected refs/RAG/FTS loader가 모두 이 composed helper를 사용하게 한다. module seeding/management은 이 helper를 호출하지 않아 import recursion을 막는다.

  **Must NOT do**: endpoint/schema status 변경, Document module 상태로 public content 차단, frontend-only hide, `can_read_collection` legacy authority 제거, module seeding↔collection policy recursion, giant file 단순 이동, disabled/hidden NSA를 admin에게 예외 허용.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 18,20,21 | Blocked By: 10

  **References** (executor has NO interview context - be exhaustive): `backend/app/modules/admin/api.py`; `backend/app/modules/collections/policy.py`; `backend/app/modules/collections/api.py`; `backend/app/modules/search`; `backend/app/modules/ai`; `backend/app/modules/admin/session_fanout.py`; `backend/tests/integration/test_nsa_redteam.py`; admin/search/AI permission tests.

  **Acceptance Criteria** (agent-executable only):
  - [ ] admin characterization contract와 audit/CSRF/session fanout 유지; `api.py` query seam 추출; circular import 0; NSA active+enabled에서 네 canonical authority 모두 direct/list/content/download/search/AI PASS; disabled/hidden/missing에서 네 authority 모두 401/403 또는 scope-filtered empty; plain user 항상 deny; Document anonymous/authenticated는 module state와 무관하게 PASS; backend full suite/LSP diagnostics 0.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path
    Tool: pytest
    Steps: active NSA module에서 admin/global/legacy/resource 사용자 모두 direct content와 AI scope를 받고 Document anonymous도 유지된다.
    Expected: Exit 0 and every named assertion is true.
    Evidence: .omo/evidence/v1-13-0/task-13.md

  Scenario: Failure/edge case
    Tool: pytest
    Steps: 같은 fixtures에서 module disabled/hidden/missing을 parameterize하면 NSA의 모든 delivery surface가 fail-closed이고 Document는 계속 200; OpenAPI/admin side-effect diff는 0이다.
    Expected: The task blocks or exits nonzero exactly as stated, with no forbidden side effect.
    Evidence: .omo/evidence/v1-13-0/task-13-error.md
  ```

  **Commit**: YES | Message: `관리자 API 경계를 분리하고 NSA 모듈 중지를 서버 전면에 강제한다`; characterization/red-team receipts와 Lore 포함. | Files: implementation, tests, and evidence paths listed above.

- [ ] 14. frontend admin console의 data loader·tab registry·section shell을 분리하고 부분 실패 상태를 도입한다

  **What to do**: `admin-console-tabs.tsx`에서 `admin-console-data.ts`, `admin-console-navigation.ts`, section shell/state components를 추출한다. initial load는 `Promise.allSettled` 기반 typed per-section state(`loading|ready|empty|error`)로 바꾸어 한 endpoint 실패가 다른 데이터까지 지우지 않게 한다. 기존 nine-tab order/default Modules, numeric `1..9`, CRUD scoped refresh, 15초 session refresh를 그대로 고정하고 Overview/`0`은 Task 22에서 추가한다.

  **Must NOT do**: `Record<string, unknown>` 확대, failed value를 0/empty로 위조, 기존 tab/shortcut/CRUD behavior 변경, 250 pure LOC를 넘는 새 monolith, unrelated visual redesign.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 22-24 | Blocked By: 11

  **References** (executor has NO interview context - be exhaustive): `frontend/components/admin/admin-console-tabs.tsx`; `frontend/components/admin/sections/*`; `frontend/lib/types.ts`; `frontend/tests/components/admin-console-tabs.test.tsx`; `admin-list-ux.test.tsx`; `g003-session-list-redteam.test.tsx`; `g004-console-shortcuts-redteam.test.tsx`.

  **Acceptance Criteria** (agent-executable only):
  - [ ] 기존 9 tab/1..9/default Modules tests PASS; 한 API reject fixture에서 해당 section만 error이고 성공 section values 보존; retry가 해당 key만 refetch; mutation scoped refresh 유지; extracted shell/loader/navigation 각각 typed unit test; typecheck/full Vitest PASS.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path
    Tool: Vitest
    Steps: 15 endpoint 중 health만 reject해도 Users/Modules/Sessions가 실제 fixture 값을 유지하고 health retry 후 ready가 된다.
    Expected: Exit 0 and every named assertion is true.
    Evidence: .omo/evidence/v1-13-0/task-14.md

  Scenario: Failure/edge case
    Tool: Vitest
    Steps: any rejection으로 global empty/zero가 되거나 interval/mutation이 전체 15 endpoint를 refetch하면 test FAIL.
    Expected: The task blocks or exits nonzero exactly as stated, with no forbidden side effect.
    Evidence: .omo/evidence/v1-13-0/task-14-error.md
  ```

  **Commit**: YES | Message: `관리자 콘솔의 데이터와 탐색 경계를 분리해 부분 실패를 격리한다`; behavior receipts와 Lore 포함. | Files: implementation, tests, and evidence paths listed above.

- [ ] 15. 단일 client session provider와 canonical NSA visibility helper를 만든다

  **What to do**: AppShell은 server component로 유지하고 하위에 `ClientSessionProvider` client island 하나를 둔다. provider state는 `loading|anonymous|authenticated|unavailable`, full `ClientSession`, retry를 제공한다. `/api/frontend/session`은 `/auth/me`, `/auth/effective-permissions`, `/api/v1/admin/service-modules/public`을 server-to-server 조회해 strict-parsed accessible module hints를 반환한다. pure `canViewNsa(sessionState)`는 authenticated, NSA module `is_enabled=true`, `status!='hidden'`, 그리고 admin 또는 global `collections.nsa.read`/legacy `search.nsa.read` 또는 exact `{resource_type:'collection',resource_id:'nsa',permission_key:'collections.nsa.read'}`를 모두 검사한다.

  **Must NOT do**: AppShell 전체 client 전환, nav/account별 중복 session fetch, malformed/unavailable/loading fail-open, resource ID만 보고 권한 인정, frontend helper를 backend authz 대체물로 취급.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 16,18,19 | Blocked By: 10

  **References** (executor has NO interview context - be exhaustive): `frontend/app/api/frontend/session/route.ts`; `frontend/lib/types.ts:75-105`; `frontend/components/layout/app-shell.tsx`; `frontend/components/layout/admin-nav-link.tsx`; `backend/app/modules/admin/api.py:353-379`; `backend/app/modules/collections/policy.py:8-40`.

  **Acceptance Criteria** (agent-executable only):
  - [ ] provider fetch 1회, retry에서만 추가 fetch; anonymous/unavailable/loading/malformed/normal/wrong-permission/module-disabled/module-hidden은 NSA false; admin/두 global permission/exact resource grant는 true; Document visibility helper 없이 public 유지; session route가 backend failure를 `authenticated:null`/empty hints로 안전하게 표현; TypeScript strict PASS.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path
    Tool: Vitest + Next route tests
    Steps: test matrix의 네 valid authority path와 enabled module에서 helper true이고 session consumer 두 곳이 동일 object를 받는다.
    Expected: Exit 0 and every named assertion is true.
    Evidence: .omo/evidence/v1-13-0/task-15.md

  Scenario: Failure/edge case
    Tool: Vitest + Next route tests
    Steps: `{collection,nsa,collections.read}`, hidden module, malformed permission array, effective-permission 500에서 NSA false이며 privileged DOM 0.
    Expected: The task blocks or exits nonzero exactly as stated, with no forbidden side effect.
    Evidence: .omo/evidence/v1-13-0/task-15-error.md
  ```

  **Commit**: YES | Message: `세션 상태와 NSA 노출 판단을 하나의 권한 원천으로 통합한다`; matrix tests와 Lore 포함. | Files: implementation, tests, and evidence paths listed above.

- [ ] 16. 계정 메뉴·Document/NSA nav·AI scope를 공유 session 계약으로 전환한다

  **What to do**: `AdminNavLink`를 `AccountMenu`로 개념/파일명까지 교체한다. 이 task의 authenticated item은 admin only `관리자 콘솔`과 `로그아웃`만이며 `내 활동`은 만들거나 활성화하지 않고 Task 19가 route와 함께 첫 항목으로 원자 추가한다. trigger에는 계정 ID, SVG icon, `aria-haspopup=menu`, `aria-expanded`를 제공한다. Enter/Space/ArrowDown은 첫 항목, ArrowUp은 마지막 항목으로 열고 cyclic arrows/Home/End/Escape-focus-return/Tab-normal-close/outside-focus-or-click-close를 구현한다. logout 실패는 menu를 usable 상태로 유지하고 성공은 `/login` hard navigation한다. primary nav는 Document를 항상 유지하고 `canViewNsa` true에서만 NSA를 추가하며 `/nsa`는 `active='nsa'`를 사용한다. AI collection/scope selector도 같은 helper를 재사용한다.

  **Must NOT do**: Admin top-level sibling link, anonymous NSA, any collection:nsa grant만으로 허용, logout error에서 menu 제거, emoji icon, ARIA role만 붙이고 keyboard model 생략.

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: 19,25-27 | Blocked By: 11,12,15

  **References** (executor has NO interview context - be exhaustive): `frontend/components/layout/admin-nav-link.tsx`; `frontend/components/layout/app-shell.tsx`; `frontend/components/ai/ai-chat-workspace.tsx:462-466`; `frontend/app/nsa/page.tsx`; `frontend/components/ui/icons.tsx`; related layout/NSA/Document/AI tests.

  **Acceptance Criteria** (agent-executable only):
  - [ ] anonymous은 Login+Document/no NSA; normal은 account/logout+Document/no Admin/no Activity/no NSA; admin은 Admin Console+Logout; 네 canonical NSA authority는 enabled/non-hidden에서 NSA; unavailable/loading/wrong grant/disabled/hidden은 no NSA; AI와 nav 결과 동일; full menu keyboard/focus/logout matrix PASS; `/nsa` `aria-current=page`; 이전 mocks가 provider contract로 갱신됨.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path
    Tool: Vitest + Playwright
    Steps: component/Playwright에서 qa-nsa와 qa-admin이 keyboard만으로 Account/Admin/Logout과 NSA를 조작하고 Escape가 trigger focus를 복원한다.
    Expected: Exit 0 and every named assertion is true.
    Evidence: .omo/evidence/v1-13-0/task-16.md

  Scenario: Failure/edge case
    Tool: Vitest + Playwright
    Steps: Task 19 전 `내 활동` link가 나타나거나 qa-normal/wrong-permission/session-500/module-hidden에서 NSA/AI option이 나타나면 FAIL하며 direct NSA API 401/403을 유지한다.
    Expected: The task blocks or exits nonzero exactly as stated, with no forbidden side effect.
    Evidence: .omo/evidence/v1-13-0/task-16-error.md
  ```

  **Commit**: YES | Message: `계정 메뉴와 권한 인식 문서 탐색을 하나의 세션 계약으로 정비한다`; component/browser matrix와 Lore 포함. | Files: implementation, tests, and evidence paths listed above.

- [ ] 17. status-preserving API 오류와 단일 safe redirect 계약으로 login 흐름을 고친다

  **What to do**: `frontend/lib/api.ts`의 `browserFetch`가 기존 `ApiError(message,status)`를 일관되게 throw하도록 고치고 callers의 plain Error 가정을 갱신한다. `frontend/lib/safe-redirect.ts`의 `sanitizeNextPath`는 정확히 하나의 root-relative same-origin path만 허용하며 raw/decoded `//`, 모든 backslash, absolute/scheme/credentials, control, malformed percent encoding, 반복 decode 결과를 거부하고 fallback `/`을 반환한다. login page가 server-side로 `next`를 sanitize해 form에 전달하고 form은 submit 동안 disable+`로그인 중`, 성공 시 safe target hard navigation, 기본 `/`를 사용한다. theme redirect route도 같은 helper를 쓴다. auth proxy exact allowlist에 `activity`를 추가한다.

  **Must NOT do**: `router.push`로 untrusted raw query 사용, 한 번 decode만 검사, status를 잃는 Error wrapping, default `/admin`, form double-submit, open redirect fallback.

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: 19,25-27 | Blocked By: 11,12

  **References** (executor has NO interview context - be exhaustive): `frontend/lib/api.ts:64-83`; `frontend/components/auth/login-form.tsx`; `frontend/app/login/page.tsx`; `frontend/app/api/frontend/auth/[...segments]/route.ts`; theme route; login/proxy/api tests.

  **Acceptance Criteria** (agent-executable only):
  - [ ] ApiError 401/403/500 status 보존; safe path/query/fragment는 유지; `//`, encoded slash/backslash, `%252f%252f`, scheme, credentials, CRLF/control, malformed encoding matrix 전부 `/`; login default `/`, safe `next` exact, unsafe `/`; submit disable/loading/error; activity proxy exact segment만 허용; typecheck/full focused tests PASS.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path
    Tool: Vitest
    Steps: `/login?next=%2Factivity`에서 정상 로그인 후 browser location이 `/activity`이고 loading 중 요청 1회다.
    Expected: Exit 0 and every named assertion is true.
    Evidence: .omo/evidence/v1-13-0/task-17.md

  Scenario: Failure/edge case
    Tool: Vitest
    Steps: external/double-encoded/backslash/control payload는 모두 `/`로 가며 backend 401/500 fixture는 각각 typed status를 유지하고 DOM에 stack/URL을 노출하지 않는다.
    Expected: The task blocks or exits nonzero exactly as stated, with no forbidden side effect.
    Evidence: .omo/evidence/v1-13-0/task-17-error.md
  ```

  **Commit**: YES | Message: `로그인 오류 상태와 내부 이동 경계를 보존하도록 정비한다`; malicious redirect table과 Lore 포함. | Files: implementation, tests, and evidence paths listed above.

- [ ] 18. self-only `GET /api/v1/auth/activity` 계약과 composite index migration을 TDD로 추가한다

  **What to do**: dedicated schemas와 route를 추가하고 `get_current_user`로만 user를 결정한다. response는 `user{username,display_name,role}`, `active_sessions{created_at,last_seen_at,expires_at,is_current}` max20, `login_events{status,created_at}` max20, `ai_requests{model,status(ok|error),latency_ms,error_code,citation_count,collection_scope,created_at}` max20, `accessible_modules{key,title,href,section,status,badge,is_external}` max50로 고정한다. sessions는 user filter + `last_seen_at >= now-access_token_ttl` + non-expired, order last_seen/id desc; login/AI는 created/id desc. current auth token hash는 내부 비교에만 쓰고 반환하지 않는다. module service와 `can_read_collection`을 사용해 Document/NSA를 canonical하게 filter한다. migration `20260710_0009_self_activity_indexes.py`는 down_revision `20260707_0008`과 `(login_events.user_id,created_at)`, `(user_session_activity.user_id,last_seen_at)`, `(ai_request_logs.user_id,created_at)`을 추가한다.

  **Must NOT do**: user ID parameter, `AiConversation` query/join, auth/AI session hash join, user/database/raw IDs, IP/UA/request/conversation ID, prompt/answer/message/citation/snippet/title, admin audit/newsletter tracking, unbounded rows.

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: 19,25-27 | Blocked By: 12,13,15

  **References** (executor has NO interview context - be exhaustive): `backend/app/modules/auth/api.py`; `auth/dependencies.py:20-79`; `admin/models.py:82-163`; `collections/policy.py`; `admin/services/modules.py`; Alembic `20260707_0008`; planned `backend/tests/integration/test_auth_activity_api.py`.

  **Acceptance Criteria** (agent-executable only):
  - [ ] anonymous 401; two-user fixture cross-user rows 0; 21-row fixtures exact newest 20 and tie id-desc; active/expired/stale/current session semantics; allowed status normalization only `ok|error`; recursive forbidden-field scanner 0; Document present; NSA plain absent and canonical four authority paths present only when module enabled/non-hidden; indexes upgrade/downgrade and query plan use; focused tests RED then GREEN.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path
    Tool: pytest + Alembic
    Steps: qa-nsa가 자기 login/session/AI metadata와 safe module hints만 받고 current session 하나를 표시한다.
    Expected: Exit 0 and every named assertion is true.
    Evidence: .omo/evidence/v1-13-0/task-18.md

  Scenario: Failure/edge case
    Tool: pytest + Alembic
    Steps: 다른 사용자 rows, expired session, conversation title/content, cleared/malformed NSA gate fixture가 response에 나타나지 않으며 unauthorized NSA는 absent다.
    Expected: The task blocks or exits nonzero exactly as stated, with no forbidden side effect.
    Evidence: .omo/evidence/v1-13-0/task-18-error.md
  ```

  **Commit**: YES | Message: `사용자 자기 활동 조회를 제한된 메타데이터 계약으로 추가한다`; migration/tests/Lore 포함. | Files: implementation, tests, and evidence paths listed above.

- [ ] 19. `/activity` 화면과 typed frontend contract를 계정 메뉴에 원자적으로 연결한다

  **What to do**: dedicated TypeScript types/API client와 `frontend/app/activity/page.tsx` 및 section components를 추가한다. header identity, active sessions, login/logout, AI request metadata, accessible modules를 각 loading/empty/error 상태로 표시하고 raw content/ID를 렌더하지 않는다. `ApiError.status===401`은 `/login?next=%2Factivity` login action/redirect를, 5xx는 inline retry를 제공한다. Task 16의 `내 활동` menu item은 이 route와 같은 commit에서 활성화한다. timestamps/status는 CJK-friendly deterministic formatter와 text label을 사용한다.

  **Must NOT do**: `/activity` 외 복수 구현 선택지, admin audit reuse, IP/UA/session/request/conversation ID 노출, AI prompt/title/content, 401과 500 동일 처리, client-side user ID query.

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: 25-27 | Blocked By: 11,12,15-18

  **References** (executor has NO interview context - be exhaustive): Task 18 schemas/route; `frontend/lib/api.ts`; `frontend/lib/types.ts`; `frontend/app/api/frontend/auth/[...segments]/route.ts`; `frontend/components/layout/account-menu.tsx`; `DESIGN.md` Activity states.

  **Acceptance Criteria** (agent-executable only):
  - [ ] exact `/activity`; normal user self rows와 max20 UI; empty sections distinct; 401 safe login target; 500 retry 후 ready; forbidden field names/text DOM 0; accessible Document/NSA hints는 backend response만 사용; account menu link exact; component/typecheck tests PASS.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path
    Tool: Vitest + Playwright
    Steps: qa-normal 로그인→keyboard account menu→Activity에서 자기 current session/login/AI metadata를 확인하고 다른 fixture username/content는 보이지 않는다.
    Expected: Exit 0 and every named assertion is true.
    Evidence: .omo/evidence/v1-13-0/task-19.md

  Scenario: Failure/edge case
    Tool: Vitest + Playwright
    Steps: API 401은 safe login link, 500은 page 유지+retry, malformed payload는 sensitive fallback 없이 error state이며 console error 0.
    Expected: The task blocks or exits nonzero exactly as stated, with no forbidden side effect.
    Evidence: .omo/evidence/v1-13-0/task-19-error.md
  ```

  **Commit**: YES | Message: `사용자 자기 활동 조회 계약과 화면을 원자적으로 연결한다`; Task 16의 Activity item activation, tests, Lore 포함. | Files: implementation, tests, and evidence paths listed above.

- [ ] 20. 기존 admin dashboard를 24시간 backend Overview와 실제 session 집계로 교체한다

  **What to do**: 기존 `GET /api/v1/admin/dashboard`를 safe `AdminOverviewResponse`로 확장해 `generated_at`, current `[now-24h,now)`, previous `[now-48h,now-24h)`를 한 transaction/time anchor로 계산한다. user total/active/inactive/roles/created current/previous/delta, actual active session rows/distinct users/window minutes, login success/failure/logout current/previous/delta, AI request/failure current/previous/delta, disjoint module bucket(unavailable=disabled or hidden 우선, coming, development, active), app/env/db/newsletter/assets/read safe summary, recent audit max10 `{id,action,target_type,status,created_at}`를 반환한다. `database_url`과 full AuditEvent를 제거한다. `/sessions`는 per-session row(no hash), `active_session_count`, `active_user_count`, compatibility `active_count=active_user_count`, recent events 25를 반환하고 expiry/TTL을 함께 적용한다.

  **Must NOT do**: frontend-derived authoritative totals, overlapping module bucket, cumulative login failure를 24h로 오표기, DB URL/actor/target raw ID/IP/UA/metadata를 Overview에 포함, user-grouped row를 actual session이라 부름.

  **Parallelization**: Can Parallel: YES | Wave 4 | Blocks: 22,23,25-27 | Blocked By: 12,13

  **References** (executor has NO interview context - be exhaustive): `backend/app/modules/admin/api.py:384-427`; `backend/app/modules/admin/schemas.py:198-240`; `backend/app/modules/admin/models.py`; `backend/app/core/config.py:21`; Task 13 services; connected-user integration tests.

  **Acceptance Criteria** (agent-executable only):
  - [ ] fixed clock boundary tests가 current/previous edge를 정확히 분리; deltas deterministic; module bucket 합=전체 module 수; active_session_count는 qualifying rows, active_user_count는 distinct users; expired/stale 제외; `database_url`/full audit forbidden fields recursive 0; compatibility active_count label/semantics documented; query count bounded; full backend tests PASS.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path
    Tool: pytest
    Steps: 48시간 양쪽에 synthetic users/logins/AI/sessions/modules를 배치해 exact counts/deltas와 safe audit 10을 검증한다.
    Expected: Exit 0 and every named assertion is true.
    Evidence: .omo/evidence/v1-13-0/task-20.md

  Scenario: Failure/edge case
    Tool: pytest
    Steps: boundary timestamp, duplicate sessions per user, disabled+coming module, expired session fixture에서 double count/overlap/PII가 발생하면 test FAIL.
    Expected: The task blocks or exits nonzero exactly as stated, with no forbidden side effect.
    Evidence: .omo/evidence/v1-13-0/task-20-error.md
  ```

  **Commit**: YES | Message: `관리자 운영 집계와 실제 세션 부하를 서버의 단일 시간창으로 계산한다`; fixed-clock tests/Lore 포함. | Files: implementation, tests, and evidence paths listed above.

- [ ] 21. service module access tuple을 server merged-state 정책으로 강제한다

  **What to do**: Task 13 module service에 pure validator를 추가해 create와 PATCH의 existing+`exclude_unset` merged state를 mutation/audit 전에 검사한다. 허용 상태는 (1) admin visibility: gate 3필드 모두 null, (2) public ungated: 모두 null, (3) public global: known exact permission + resource fields null, (4) public resource: exact `collections.nsa.read/collection/nsa`만이다. partial/unknown/mismatch/unsafe ID, `collections.read+nsa`, admin+gate는 400으로 거부한다. public listing은 `is_enabled=false` 또는 `status=hidden`을 non-admin에게 반환하지 않고 NSA는 canonical collection policy를 추가 확인한다.

  **Must NOT do**: frontend validation만 신뢰, PATCH payload 일부만 검사, invalid request 후 row/audit/session-version mutation, arbitrary resource-safe permission을 module NSA tuple로 허용, admin hidden module을 일반 사용자에게 노출.

  **Parallelization**: Can Parallel: YES | Wave 4 | Blocks: 24-27 | Blocked By: 12,13

  **References** (executor has NO interview context - be exhaustive): `backend/app/modules/admin/schemas.py:142-194`; `admin/api.py:353-380,663-697`; `admin/permissions.py`; `collections/policy.py`; `backend/tests/integration/test_admin_operations_api.py:191-248`; Task 13 modules service.

  **Acceptance Criteria** (agent-executable only):
  - [ ] create/update allowed matrix PASS; 모든 reject case 400+row unchanged+audit count unchanged; toggle `is_enabled` only PATCH가 기존 valid gate를 보존; NSA gate clear 시 400이고 plain user public list에 NSA 없음; exact global known permission round-trip; hidden/disabled filtering; full permission/NSA/resource red-team tests PASS.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path
    Tool: pytest
    Steps: valid Document ungated와 exact NSA preset create/edit/toggle가 저장되고 canonical users만 public list에서 본다.
    Expected: Exit 0 and every named assertion is true.
    Evidence: .omo/evidence/v1-13-0/task-21.md

  Scenario: Failure/edge case
    Tool: pytest
    Steps: existing NSA row에 `{required_permission:null}` partial PATCH 또는 `collections.read/collection/nsa`를 보내면 400, before/after row 동일, audit 0이다.
    Expected: The task blocks or exits nonzero exactly as stated, with no forbidden side effect.
    Evidence: .omo/evidence/v1-13-0/task-21-error.md
  ```

  **Commit**: YES | Message: `서비스 모듈 접근 정책을 병합 상태 기준으로 서버에서 강제한다`; matrix tests/Lore 포함. | Files: implementation, tests, and evidence paths listed above.

- [ ] 22. dependency-free horizontal chart primitives와 기본 Overview/`0` shortcut을 구현한다

  **What to do**: pure metrics formatter와 `AdminMetricCard`, grouped/stacked horizontal bars, exact text-value list를 작은 `.ts/.tsx` 모듈로 만든다. graphic shape는 `aria-hidden`, 의미는 heading/label/value text로 제공한다. `Overview`를 첫 tab·default로 추가하고 shortcut을 `0=Overview`, 기존 `1=Modules,2=Users,3=RBAC,4=Sessions,5=System,6=Taxonomy,7=Search,8=Backups,9=Audit`로 유지한다. `aria-keyshortcuts`와 visible help를 갱신하고 editable target/modifier에서 shortcut을 무시한다. Overview는 Task 20 backend response를 authoritative aggregate로 사용하고 detail endpoint 실패는 per-section degraded/retry로 표시한다.

  **Must NOT do**: donut/ring/sparkline, chart/runtime dependency, canvas-only information, missing/error를 0으로 표시, existing shortcut remap, admin shell monolith에 모든 JSX 누적.

  **Parallelization**: Can Parallel: YES | Wave 4 | Blocks: 25-27 | Blocked By: 11,12,14,20

  **References** (executor has NO interview context - be exhaustive): `frontend/components/admin/admin-console-tabs.tsx:217-244,435-490`; Task 14 loader/navigation; Task 20 response; `DESIGN.md`; `admin-console-tabs.test.tsx`; `admin-list-ux.test.tsx`; `g004-console-shortcuts-redteam.test.tsx`.

  **Acceptance Criteria** (agent-executable only):
  - [ ] default Overview, exact 0/1..9 matrix, editable/modifier ignored, visible/ARIA help 일치; fixed fixtures의 user/session/login/AI/module values가 backend response와 exact; empty/error/degraded에 NaN/0 위조 없음; chart text values keyboard/screen-reader available; graphics aria-hidden; component LOC boundary와 typecheck/Vitest PASS.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path
    Tool: Vitest + Playwright
    Steps: admin keyboard `0`으로 Overview, `1`로 Modules, `9`로 Audit을 이동하고 screen reader query가 모든 bar label/value를 찾는다.
    Expected: Exit 0 and every named assertion is true.
    Evidence: .omo/evidence/v1-13-0/task-22.md

  Scenario: Failure/edge case
    Tool: Vitest + Playwright
    Steps: overview API 500+health success에서 health detail은 유지되고 aggregate section만 degraded; input에 `0` 입력 시 tab은 바뀌지 않는다.
    Expected: The task blocks or exits nonzero exactly as stated, with no forbidden side effect.
    Evidence: .omo/evidence/v1-13-0/task-22-error.md
  ```

  **Commit**: YES | Message: `관리자 Overview를 실제 운영 지표와 호환 단축키로 추가한다`; metrics/component tests/Lore 포함. | Files: implementation, tests, and evidence paths listed above.

- [ ] 23. Users·Sessions 화면에 실제 역할/상태/세션 부하와 결정적 paging을 추가한다

  **What to do**: frontend `AdminUser`에 `created_at/last_login_at`을 추가해 표시하고 role·active/inactive text summary와 horizontal bars를 제공한다. Users는 search/sort + client pagination 10/page, query/sort change 시 page 1 reset, empty/degraded를 분리한다. Sessions는 Task 20의 actual session/user counts, per-session rows와 login status current window를 표시하면서 기존 15초 `connectedUsers`-only refresh, last refresh, search/sort, login-event 10/page, purge confirmation/scoped refresh를 유지한다. responsive grid/scroll region을 DESIGN tokens로 조정한다.

  **Must NOT do**: cumulative failure count를 recent 25 distribution과 혼합, users endpoint 재요청 paging으로 오표기, auto-refresh가 다른 14 endpoint를 호출, synthetic chart values, PII를 QA screenshot에 사용.

  **Parallelization**: Can Parallel: YES | Wave 4 | Blocks: 25-27 | Blocked By: 11,12,14,20

  **References** (executor has NO interview context - be exhaustive): `frontend/components/admin/sections/admin-users-section.tsx`; `admin-sessions-section.tsx`; `frontend/lib/types.ts:107-175`; `admin-sessions-autorefresh.test.tsx`; `g003-session-list-redteam.test.tsx`; `admin-console-tabs.test.tsx:484-559`; Task 20 contracts.

  **Acceptance Criteria** (agent-executable only):
  - [ ] user role/status counts exact, created/last login render; 21 users가 10/10/1 page이고 search/sort reset; actual sessions 2 for one user면 session=2/user=1; recent event distribution은 25 sample로 명시; 15초 tick에서 connectedUsers만 1회; purge scope 유지; 375/768/1280 root `scrollWidth<=clientWidth+1`; no clipped controls.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path
    Tool: Vitest + Playwright
    Steps: Playwright synthetic 21 users/duplicate sessions에서 paging, search reset, 15초 refresh와 actual counts를 확인한다.
    Expected: Exit 0 and every named assertion is true.
    Evidence: .omo/evidence/v1-13-0/task-23.md

  Scenario: Failure/edge case
    Tool: Vitest + Playwright
    Steps: sessions API failure 시 이전 값 위에 stale/degraded label+retry를 보이고 0으로 바꾸지 않으며, narrow viewport horizontal root overflow가 있으면 FAIL.
    Expected: The task blocks or exits nonzero exactly as stated, with no forbidden side effect.
    Evidence: .omo/evidence/v1-13-0/task-23-error.md
  ```

  **Commit**: YES | Message: `사용자와 세션 화면에 실제 부하와 결정적 탐색을 제공한다`; timer/paging/browser tests/Lore 포함. | Files: implementation, tests, and evidence paths listed above.

- [ ] 24. Module create/edit UI에 server 정책과 일치하는 access presets·preview를 추가한다

  **What to do**: `ModuleDraft`, API types, create/edit controls에 `required_permission/resource_type/resource_id`를 완전 연결한다. pure access-policy module에서 four server states와 inline validation을 공유 표현한다. Create form은 full `Public Document`/`NSA collection` preset을 제공한다. Existing row edit의 access preset은 gate/section/visibility만 바꾸고 key/title/href/description/sort identity를 덮어쓰지 않는다. route/audience/status/access preview를 text로 제공하고 save/toggle/create/delete 후 기존 scoped refresh와 error toast를 유지한다.

  **Must NOT do**: preset이 existing identity overwrite, frontend PASS를 server authority로 취급, invalid tuple submit, toggle payload에 전체 stale draft 전송, delete 확인/audit refresh 제거.

  **Parallelization**: Can Parallel: YES | Wave 4 | Blocks: 25-27 | Blocked By: 11,12,14,21

  **References** (executor has NO interview context - be exhaustive): `frontend/components/admin/admin-console-tabs.tsx:75,131-170,320-336`; `frontend/components/admin/sections/admin-modules-section.tsx`; `frontend/components/admin/widgets/resource-grant-form.tsx`; `frontend/lib/api.ts:441-462`; Task 21 validator/tests.

  **Acceptance Criteria** (agent-executable only):
  - [ ] existing module three fields round-trip; Document preset all gates null/public/Document, NSA exact tuple; create reset fields; edit preset identity unchanged; invalid partial/unknown/unsafe/mismatch inline error+API call 0; server 400 toast and row UI unchanged; toggle only `is_enabled`; create/update/delete/toggle scoped refresh/audit behavior PASS.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path
    Tool: Vitest + pytest
    Steps: admin이 NSA preset으로 create하고 exact payload/preview를 확인한 뒤 edit preset 적용에도 key/title/href가 유지된다.
    Expected: Exit 0 and every named assertion is true.
    Evidence: .omo/evidence/v1-13-0/task-24.md

  Scenario: Failure/edge case
    Tool: Vitest + pytest
    Steps: `../nsa`, `collections.read`, partial resource를 입력하면 submit disabled/inline error이며 강제 API 400에서도 DB/audit/UI가 변하지 않는다.
    Expected: The task blocks or exits nonzero exactly as stated, with no forbidden side effect.
    Evidence: .omo/evidence/v1-13-0/task-24-error.md
  ```

  **Commit**: YES | Message: `모듈 접근 정책을 생성과 편집 화면에서 안전하게 관리한다`; frontend/backend integration receipts/Lore 포함. | Files: implementation, tests, and evidence paths listed above.

- [ ] 25. v1.13.0 동작·보안·운영 문서와 새 handoff를 구현 상태에 맞춘다

  **What to do**: `docs/reports/phase-26-operator-experience.md`와 `docs/runbook/ai-agent-handoff-2026-07-10.md`를 새로 만들고 old 2026-07-09 handoff를 superseded로 연결한다. `docs/reports/INDEX.md`, `docs/INDEX.md`, `README.md` feature/verification, `AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`, `docs/CLOSED_NETWORK_GUIDE.md`, `docs/runbook/windows-offline.md`, `admin-auth.md`, `closed-network-install-manual.md`를 실제 account/activity/NSA/module/overview/QA/package 계약과 동기화한다. incident report에는 최종 1.12.3 link/receipt를 redacted로 연결한다. 이 task에서는 README badge/release line과 app version은 1.12.3을 유지한다.

  **Must NOT do**: 구현되지 않은 기능/통과하지 않은 count 주장, secret/credential literal, 1.13.0 released 표현, old handoff 삭제, public/internal data 경계 모순, setup-only password rotation 주장.

  **Parallelization**: Can Parallel: NO | Wave 5 | Blocks: 26-27 | Blocked By: 16-24

  **References** (executor has NO interview context - be exhaustive): `AGENTS.md` §5/§9.6; `docs/reports/INDEX.md`; `docs/INDEX.md`; `docs/CLOSED_NETWORK_GUIDE.md`; `docs/runbook/ai-agent-handoff-2026-07-09.md`; Tasks 8,16-24.

  **Acceptance Criteria** (agent-executable only):
  - [ ] phase-26가 minor report 요건과 동작/위험/검증/후속 범위를 포함; new handoff가 branch/HEAD/remaining gates/PR-not-open을 정확히 기록; docs index links 모두 존재; public package data 0·internal approval·NSA rule·setup rotation caveat 일치; credential/secret scanner 0; premature `version-1.13.0`/“릴리스 1.13.0 기준” 0.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path
    Tool: markdown link checker + rg
    Steps: markdown link checker, referenced path/heading/commit existence, forbidden credential pattern, cross-doc policy matrix가 PASS한다.
    Expected: Exit 0 and every named assertion is true.
    Evidence: .omo/evidence/v1-13-0/task-25.md

  Scenario: Failure/edge case
    Tool: markdown link checker + rg
    Steps: 실제 API field/shortcut/version/package profile과 문서가 하나라도 다르거나 dead link가 있으면 Task 26을 시작하지 않는다.
    Expected: The task blocks or exits nonzero exactly as stated, with no forbidden side effect.
    Evidence: .omo/evidence/v1-13-0/task-25-error.md
  ```

  **Commit**: YES | Message: `v1.13.0 운영 경험과 보안 경계를 문서화한다`; phase/handoff/index receipts/Lore 포함. | Files: implementation, tests, and evidence paths listed above.

- [ ] 26. 전체 자동·패키지·production-browser·시각 QA를 동일 revision에서 통과시킨다

  **What to do**: backend 전체 pytest, frontend full Vitest/typecheck/build, package security/E2E, Alembic upgrade/downgrade/upgrade를 fresh 실행한다. Task 12 harness로 Browser Matrix 전체를 375×812/768×1024/1280×800 및 대표 200% zoom에서 실행하고 keyboard/focus/CJK/overflow/console/network/Axe를 측정한다. `/login`,`/activity`,`/admin` mobile+desktop Lighthouse 각 3회 median, react-doctor, react-scan render budget을 실행한다. QA-mode `1.13.0-pr-<sha>` package를 clean temp에 설치·start·health·login·빈 NSA로 smoke하고 publishable false/forbidden 0을 검증한다. 모든 fresh screenshot을 두 independent read-only visual reviewer가 같은 SHA에서 검토한다.

  **Must NOT do**: 과거 evidence 재사용, jsdom으로 browser PASS 대체, 실패를 pre-existing로 면제, real DB/credential, screenshot만 보고 network/DOM assertion 생략, source edit 후 일부 capture만 재사용, true physical-airgap release certification 주장.

  **Parallelization**: Can Parallel: NO | Wave 5 | Blocks: 27 | Blocked By: 12,19,22-25

  **References** (executor has NO interview context - be exhaustive): Tasks 5-7/12; Browser Matrix; `$visual-qa`; `frontend/tests/e2e/operator-experience.spec.ts`; `scripts/run_v1_13_browser_qa.ps1`; AGENTS test gate.

  **Acceptance Criteria** (agent-executable only):
  - [ ] backend/frontend/typecheck/build/migration/package/install 모두 exit 0; browser matrix case 누락 0; root overflow≤1px; U+FFFD/mojibake 0; unexpected console/page/request/4xx/5xx 0; external browser network/CDN/11434 0; Axe moderate/serious/critical 0; Lighthouse median 100/100/100/100; react-doctor blocking finding 0; react-scan unnecessary render 0; two visual reviewers unconditional PASS; teardown leak 0; actual final test counts 기록.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path
    Tool: pytest + npm + PowerShell QA harness
    Steps: commit SHA별 artifact 폴더에 commands/results/screenshots/traces/cleanup receipt와 reviewer verdict가 모두 있고 summary hash가 일치한다.
    Expected: Exit 0 and every named assertion is true.
    Evidence: .omo/evidence/v1-13-0/task-26.md

  Scenario: Failure/edge case
    Tool: pytest + npm + PowerShell QA harness
    Steps: 한 assertion/reviewer라도 실패하면 owning task로 돌아가 fix commit 후 전체 browser captures와 영향을 받는 자동 gate를 새 SHA에서 다시 실행한다.
    Expected: The task blocks or exits nonzero exactly as stated, with no forbidden side effect.
    Evidence: .omo/evidence/v1-13-0/task-26-error.md
  ```

  **Commit**: YES | Message: source fix는 owning task commit으로, 모두 green 뒤 `.omo/evidence/v1-13-0/task-26.md` 요약만 `v1.13.0 통합 검증 기준을 동일 리비전에서 고정한다` commit에 포함; 7 Lore trailer 필수. | Files: implementation, tests, and evidence paths listed above.

- [ ] 27. v1.13.0 release-final 메타데이터만 마지막 dev commit으로 고정한다

  **What to do**: Task 26 green SHA 이후 README version badge와 “릴리스 1.13.0 기준”, `backend/app/core/config.py` app version, `frontend/lib/changelog.ts` 최신 entry를 1.13.0으로 정렬한다. version/changelog/docs focused tests와 grep을 실행한다. 이 commit 이후 tracked source/docs를 수정하지 않고 Final Wave는 ignored artifacts만 생성한다.

  **Must NOT do**: annotated 1.13.0 tag, official ZIP/release, main merge, 기능/스타일/refactor 동시 변경, test count 추측, metadata commit 뒤 amend로 source 숨김.

  **Parallelization**: Can Parallel: NO | Wave 5 | Blocks: F1-F6 | Blocked By: 26

  **References** (executor has NO interview context - be exhaustive): `README.md` badge/verification; `backend/app/core/config.py`; `frontend/lib/changelog.ts`; version regression tests; `AGENTS.md` §9.1 step 3.

  **Acceptance Criteria** (agent-executable only):
  - [ ] repository의 release-facing current version이 exact 1.13.0이고 stale 1.12.1/1.12.2 app-version claim 0; 1.12.3는 history/incident reference로만 남음; focused tests PASS; diff가 metadata/docs line으로 제한; commit이 현재 dev의 마지막 tracked change.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path
    Tool: version tests + rg
    Steps: version scanner가 README/backend/changelog current=1.13.0 및 history entries 보존을 확인한다.
    Expected: Exit 0 and every named assertion is true.
    Evidence: .omo/evidence/v1-13-0/task-27.md

  Scenario: Failure/edge case
    Tool: version tests + rg
    Steps: metadata 외 source diff, premature tag/release, inconsistent current version 중 하나면 commit하지 않고 Task 26 green SHA로 돌아가 범위를 정리한다.
    Expected: The task blocks or exits nonzero exactly as stated, with no forbidden side effect.
    Evidence: .omo/evidence/v1-13-0/task-27-error.md
  ```

  **Commit**: YES | Message: `v1.13.0 릴리스 표기와 검증 기준을 최종 고정한다`; metadata-only diff와 Lore 포함. | Files: implementation, tests, and evidence paths listed above.


## Final Verification Wave

> ALL must APPROVE. Present consolidated results to the user and get explicit `okay` before declaring the execution complete.

- [ ] F1. Plan Compliance Audit

  독립 reviewer가 Original Request·다섯 권고·Must Have/Not·Task 1-27을 changed files/tests/evidence와 양방향으로 매핑한다. 누락, 근거 없는 PASS, stale evidence 재사용, out-of-scope 변경이 0일 때만 `APPROVE`한다. 결과는 `artifacts/qa/v1.13.0/<sha>/reviews/f1-plan-compliance.md`에 저장한다.

- [ ] F2. Code Quality Review

  `$review-work`를 현재 SHA에 읽기 전용으로 실행해 goal/constraint, code quality, security, hands-on QA, context fidelity 5개 관점에서 검토한다. admin seam/LOC, Python/TypeScript strictness, transaction/error handling, test quality, dead/duplicate path, raw UI token/slop을 검사한다. 모든 reviewer가 조건 없는 `APPROVE`여야 한다.

- [ ] F3. Real Manual QA

  Task 27 SHA에서 backend/frontend/package gates와 Browser Matrix를 다시 실행한다. metadata/changelog가 UI에 보이므로 screenshot·Axe·Lighthouse·react-doctor/react-scan evidence를 전부 새로 만든다. 두 independent visual reviewer가 같은 fresh capture를 375/768/1280·200%·light/dark·degraded 상태에서 검토해 둘 다 조건 없이 승인해야 한다.

- [ ] F4. Scope Fidelity Check

  Original Request/IN/OUT과 changed-file map, docs link/heading/version/credential-literal/policy matrix, 모든 commit의 한국어 본문·7 Lore trailer를 확인한다. `034bd03`/`1.12.3^{}` ancestry, 2-parent merge, dev 보존, 1.13 tag/release/main merge/official ZIP/real internal bundle 없음과 unrelated diff 0을 승인 조건으로 한다.

- [ ] F5. Security and Release Audit

  별도 security reviewer가 1.12.2/owner-approved historical containment, 1.12.3 release/digest, credential rotation/quarantine receipts, public policy/verifier, CMS internal approval/import boundary, QA ZIP entry categories를 재검증한다. old approved URLs 404, known-old credential reject, public forbidden 0, real internal bundle 0, secret evidence 0이어야 한다.

- [ ] F6. dev push와 한국어 PR 본문 준비 후 PR 생성 직전에서 중단

  F1-F5 unconditional PASS hash가 현재 HEAD와 같은지 확인하고 `git diff --check`, full `git status`, secret/generated-artifact staging scan을 수행한다. `git push origin 1.13.0-dev` 후 `git rev-list --left-right --count HEAD...origin/1.13.0-dev`가 `0 0`인지 확인한다. `artifacts/qa/v1.13.0/<sha>/pr-body.md`에 한국어 제목과 `변경 배경 / 핵심 수정 사항 / 검증 결과(명령+실제 출력) / 영향 범위 / 후속 작업`을 작성하고 1.12.3 incident/hotfix receipt를 선행 외부 조치로만 링크한다. `gh pr list`로 open 1.13 PR 없음만 확인하고 `gh pr create` 및 `--dry-run`은 실행하지 않는다. 최종 tracked worktree는 clean이어야 한다.

모든 final reviewer는 동일한 최종 revision을 읽기 전용으로 검토한다. 하나라도 조건부 승인·수정 요청이면 해당 owner task로 돌아가 수정하고, 영향을 받는 Task 26-27 및 F1-F5를 모두 새 revision에서 다시 실행한다. F6는 F1-F5가 모두 무조건 승인한 뒤에만 실행한다.

## Commit Strategy

- hotfix main worktree와 dev worktree를 분리하고 서로의 dirty 파일을 stage하지 않는다.
- 권장 atomic commit 순서:
  1. `노출 가능 자격증명을 데이터베이스 기준으로 일괄 회전한다`
  2. `공개 오프라인 패키지에서 운영 비밀과 데이터를 구조적으로 차단한다`
  3. `내부 데이터 번들의 승인 경계를 공개 패키지와 분리한다`
  4. `Next.js 보안 패치와 1.12.3 대응 문서를 반영한다`
  5. `1.12.3 보안 핫픽스를 개발 브랜치에 계보 그대로 반영한다` (2-parent merge)
  6. `v1.13.0 운영 UI 기준과 재현 가능한 QA 기반을 고정한다`
  7. `계정 메뉴와 권한 인식 탐색 및 로그인 흐름을 정비한다`
  8. `사용자 자기 활동 조회 계약과 화면을 추가한다`
  9. `관리자 운영 집계와 모듈 접근 정책을 서버에서 강제한다`
  10. `관리자 Overview와 사용자 세션 모듈 UX를 강화한다`
  11. `v1.13.0 운영 경험과 보안 경계를 문서화한다`
  12. `v1.13.0 릴리스 표기와 검증 기준을 최종 고정한다`
- 모든 commit은 한국어 제목과 1~3개 한국어 본문 문단 뒤에 `Constraint`, `Rejected`, `Confidence`, `Scope-risk`, `Directive`, `Tested`, `Not-tested`를 실제 값으로 기록한다.
- release 1.12.3 tag는 annotated tag로 만들고, dev는 squash하지 않으며 1.12.3 commit을 일반 merge로 계승한다.
- 최종 `git log` parser가 범위 내 모든 commit의 7개 trailer 누락 0을 확인한다.

## Success Criteria

- 공개 1.12.2와 감사에서 unsafe로 판정된 과거 asset은 제거되고 각 release/tag/원문 notes는 보존된다.
- exact current workspace env와 deduplicated canonical DB의 자격증명·세션 대응이 값 없는 receipt로 증명되며 예상 밖 provider/root는 publish blocker다.
- 공개 1.12.3 ZIP은 code/runtime-only이고 manifest/sha/GitHub digest 및 clean offline smoke가 일치한다.
- 내부 데이터 builder는 synthetic 승인 테스트만 통과하며 실제 bundle을 만들거나 업로드하지 않는다.
- `1.13.0-dev`는 1.12.3 hotfix 계보를 보존한다.
- Document 공개성과 canonical NSA 권한/모듈 상태가 모든 UI/API/AI surface에서 일치한다.
- 일반 사용자는 자기 활동만 보고 민감 콘텐츠·식별자를 받지 않는다.
- 관리자 Overview는 24시간 backend 집계와 실제 세션 수를 표시하고 degraded 상태를 0으로 위조하지 않는다.
- module access tuple은 server merged-state validation으로 보호된다.
- backend 전체, frontend test/typecheck/build, package verifier/smoke, browser matrix, Axe, Lighthouse, react-doctor, react-scan, 두 visual reviewer와 security/scope review가 모두 PASS다.
- README/backend/changelog가 1.13.0으로 최종 정렬되고 문서 link/credential-literal 검사도 PASS다.
- 최종 branch는 clean, upstream과 `0 0`, 1.13 PR/tag/release 없음, ignored artifact에 한국어 PR 본문이 준비돼 있다.
