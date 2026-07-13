# v1.13.0 Ultragoal 핸드오프 — Claude Code 이어받기 (2026-07-12 밤, 최종판)

이 문서는 중단된 세션을 **AeroOne v1.13.0 direct release Ultragoal** 로 이어서 완료하기 위한 단일 진실 원천입니다. 이 문서만으로 별도 맥락 없이 재개할 수 있습니다.

> **2026-07-13 현재 상태가 아래 2026-07-12 스냅샷보다 우선합니다.** 아래 내용은 계보와 설계 근거로 보존하며, 재개 작업은 이 갱신 블록부터 시작합니다.

## 현재 재개 지점 — PR 생성 직전 검증 준비

| 항목 | 현재 상태 |
|---|---|
| 작업 위치 | `D:/Chanil_Park/Project/Programming/AeroOne`, branch `1.13.0-dev` |
| 기준 HEAD | `d0f73ca9983d4973cf27c4a8b00e92d49d76b15e` 뒤에 최종 hardening 변경이 미커밋 상태 |
| 원격 차이 | `origin/1.13.0-dev`보다 54 commits ahead, 아직 이번 최종 변경 push 없음 |
| 구현 | Activity 모듈 가시성/미지 역할 fail-closed, Admin Overview·Sessions 실제 데이터, BFF no-store·오류 비공개, allow-list 패키지 경계, SHA-bound browser/React 진단 hardening 완료 |
| 코드 정리 리뷰 | backend policy, frontend failure handling, package boundary, browser evidence 네 lane 모두 `CLEAR/CLEAR/CLEAR`, `APPROVE`, blocker/advisory 0 |
| 현재 테스트 | frontend 전체 **397 passed / 73 files**, typecheck 0; backend full은 clipboard 점유 timeout 1건 외 **566 passed**, 같은 clipboard 파일 단독 재실행 **2 passed**; package focused **35 passed**; browser contract **14 passed**; Ruff와 `git diff --check` 통과 |
| 릴리스 상태 | main merge, tag, GitHub Release 모두 아직 수행하지 않음 |

### 현재 미커밋 변경의 목적

1. 서버가 Activity와 Admin 모듈 목록을 동일한 역할·권한·resource gate 정책으로 계산하고, 알 수 없는 역할·상태를 정상값으로 위조하지 않게 한다.
2. Activity 응답과 frontend BFF가 성공·오류 모두 `no-store`를 유지하고 백엔드 오류 본문이나 민감 헤더를 복사하지 않게 한다.
3. 관리자 세션 화면이 sibling 요청 실패나 out-of-order 응답 때 실제 마지막 성공값을 보존하고 가짜 0을 만들지 않게 한다.
4. 오프라인 패키지가 exact annotated `v1.13.0`과 immutable captured commit에서만 publishable 산출물을 만들고 tests/QA/dev dependency를 제외하게 한다.
5. Browser QA가 clean exact SHA/BUILD_ID, loopback HTTP·WebSocket, local locked diagnostics, stale receipt 선삭제, 공통 redaction, atomic receipt를 강제하게 한다.

### 정확한 남은 순서

1. 현재 전체 변경과 문서 통계를 한 한국어+Lore 커밋으로 고정한다.
2. 그 clean SHA에서 backend 567, frontend 397, typecheck, production build를 다시 실행한다. clipboard 통합 테스트는 다른 프로세스 점유로 timeout 나면 전체 결과와 격리 재실행을 모두 보존하되 최종 릴리스 판단에는 실제 PASS가 필요하다.
3. 같은 SHA로 `qa:browser:all`을 실행해 smoke/matrix/Axe/Lighthouse/React 진단 receipt와 비균일 screenshot을 만든다.
4. 같은 SHA로 QA 오프라인 ZIP을 만들고, 별도 빈 테스트 폴더에서 인터넷 없음(`PIP_NO_INDEX=1`) 조건으로 설치·마이그레이션·seed·loopback 기동·health 200을 확인한 뒤 테스트 폴더를 삭제한다.
5. frozen SHA에 대해 Architect 3-lane과 Executor QA/red-team을 합류시키고 strict Ultragoal quality gate를 만든다.
6. G017~G024의 실제 완료·대체 관계를 `goals.json`과 `ledger.jsonl`에 checkpoint한다. G022의 main merge/tag/release는 PR 승인 뒤 단계이므로 임의 완료 금지다.
7. `1.13.0-dev`를 push하고 한국어 정식 PR을 생성한 뒤 mergeability/check 상태를 확인한다.
8. **PR 병합 직전 중단하고 사용자에게 결과 표를 보고한다.** 사용자 승인 전 main merge, annotated tag, GitHub Release, asset upload를 수행하지 않는다.

