---
slug: v1-13-0-operator-experience-plan
status: decision-needed
intent: clear
review_required: true
pending-action: Task 2 증적에 적힌 1.12.2 외 historical exact ZIP/SHA 14쌍 삭제 승인을 받은 뒤 실행을 재개하고, 이후 Windows Sandbox가 restart를 요구할 때 별도 host reboot 승인을 받는다
approach: 공개 자산 containment와 1.12.3 보안 핫픽스를 선행한 뒤, v1.13.0-dev에서 인증 후 문서/NSA 진입, 계정 메뉴, 일반 사용자 활동, 관리자 통합 대시보드와 모듈/사용자/세션 UX를 개발해 PR 생성 직전까지 검증한다.
---

# Draft: v1-13-0-operator-experience-plan

## Components (topology ledger)
| id | outcome | status | evidence path |
| --- | --- | --- | --- |
| C1 | `1.13.0-dev` 작업 브랜치와 디자인 시스템 기준을 먼저 고정한다. | active | `.omo/evidence/task-1-v1-13-0-operator-experience-plan.md`, `.omo/evidence/task-2-v1-13-0-operator-experience-plan.md` |
| C2 | 로그인 후 Document/NSA 네비게이션과 계정 메뉴를 세션/권한 기반으로 재구성한다. | active | `.omo/evidence/task-3-v1-13-0-operator-experience-plan.md`, `.omo/evidence/task-4-v1-13-0-operator-experience-plan.md` |
| C3 | 일반 사용자가 자기 최근 활동을 볼 수 있는 self-scoped API와 화면을 만든다. | active | `.omo/evidence/task-5-v1-13-0-operator-experience-plan.md`, `.omo/evidence/task-6-v1-13-0-operator-experience-plan.md` |
| C4 | 관리자 콘솔에 Overview 기본 탭과 상태 시각화 그래프를 추가한다. | active | `.omo/evidence/task-7-v1-13-0-operator-experience-plan.md`, `.omo/evidence/task-8-v1-13-0-operator-experience-plan.md` |
| C5 | 사용자/세션 로드와 모듈 관리 UX를 운영자가 쓰기 쉬운 밀도 높은 화면으로 개선한다. | active | `.omo/evidence/task-9-v1-13-0-operator-experience-plan.md`, `.omo/evidence/task-10-v1-13-0-operator-experience-plan.md` |
| C6 | 문서, 회귀 테스트, 폐쇄망/브라우저 smoke를 v1.13.0 릴리즈 게이트에 맞춘다. | active | `.omo/evidence/task-11-v1-13-0-operator-experience-plan.md`, `.omo/evidence/final-v1-13-0-operator-experience-plan.md` |

## Open assumptions (announced defaults)
| assumption | adopted default | rationale | reversible? |
| --- | --- | --- | --- |
| UI/차트 라이브러리 | 새 런타임 의존성을 추가하지 않고 기존 Tailwind/CSS/SVG/로컬 `Icon` 시스템을 확장한다. | 폐쇄망 ZIP 패키징과 node_modules 번들 안정성이 핵심이다. | yes |
| NSA 노출 | 로그인 후에도 `collections.nsa.read` 또는 `collection:nsa` 권한이 있는 사용자에게만 NSA 탭을 보인다. | 백엔드 `can_read_collection` 정책을 약화하면 보안 회귀다. | no for this scope |
| 로그인 성공 이동 | 모든 사용자를 `/admin`으로 보내지 않고 기본 `/`로 보낸 뒤 계정 메뉴에서 관리자 콘솔로 진입한다. | 일반 사용자 활동 화면과 관리자 메뉴 요구를 모두 만족한다. | yes |
| 일반 사용자 최근 작업 | 새 스키마보다 기존 `LoginEvent`, `UserSessionActivity`, `AiRequestLog`, 현재 AI 대화 세션을 self API로 묶는다. | user-scoped 조회가 가능하고 데이터 마이그레이션 위험이 낮다. | yes |
| 디자인 방향 | 사내 운영 콘솔이므로 마케팅 랜딩처럼 만들지 않고, 로그인 화면만 더 풍부한 command-center 스타일로 고도화한다. | 반복 업무 UI는 밀도와 스캔성이 우선이다. | yes |
| 관리자 콘솔 | 기존 탭을 제거하지 않고 `overview` 탭을 첫 탭/기본값으로 추가한다. | 기존 운영 동선을 보존하면서 통합 상황판을 제공한다. | yes |
| 버전 표기 | 개발 초기에 README badge를 `1.13.0`으로 바꾸지 않고 릴리즈 직전 버전 커밋에서만 갱신한다. | 저장소 릴리즈 사이클 규칙과 맞춘다. | yes |