---

## 0. 목표(변경 금지)

`.gjc/ultragoal/goals.json` 의 durable 계획 전체 완료. 감사 추적은 `.gjc/ultragoal/ledger.jsonl`.
승인된 실행 계획(불변):
- `.gjc/_session-019f5114-23ef-7000-bb80-6cff38ba0ead/plans/ralplan/019f5114-23ef-7000-bb80-6cff38ba0ead/pending-approval.md`
- SHA-256 `23c51be829cd61bc5741f809a22a6098d93e5e6898ed73c3317f44dee0e0f63a`

최종 산출: 공유 세션/계정 내비게이션, 안전 로그인 리다이렉트, self-only `/activity`, 실제 Admin Overview/Users/Sessions/Modules, Document/NSA/AI 가시성 일관성, 반응형/접근성, 재현 가능한 오프라인 패키지, 한국어 정식 PR + phase report 1건 이상 + main no-ff + annotated `1.13.0` tag + ZIP/SHA GitHub Release(업로드 후 재다운로드 digest 검증).

Goal 순서(gjc ultragoal 이 관리): G017(계보+Wave0) → G018(Wave1 세션/로그인) → G019(Wave2 Activity) → G020/G021(Wave3 Admin) → G022(RC/PR/릴리스). 체크포인트 요구: `architectReview:CLEAR+APPROVE`, `executorQa:passed`. 현재 CLI next-action 은 G018 실행 단계였고 G017 은 review-blocker 기록 상태.

---

## 1. 왜 진행이 막혔는가 (근본 원인 — 코드 문제 아님)

1. **에이전트 도구 인프라 장애**: 세션 중반 `task`/`subagent` 가 0B 출력·2~6초 실패(모델 라우팅 장애) → 복구 → **세션 말미에 `subagent` 도구 자체 소실**("Tool subagent not found"). Wave 3 두 작업(48/49)은 파일을 전부 디스크에 착지시켰으나 최종 보고 수신 불가.
2. **마지막 턴 중단**: Wave 3 통합 검증 중 frontend 전체 Vitest 실행 도중 턴이 abort 됨. 그 직전까지의 검증 결과는 §3-C 에 기록.
3. **긴 backend full suite(30~50분) × receipt SHA 바인딩**: provenance 게이트는 `HEAD==--sha && clean tree` 요구 → 커밋마다 재실행 필요. 이 루프와 리뷰 지적(영수증 덮어쓰기/경로 누출/출처 불명 → 수정 → 재생성 → junction 실경로 누출 발견)이 겹치며 마감 절차가 길어짐.

제품 구현(Wave 0~3)은 사실상 전부 끝났다. 남은 것은 **Wave 3 마감(검증 잔여+커밋) → 영수증 재생성 → 리뷰/체크포인트 → Wave 4 RC/릴리스**.

---

## 2. 완료·커밋된 것 (branch `1.13.0-dev` = `47ceec0`, origin 대비 ahead 33 — **push 0건, tag 0건, release 0건**)

| SHA | 내용 | 검증 영수증 |
|---|---|---|
| `a6c4a6d` | Gate M 완료: 검증된 hotfix 계보 no-ff 병합(`175d0fd`) → root ff-only 착지. 관리자 셸에서도 runas limited-token 으로 일반 토큰 ACL 계약 실증 | backend 486 PASS, frontend 319 PASS, smoke PASS (`artifacts/qa/v1.13.0/a6c4a6d…/`) |
| `a01db20` | QA 영수증 결함 수정: `results-<project>.json` 분리 + redact reporter(실패 시 원본 삭제 fail-closed) + SHA-bound `scripts/qa/run_v113_backend_gates.mjs` | **provenance receipts 전부 exit 0**: backend 486 / package 112 / migration 10 / 단일 head `20260710_0009` — `.worktrees/v1.13.0-hotfix-integration/artifacts/qa/v1.13.0/a01db20…/gates/` |
| `476e6ff` | **Wave 1 (G018)**: 세션 BFF 파생 플래그(is_admin/can_view_document/can_view_nsa/can_use_ai; no-store; 하드코딩 loopback fallback 제거), AccountMenu(내 활동/Admin/로그아웃, aria/Escape/포커스 복귀), `resolveSafeNext`(///스킴/백슬래시/제어문자/인코딩 우회 전부 '/' 로 거부), ApiError 안전 한국어 카테고리, AI workspace 인라인 NSA 재계산 제거 | frontend 365 PASS + typecheck + build, smoke PASS, NSA/collections 정책 54 PASS |
| `47ceec0` | **Wave 2 (G019)**: `GET /api/v1/auth/activity` 동결 계약 구현(query/body→422, 401, no-store, 각 섹션 최신20 desc+id desc, 알 수 없는 상태 fail-closed 생략, module_key 항상 null, ID/해시/IP/UA/프롬프트 직렬화 0), `session_hash.hash_session_token` 정본화(기록·현재세션 비교·로그아웃 통일), 마이그레이션 `20260712_0010`((user_id,created_at) 인덱스, fresh up→down→up 왕복 PASS), `/activity` 한국어 UI + auth BFF allowlist 'activity' | backend 집중 38 PASS, frontend 371 PASS + typecheck + build, smoke PASS |

부수 상태: root `frontend/node_modules` 는 lockfile 대로 재설치됨(QA deps 포함), root `frontend/.next` 는 47ceec0 기준 build. `.worktrees/v1.13.0-hotfix-integration` = `a01db20`(venv/node_modules junction 연결). `.worktrees/v1.13.0-browser-harness` = `c1966cc`(역할 종료, 보존).

**G017 최종 리뷰 상태**(a01db20 대상, 재실행 완료):
- Architect: `CLEAR/CLEAR/WATCH`, `COMMENT`, **blockers []** (잔여는 P2/P3 advisory).
- Executor QA: 3개 blocker 중 2개 해소 확인(영수증 분리·출처). **잔여 1건**: worktree junction `.venv` 의 실경로(`D:\Chanil_Park\…`)가 `gates/*.stderr.log` 에 누출(REPO_ROOT prefix 매칭 우회). → 수정 코드가 §3-B 로 디스크에 있음(미커밋).
- matrix/axe/lighthouse/실제 패키지 빌드 부재는 승인 계획상 **Wave 4 RC 게이트로 이연 확정** — 재리뷰 시 scope ruling 문구로 반드시 명시할 것(안 하면 QA 요원이 다시 blocker 로 올림).

---

## 3. 디스크의 미커밋 작업 (다음 세션 첫 처리 대상)

`git status` 정확한 목록(2026-07-12 23시 기준):

### 3-A. Wave 3 (G020+G021) 구현 — 서브에이전트 착지 완료
- **backend**: `app/modules/admin/api.py`(신규 `GET /api/v1/admin/overview`, 구 `GET /dashboard` 제거, `/sessions` per-session rows + `active_session_count`/`active_user_count`/호환 `active_count`), `schemas.py`(AdminSummaryResponse 제거·Overview/Connected 스키마), 신규 `overview_service.py`(build_overview, 고정 시계 주입 가능), 신규 `module_policy.py`(모듈 gate 400 매트릭스: admin+gate/부분 gate/미지 권한/자원 불일치/unsafe id/`collections.read`+nsa 전부 400, 변이 전 차단), 테스트 신규 `tests/integration/test_admin_overview_api.py`·`tests/unit/test_module_policy.py`, 수정 `tests/integration/test_admin_operations_api.py`.
- **frontend**: `admin-console-tabs.tsx`(fetchAdminSummary→fetchAdminOverview), 신규 `sections/admin-overview-section.tsx`+`tests/components/admin-overview-section.test.tsx`, users/sessions/modules/system 섹션 확장(Users 10/page·검색/정렬 시 1페이지 리셋·login events 10/page·empty vs degraded 구분, Sessions 2세션/1사용자=2/1·degraded retry, Modules gate 필드 요약+400 안전 토스트), admin 테스트 10개 파일 mock 교체.
- **integrator 선반영분**(같은 미커밋 덩어리): `lib/api.ts` `fetchAdminOverview`(fetchAdminSummary 삭제), `lib/types.ts` `AdminOverviewResponse`/`ConnectedUsersResponse` 확장 + **죽은 `AdminSummary` 인터페이스 삭제**, `tests/lib/api.test.ts` 를 overview 경로(`/api/frontend/admin/overview`)로 갱신.

### 3-B. `scripts/qa/run_v113_backend_gates.mjs` 리댁션 강화
`fs.realpathSync(REPO_ROOT|PYTHON|BACKEND_CWD)` 로 junction 실경로를 정규화해 `[REPO_ROOT]` 치환 루트에 추가(경로에서 `\backend\` 마커 앞부분을 루트로 절단). `node --check` 통과. **G017 잔여 QA blocker 해소분.**

### 3-C. Wave 3 사전 검증 — 이미 통과한 것 / 남은 것
이미 통과(이 세션에서 실측):
- backend 집중 게이트: `test_admin_overview_api.py + test_module_policy.py + test_admin_operations_api.py + test_admin_rbac_matrix.py` → **52 passed**.
- `ruff check app/modules/admin` → clean.
- frontend `tsc --noEmit` → **0 errors** (api.test.ts/AdminSummary 정리 후).

남은 것(턴 abort 로 미완):
1. frontend **전체 Vitest** (`cd frontend && npm test`) — 실행 도중 중단됨, 처음부터 재실행 필요.
2. `npm run build`.
3. §4 Step 2 이후 전부.

---

## 4. 다음 세션 실행 순서 (정확한 명령)

작업 디렉토리: `D:/Chanil_Park/Project/Programming/AeroOne` (root, branch `1.13.0-dev`).

### Step 1 — Wave 3 잔여 검증
```bash
cd frontend && npm test && npm run build
# 실패 시 §3-A 동결 계약을 기준으로 테스트/구현 수정(계약 변경 금지)
```

### Step 2 — Wave 3 + 리댁션 수정 일괄 커밋
- 대상: §3 의 `git status` 목록 전체(핸드오프 문서 포함 가능).
- 형식: 한국어 제목(의도)+본문 1~3문단+Lore trailer 7키(Constraint/Rejected/Confidence/Scope-risk/Directive/Tested/Not-tested). AGENTS.md §3 참조.

### Step 3 — 새 SHA(S3)에서 영수증 재생성
```bash
cd frontend
SHA=$(git rev-parse HEAD); export QA_SHA="$SHA"
npm run qa:browser:setup -- --sha "$SHA" && npm run qa:browser:smoke; rc=$?
npm run qa:browser:teardown -- --sha "$SHA"; test $rc -eq 0
cd .. && node scripts/qa/run_v113_backend_gates.mjs --sha "$SHA" --suite all   # backend full 포함 ~30-50분
grep -rl "Chanil_Park" artifacts/qa/v1.13.0/$SHA/gates/ || echo REDACTION_OK   # 0건이어야 함
```
게이트 러너는 clean tree + HEAD==SHA 필수. root 실행 가능(스크립트가 자기 위치 기준).

### Step 4 — 리뷰 lane + 체크포인트 소진
- S3 기준 Architect(3-lane CLEAR+APPROVE)·Executor QA(passed) 재실행. **scope ruling 필수 포함**: "matrix/axe/lighthouse·실제 패키지 빌드는 Wave 4 RC 게이트(승인 계획)이며 G017~G021 blocker 아님".
- 통과 후 `gjc ultragoal complete-goals` 흐름으로 G017→G018→G019→G020→G021 체크포인트 기록(증거: §2 표 + S3 영수증 + §3-C 결과). 상태 전환 오류 시 `gjc state ultragoal … --force` 전례 참조.
- 서브에이전트 도구 불가 시: 리뷰 게이트를 임의 생략하지 말고 사용자에게 수동 승인 여부 확인.

### Step 5 — Wave 4 (G022) RC → 릴리스
1. **browser 전체**: `/activity`·`/admin` 실존하므로 `npm run qa:browser:all -- --sha <S>` (setup→smoke→matrix→axe→lighthouse→react→teardown; Lighthouse 는 합성 `qa-admin`/`QA-admin-v1130-strong!` 인증 경로 감사). 기준: Axe moderate+ 0, Lighthouse median 100×4, 375/768/1280+200% zoom overflow 0, react-doctor blocking 0.
2. **패키지 QA-A**: exact RC SHA 에서 `powershell -File scripts/build_offline_package.ps1`(-DryRun 먼저) → **사용자 지정 빈 폴더 실제 오프라인 설치·기동·성공·삭제**(1.12.3 전례: PIP_NO_INDEX=1, wheelhouse, Alembic head `20260712_0010`, seed, health 200; 기본 포트 18437/29501 은 사용자 dashboard-enhancements 점유 — 소유 포트만 사용).
3. 버전 표기: `frontend/lib/changelog.ts` CHANGELOG[0]→1.13.0(화면 버전 뱃지 근원), `backend/app/core/config.py` app_version, README 뱃지+검증 줄, docs INDEX/CLOSED_NETWORK_GUIDE/AGENTS 정합.
4. phase report ≥1건: `docs/reports/phase-27-*.md` + reports/INDEX.md (minor 필수).
5. **한국어 정식 PR**(1.13.0-dev→main): 배경/핵심/검증(명령+출력)/영향/후속. → **사람 승인 대기 = 유일한 pause 지점**.
6. 승인 후: main `merge --no-ff`(한국어+Lore), annotated tag `1.13.0`, exact-tag 재빌드 ZIP+sha256 을 `gh release upload`, 재다운로드 digest 대조. 보상 규칙: pre-push 실패는 로컬 tag/소유 산출물만 삭제 후 전체 재시도, pushed tag 이동 절대 금지(결함은 patch 계보).

---

## 5. 동결 계약 (변경 = 버전 증가 + 소비자 재검증)

- **ClientSession v1**: `.omo/evidence/v1-13-0/contracts/frontend-shared-v1.md`. snake_case 파생 플래그, BFF 단독 계산, 실패 시 보호 플래그 false + Document 공개, ApiError 안전 한국어 메시지(401 로그인이 필요합니다/403 접근 권한이 없습니다/422/429/5xx), 원문 본문 노출 금지.
- **Activity v1**: §2 의 47ceec0 항목. `module_key` 항상 null(추론 금지), 역할 미지값→pending fail-closed.
- **AdminOverviewResponse v1 + ConnectedUsers 확장**: §3-A. `frontend/lib/types.ts` 가 mirror. `database_kind` 만 노출(URL 금지), recent_audit 은 {id,action,target_type,status,created_at} max10, 모듈 4버킷 disjoint-sum(unavailable=disabled∨hidden 우선).
- **session hash**: `backend/app/modules/auth/session_hash.py` 유일 구현(UTF-8 SHA-256 lowercase hex).
- **browser harness**: exact pins(@playwright/test 1.61.1, axe 4.12.1, lighthouse 12.8.2, playwright-lighthouse 4.0.0, react-doctor 0.7.3, react-scan 0.5.7, react-grab 0.1.48 — scan/grab 은 설치 계약만, mutating init CLI 금지), 설치된 Chrome 만, QA_SHA 40자 소문자 hex, loopback 전용, 정리 fail-closed.

## 6. 함정 / 환경 특이사항

- cygwin bash 에서 `.venv/Scripts/python.exe` 상대경로 실행 불가 → **항상 절대경로** `D:/Chanil_Park/Project/Programming/AeroOne/backend/.venv/Scripts/python.exe`.
- `backend/alembic/env.py` 는 Settings.database_url 강제 → 임시 DB 는 `DATABASE_URL` env 주입(APP_ENV=test).
- worktree `frontend/node_modules`·`backend/.venv` 는 junction — 로그 실경로 누출은 §3-B 로 해결(커밋 필요).
- Playwright worker 가 config 재평가 시 `--project` argv 없음 → 첨부물이 `playwright/all/` 로 감(P2 advisory, 폴더명에 project 포함되어 비파괴).
- teardown/wait 의 `wmic.exe` 의존은 Win11 24H2+ 제거 가능성(P3; 현 머신 동작). 개선 시 `Get-CimInstance`.
- P3 advisory 잔여: 합성 자격증명 3파일 중복(e2e/prepare/lighthouse), 포트 할당 TOCTOU, BUILD_ID↔SHA 바인딩 없음 — RC 전 선택 개선.
- `dashboard-enhancements` worktree/프로세스는 **사용자 작업 — 종료/수정 금지**.
- production `.env`/canonical DB/`%USERPROFILE%/AeroOne-secure` 무접촉 유지. reset/checkout/clean/rebase/squash/force 금지. 브랜치 삭제 금지(release archaeology).
- live 배포 scope 가 노출 자격증명 범위와 겹치면 rotation receipt 전 릴리스 차단(별도 운영 승인 사안).
- 백엔드 full suite 를 두 개 동시에 돌리지 말 것(과거 rotation 테스트 경합·플레이크 원인; 포트 격리는 이미 커밋됨).

## 7. 영수증 지도

- **G017 정본**: `.worktrees/v1.13.0-hotfix-integration/artifacts/qa/v1.13.0/a01db20…/gates/`(backend/package/migration/migration-heads receipt 전부 exit 0, 단 stderr 로그에 실경로 누출 1건 → S3 재생성으로 대체) + `browser/playwright/results-smoke.json`(리댁션 검증 완료) + `browser/react-diagnostics.json`.
- Wave1/2 smoke: root `artifacts/qa/v1.13.0/{476e6ff…,47ceec0…}/browser/`.
- a6c4a6d 통합 스냅샷: root+worktree `artifacts/qa/v1.13.0/a6c4a6d…/`(backend-final 486, browser, package, migration).
- 이전 세션 로그: `.omo/evidence/v1-13-0/session-progress-2026-07-12.md`. **본 문서가 최신 인계본.**