## Findings (cited - path:lines)
- Git: 현재 `main...origin/main`, 최신 태그 `1.12.2`, `1.13.0-dev` 브랜치 없음. 작업 전 `git switch -c 1.13.0-dev origin/main` 필요.
- Dirty worktree risk: 현재 `.omo/`, `_codex_exports/`, `pkg264_082120*`, `pkg264_082225*` 가 untracked. 실행자는 제품 작업 중 이 파일들을 커밋 대상에서 제외해야 한다.
- 디자인 시스템: `DESIGN.md`/`design-system.md`/`design-tokens.md` 검색 결과 없음. UI 구현 전 디자인 시스템 파일 생성 필요.
- `frontend/package.json:6-10`, `frontend/package.json:13-30`: Next 15.2.0 + React 19 + Tailwind 3.4.17 + Vitest, 별도 아이콘/차트 런타임 없음.
- `frontend/components/ui/icons.tsx:1`: 로컬 currentColor SVG 아이콘 시스템 존재. 새 관리자/활동/차트 아이콘은 여기 확장.
- `frontend/components/layout/app-shell.tsx:13-17`, `frontend/components/layout/app-shell.tsx:69-103`: 상단 nav는 Dashboard/Newsletter/Document 고정, NSA active 상태 없음, 우측은 `AdminNavLink`.
- `frontend/components/layout/admin-nav-link.tsx:21-88`: 사용자명, Admin 링크, 로그아웃이 한 줄에 직접 노출됨.
- `frontend/components/auth/login-form.tsx:15-16`: 로그인 성공 후 항상 `/admin` 이동.
- `backend/app/modules/admin/api.py:80`, `backend/app/modules/admin/api.py:353-379`: `document`/`nsa` service module과 권한 필터가 이미 존재.
- `backend/app/modules/collections/policy.py:9-29`: document/civil은 public, nsa는 권한 사용자만 허용.
- `frontend/components/admin/admin-console-tabs.tsx:217-244`, `frontend/components/admin/admin-console-tabs.tsx:513-522`: 관리자 콘솔은 9개 탭이며 기본 탭은 `modules`, 별도 overview 탭 없음.
- `frontend/components/admin/admin-console-tabs.tsx:75`, `frontend/components/admin/sections/admin-modules-section.tsx:174-198`, `backend/app/modules/admin/schemas.py:155-157`: backend는 모듈 권한 필드를 제공하지만 frontend module draft/UI는 `required_permission/resource_type/resource_id`를 노출하지 않음.
- `frontend/components/admin/sections/admin-sessions-section.tsx:25-26`, `frontend/components/admin/sections/admin-sessions-section.tsx:104-139`: 세션/로그인 이벤트 UI는 존재하지만 세로 영역과 시각화가 제한적.
- `backend/app/modules/auth/api.py:79-89`, `backend/app/modules/admin/models.py:87-121`, `backend/app/modules/admin/models.py:148-162`: 자기 활동 API는 로그인 이벤트, 세션 활동, AI 요청 로그를 기반으로 구성 가능.
- `backend/app/modules/ai/models.py:24-40`, `backend/app/modules/ai/repositories.py:21-32`, `backend/app/modules/ai/api/public.py:266-279`: AI 대화는 세션 소유 기반으로 목록화되어 있고, `user_id` 컬럼은 nullable로 준비되어 있음.

## Decisions (with rationale)
- 이 계획은 `intent: unclear` 로 유지한다. 사용자가 "잘 생각해서 고도화"를 요청했으므로 추가 질문 대신 저장소 제약과 운영 UI 모범값을 채택한다.
- 서브에이전트 Metis/Momus 리뷰는 현재 도구 정책상 사용자가 명시적으로 "서브에이전트/병렬 에이전트"를 요청하지 않아 실행하지 않는다. 대신 계획 자체에 F1-F4 최종 검증과 실행자 QA 증거를 강제한다.
- 새 dependency는 금지 기본값으로 둔다. Lucide/차트 라이브러리는 사용자가 별도 승인할 때만 도입한다.
- self activity는 관리자 audit 전체를 일반 사용자에게 노출하지 않는다. 일반 사용자는 자기 로그인/세션/AI 요청/현재 AI 대화/접근 가능 모듈만 본다.
- Newsletter read tracking은 IP 기반이므로 "내 최근 작업"으로 표시하지 않는다. 향후 user_id 기반 read tracking을 별도 기능으로 확장할 수 있다.
- 관리자 콘솔 Overview는 기존 9개 탭 위에 추가되는 10번째 구조가 아니라 첫 번째 `overview` 탭이다. 숫자 단축키는 `1=Overview`부터 다시 매핑하고 10번째 탭은 `0` 또는 단축키 없음 중 구현 시 하나로 고정한다.

## Scope IN
- `1.13.0-dev` 브랜치 생성.
- `DESIGN.md` 추가.
- 로그인 UI 고도화와 깨진 한글 문구 정리.
- 세션/권한 기반 Document/NSA nav 노출.
- 계정 메뉴 컴포넌트: 내 활동, 관리자 콘솔, 로그아웃.
- 일반 사용자 최근 활동 API/프론트 화면.
- 관리자 Overview 탭과 SVG/CSS 기반 그래프.
- 사용자/세션 로드 시각화와 세로 패널 확장.
- 모듈 관리 탭의 권한형 모듈 필드/프리셋/미리보기 UX.
- 테스트, 문서, 폐쇄망 smoke 가이드 갱신.

## Scope OUT (Must NOT have)
- NSA 권한 우회, 공개화, 비밀번호식 가림막 회귀.
- 새 런타임 UI/차트 dependency 추가.
- README 버전 badge를 릴리즈 전 조기 변경.
- `.env`, 관리자 비밀번호, JWT secret, `_database/`, `dist/`, ZIP 산출물 커밋.
- 관리자 감사 로그 원문 또는 AI prompt/answer/snippet을 일반 사용자 화면에 노출.
- 랜딩 페이지식 hero/마케팅 화면.

## Open questions
- 없음. 승인된 기본값으로 계획을 작성한다.

## Approval gate
status: approved
approved-by-user: "승인"
approved-action: write `.omo/plans/v1-13-0-operator-experience-plan.md`

## Re-review — 2026-07-10

### Current verdict

- `git pull --ff-only` on `1.13.0-dev`: `Already up to date.`
- Branch state: `HEAD=034bd03`, upstream `origin/1.13.0-dev`, remote divergence `0 0`, main divergence `2 0`.
- Verdict: **INVALID AS WRITTEN / DIRECTIONALLY VALID**. Product work must not start from the current plan until the blockers below are corrected and the required dual review approves the revised plan.

### Blocking corrections

1. Replace the stale branch-creation task with current-branch reconciliation; never recreate or reset `1.13.0-dev`.
2. Keep Document public, and make NSA fail-closed through one shared session provider plus the canonical permission/resource tuple.
3. Fix the self-activity contract to exact `GET /api/v1/auth/activity` and `/activity`, bounded self-only fields, active sessions plus login/logout events, and `AiRequestLog` metadata only. Exclude `AiConversation` titles/content and never join auth/AI session hashes.
4. Add the missing frontend proxy allowlist, status-preserving `ApiError`, hardened same-origin `next` sanitizer, deterministic 401 behavior, and complete menu-button keyboard/focus tests.
5. Add server-side merged-state validation for service-module permission/resource tuples; frontend validation remains UX assistance only.
6. Narrow the session/users task to real deltas, define metric windows and source precedence, and prevent DB URLs or real PII from entering Overview screenshots/evidence.
7. Make browser QA reproducible with an isolated database, synthetic admin/normal/NSA accounts, exact start/health/teardown commands, and measurable assertions.
8. Split behavior docs, full regression/browser QA, release-final version metadata, and release packaging into separate tasks; add `docs/reports/phase-26-operator-experience.md` and the reports index.
9. Add a release-safety gate before any new ZIP: exclude real environment files and local agent state, inspect staging and ZIP entry names fail-closed, and reconcile the `_database` distribution policy.

### Security evidence (names only; contents not read)

- Existing `dist/AeroOne-offline-1.12.2-20260708-081654.zip` contains `.env`, `backend/.env`, `backend/.env.bak`, `frontend/.env.local`, and `frontend/.env.local.bak`.
- Its local SHA256 `b67f595f...c2e4cd` matches the GitHub Release asset digest exactly, so the published 1.12.2 asset has the same entries.
- The same ZIP contains 90 `_database` entries. `_database` inclusion was historically intentional for content snapshots, but its distribution through a GitHub Release is an owner-level data policy decision.
- `.omo` and `.codegraph` are absent from that existing ZIP but are not excluded by the current robocopy rule, so a new package can capture them unless the batch is fixed.
- Until containment is decided, do not redistribute, rebuild, or upload an offline ZIP from this workspace.

### Verification receipts

- Backend focused auth/session/AI/NSA/ResourceGrant/admin tests: 63 passed, 3 unrelated deprecation warnings.
- Frontend focused layout/auth/proxy/NSA/document tests: 31 passed across 7 files; `npm run typecheck` passed.
- Full backend/frontend parallel baseline attempt did not return results because the Git Bash tool call timed out; it is not recorded as a test failure or success.
- Plan/draft/handoff files are valid UTF-8. PowerShell's default decoding caused the observed mojibake display; no encoding rewrite is justified.

### Owner decision required before plan revision

- **Recommended:** GitHub Release ZIP is code/runtime-only with empty or curated non-sensitive sample content; live `_database` content travels as a separately approved internal data bundle.
- Alternative: keep a `_database` snapshot in the Release ZIP only with an explicit per-root allowlist, content-owner approval, and a forbidden-entry manifest check. NSA content must never be included by default.

The required Momus plus independent Codex high-accuracy review remains pending until this owner decision is resolved and the plan is revised.

## Owner decision resolved — 2026-07-10

- 사용자는 추천안 1~5를 모두 승인했다.
- 공개 GitHub Release ZIP은 코드·런타임 전용으로 전환하며, `_database`, 운영 DB, storage, 실제 환경 파일은 0개여야 한다.
- 비민감 공개 샘플은 저장소에 추적되는 seed Markdown만 허용하고, 실제 운영 자료에서 파생한 샘플과 NSA 샘플은 금지한다.
- 실데이터는 공개 packager와 다른 도구·출력 루트·승인 manifest를 사용하는 내부 번들로만 전달한다. NSA는 별도 명시 승인과 권한 있는 수신 환경이 모두 없으면 실패해야 한다.
- 제품 개발 전 P0 경로는 공개 1.12.2 자산 봉쇄, 모든 계정의 DB-aware 자격증명·세션 무효화, fail-closed packager/verifier, Next.js 15.2.9 보안 패치, 검증된 1.12.3 교체 릴리스다.
- 이후 `origin/main`의 hotfix를 `1.13.0-dev`에 merge하고 v1.13.0 제품 개발을 진행한다. PR은 생성하지 않고 push와 한국어 PR 본문 준비 직전에서 중단한다.
- 이 결정으로 owner-level open question은 모두 닫혔으며, 다음 단계는 Metis 보완 → 계획 교체 → Momus 및 독립 고정밀 검토다.

## Momus review 1 — 2026-07-10

- Verdict: REJECT.
- 교정 대상: `setup_offline.bat`의 runtime requirements 불일치, current-environment 회전 root/key/DB 범위, internal approval의 signature/trust-anchor schema, Windows Sandbox 자동 harness, Activity menu task ownership, planner scaffold/draft state.
- 추가 자체 발견: 같은 취약 packager로 생성된 과거 공개 release asset도 중앙 디렉터리 이름만 감사하고 위험 자산을 함께 봉쇄해야 한다.
- 현재 환경의 값 없는 inventory 결과: root/backend env에서 회전 대상은 `JWT_SECRET_KEY`와 `ADMIN_PASSWORD`; frontend env에는 URL key만 존재; root/backend `DATABASE_URL`은 동일한 `backend/data/aeroone.db`로 resolve되어 한 번만 처리한다.
- unknown provider 또는 추가 deployment는 자동 추정·회전하지 않고 blocker로 보고한다. 사용자 상태/role은 변경하지 않고 password/session만 회전한다.
- Host prerequisite: Windows 10 Pro/Administrator이지만 Windows Sandbox feature는 Disabled이고 executable이 없다. 실행 계획은 feature enable 후 restart-needed checkpoint를 남기며 자동 reboot는 하지 않는다.

## High-accuracy review 2 — 2026-07-10

- Momus verdict: REJECT. Historical asset deletion exact authority, clean Sandbox installers, production internal trust model, deterministic quarantine, template/draft lifecycle을 교정 대상으로 지적했다.
- Independent verdict: REVISE. Immediate 1.12.2-first ordering, all local unsafe artifacts, known-old credential evidence, executable crypto consumer, Sandbox feature/installers/tag cleanup, Node/Lighthouse engines, backend NSA module-state owner, Boulder state를 추가로 지적했다.
- Planning-only central-directory audit completed across 46 releases: 15 ZIP assets are unsafe under the new public policy; exact ZIP/SHA IDs are recorded in the plan. Contents/entry streams were not opened.
- Current host facts: Windows 10 Pro, Administrator, Sandbox disabled; Node 22.14.0; stable Chrome present; Python 3.13 has cryptography but the selected internal design uses verified PowerShell 5.1 SignedCms/EnvelopedCms; exact Python 3.12.7 and Node 20.18.0 signed installers already exist locally with pinned hashes/signers.
- Corrections applied: Task 1 immediately contains only approved 1.12.2; Task 2 audits/presents exact historical IDs and blocks without approval; local unsafe artifacts move to a one-year current-SID quarantine with no deletion; rotation uses DPAPI journal and known-old-only negative proof; package includes pinned silent installers; Sandbox prerequisites occur before tag with local-tag cleanup; Lighthouse is 12.8.2; Task 13 owns backend NSA module-state enforcement; Task 7 owns CMS build+import contract.
- The actual ulw-plan SKILL template was re-read. Required Context/Work Objectives structure is retained, headings/task fields/parallelization/checklist QA/commit format are normalized to that source rather than reviewer-invented `Scope` scaffolding.

## Execution checkpoint — 2026-07-10 18:50 KST

- Task 1 완료: release/tag/body suffix를 보존하고 1.12.2 exact asset IDs `469662394`/`469662393`만 삭제했다. 두 old URL 404와 dual CRLF/LF body hash를 확인했다.
- Task 2 read-only 구간 완료: `git pull --ff-only`는 up to date, 46 releases/원격 ZIP 14/local contained receipt 1을 중앙-directory-only로 감사해 15 unsafe, error 0, mismatch 0을 확인했다.
- Legacy planning verdict의 `backup`은 dependency basename 오탐이었다. 고정 정책 결과는 env/database/storage/agent-state/dev-artifact 또는 storage 계열이며 계획표와 증적을 교정했다.
- Task 1 외 historical release에는 warning/delete를 수행하지 않았다. 추천안 전체 승인과 별개로 irreversible exact-ID deletion은 `.omo/evidence/v1-13-0/task-2.md`의 14 ZIP/SHA pair에 대한 명시 승인을 기다린다.
- 이 승인 전에는 계획 계약상 Task 3, 1.12.3 hotfix/release, v1.13.0 제품 구현을 시작하지 않는다.

## Destructive-action dry-run checkpoint — 2026-07-10 19:01 KST

- exact-contract 실행기 `.omo/evidence/v1-13-0/task-2-contain-historical-assets.sh`를 추가했다.
- 기본 모드는 read-only이며 12 releases/14 ZIP-SHA pairs/28 assets를 현재 ID·digest·body hash·other-assets hash와 대조해 exit 0, mutation 0을 확인했다.
- `--execute`는 exact approval token이 없으면 GitHub 조회·변경 전에 exit 64로 거부된다. `--help`, rejection path, dry-run을 실제 CLI로 확인했다.
- 실행기는 준비됐지만 승인 토큰은 owner 승인 자체가 아니다. historical 14쌍의 irreversible delete는 여전히 명시 승인을 기다린다.
